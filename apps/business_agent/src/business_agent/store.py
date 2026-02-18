# Copyright 2026 UCP Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""UCP."""

import asyncio
from decimal import Decimal
import json
import logging
import os
from pathlib import Path
import sys
from typing import Optional
from uuid import uuid4
from pydantic import AnyUrl
import libsql_client

# UCP: All checkout models come from the ucp_sdk package
from ucp_sdk.models.schemas.shopping.checkout_resp import (
    CheckoutResponse as Checkout,
)
from ucp_sdk.models.schemas.shopping.discount_resp import (
    AppliedDiscount,
    DiscountsObject,
)
from ucp_sdk.models.schemas.shopping.fulfillment_resp import (
    Checkout as FulfillmentCheckout,
)
from ucp_sdk.models.schemas.shopping.fulfillment_resp import Fulfillment
from ucp_sdk.models.schemas.shopping.payment_resp import PaymentResponse
from ucp_sdk.models.schemas.shopping.types.fulfillment_destination_resp import (
    FulfillmentDestinationResponse,
)
from ucp_sdk.models.schemas.shopping.types.fulfillment_group_resp import (
    FulfillmentGroupResponse,
)
from ucp_sdk.models.schemas.shopping.types.fulfillment_method_resp import (
    FulfillmentMethodResponse,
)
from ucp_sdk.models.schemas.shopping.types.fulfillment_option_resp import (
    FulfillmentOptionResponse,
)
from ucp_sdk.models.schemas.shopping.types.fulfillment_resp import (
    FulfillmentResponse,
)
from ucp_sdk.models.schemas.shopping.types.item_resp import ItemResponse as Item
from ucp_sdk.models.schemas.shopping.types.line_item_resp import (
    LineItemResponse as LineItem,
)
from ucp_sdk.models.schemas.shopping.types.order_confirmation import (
    OrderConfirmation,
)
from ucp_sdk.models.schemas.shopping.types.postal_address import PostalAddress
from ucp_sdk.models.schemas.shopping.types.shipping_destination_resp import (
    ShippingDestinationResponse,
)
from ucp_sdk.models.schemas.shopping.types.total_resp import (
    TotalResponse as Total,
)
from ucp_sdk.models.schemas.ucp import ResponseCheckout as UcpMetadata
from .helpers import get_checkout_type
from .models.product_types import ImageObject, Product, ProductResults

DEFAULT_CURRENCY = "USD"
logger = logging.getLogger(__name__)

# Add SCAPI integration import
try:
    from scapi_integration import SalesforceSyncClient, SCAPIConfig
    from scapi_integration.models import get_state_code, get_country_code
    SCAPI_AVAILABLE = True
    print("DEBUG: SCAPI integration found and imported.")
    logger.info("SCAPI integration loaded successfully")
except ImportError:
    SCAPI_AVAILABLE = False
    print("DEBUG: SCAPI integration NOT found (ImportError).")
    logger.warning("SCAPI integration not available, using fallback to products.json")


class RetailStore:
    """Mock Retail Store for demo purposes.

    Uses in-memory data structures to store products, checkouts, and
    orders.
    """

    def __init__(self):
        """Initialize the retail store."""
        self._products = {}
        self._checkouts = {}
        self._orders = {}
        self._scapi_client: Optional[SalesforceSyncClient] = None
        self._use_scapi = SCAPI_AVAILABLE and os.getenv("USE_SCAPI", "true").lower() == "true"
        # Passwordless auth state
        self._auth_mode: str = "guest"  # "guest" or "registered"
        self._customer_email: Optional[str] = None
        self._customer_addresses: list = []
        
        self._initialize_ucp_metadata()
        self._initialize_products()
        self._initialize_db()
        
        # Initialize SCAPI configuration check
        if self._use_scapi:
            try:
                self._scapi_client = SalesforceSyncClient()
                logger.info("SCAPI client initialized (Sync)")
            except Exception as e:
                logger.warning(f"Failed to initialize SCAPI client: {e}. Falling back to static products.")
                self._use_scapi = False

    def _initialize_db(self):
        """Initialize database connection (currently in-memory only)."""
        self._db_url = None
        self._db_token = None
        self._db_client = None
        
        logger.info("Store initialized in IN-MEMORY mode (Turso disabled).")
        print("DEBUG: Using In-Memory storage for this session.")

    def _save_checkout_to_db(self, checkout: Checkout):
        if self._db_client:
            try:
                data_json = checkout.model_dump_json()
                self._db_client.execute(
                    "INSERT INTO agent_checkouts (id, data) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data = EXCLUDED.data",
                    (checkout.id, data_json)
                )
            except Exception as e:
                logger.error(f"Failed to save checkout to Turso: {e}")

    def _load_checkout_from_db(self, checkout_id: str) -> Optional[Checkout]:
        if self._db_client:
            try:
                rs = self._db_client.execute("SELECT data FROM agent_checkouts WHERE id = ?", (checkout_id,))
                if rs.rows:
                    data = json.loads(rs.rows[0][0])
                    # Determine checkout type
                    from .helpers import get_checkout_type_from_data
                    checkout_type = get_checkout_type_from_data(data)
                    return checkout_type.model_validate(data)
            except Exception as e:
                logger.error(f"Failed to load checkout from Turso: {e}")
        return None

    def _save_order_to_db(self, order_id: str, checkout: Checkout):
        if self._db_client:
            try:
                data_json = checkout.model_dump_json()
                self._db_client.execute(
                    "INSERT INTO agent_orders (id, data) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data = EXCLUDED.data",
                    (order_id, data_json)
                )
            except Exception as e:
                logger.error(f"Failed to save order to Turso: {e}")

    # ── Auth Mode Management ──────────────────────────────────────────

    def set_auth_mode(self, mode: str) -> str:
        """Set the authentication mode (guest or registered).

        Args:
            mode: 'guest' or 'registered'

        Returns:
            Confirmation message.
        """
        self._auth_mode = mode.lower()
        logger.info(f"Auth mode set to: {self._auth_mode}")
        return f"Authentication mode set to: {self._auth_mode}"

    @property
    def auth_mode(self) -> str:
        """Get current auth mode."""
        return self._auth_mode

    @property
    def is_registered_user(self) -> bool:
        """Check if operating in registered user mode with active token."""
        return (
            self._auth_mode == "registered"
            and self._scapi_client is not None
            and self._scapi_client.is_authenticated
        )

    # ── Passwordless Authentication ───────────────────────────────────

    def request_passwordless_login(self, user_email: str) -> bool:
        """Request passwordless OTP for a registered user.

        Args:
            user_email: The user's registered email.

        Returns:
            True if OTP was sent successfully.
        """
        if not self._use_scapi or not self._scapi_client:
            logger.error("SCAPI client not available for passwordless login")
            return False

        self._customer_email = user_email
        return self._scapi_client.request_passwordless_login(user_email)

    def verify_passwordless_otp(self, otp_code: str) -> Optional[str]:
        """Exchange OTP code for passwordless access token.

        Args:
            otp_code: The 6-digit OTP from email.

        Returns:
            customer_id if successful, None otherwise.
        """
        if not self._use_scapi or not self._scapi_client:
            logger.error("SCAPI client not available for OTP verification")
            return None

        token_data = self._scapi_client.get_passwordless_token(otp_code)
        if token_data:
            self._auth_mode = "registered"
            customer_id = token_data.get("customer_id")
            logger.info(f"Passwordless auth successful. customer_id={customer_id}")
            return customer_id

        return None

    # ── Customer Address Management ───────────────────────────────────

    def get_customer_addresses(self) -> list:
        """Fetch all saved addresses for the authenticated customer.

        Returns:
            List of address dicts with addressId, address1, city, etc.
        """
        if not self._use_scapi or not self._scapi_client:
            return []

        customer_id = self._scapi_client.customer_id
        if not customer_id:
            logger.error("No customer_id available — user not authenticated")
            return []

        customer_data = self._scapi_client.get_customer(customer_id)
        if not customer_data:
            return []

        addresses = customer_data.get("addresses", [])
        self._customer_addresses = addresses
        logger.info(f"Retrieved {len(addresses)} saved addresses for customer {customer_id}")
        return addresses

    def get_customer_address(self, address_id: str) -> Optional[dict]:
        """Fetch a specific customer address by addressId.

        Args:
            address_id: The addressId label (e.g. 'Home Address').

        Returns:
            Address dict or None.
        """
        if not self._use_scapi or not self._scapi_client:
            return None

        customer_id = self._scapi_client.customer_id
        if not customer_id:
            logger.error("No customer_id available — user not authenticated")
            return None

        return self._scapi_client.get_customer_address(customer_id, address_id)


    def _initialize_ucp_metadata(self):
        """Load UCP metadata from data/ucp.json."""
        base_path = Path(__file__).parent
        ucp_path = base_path / "data" / "ucp.json"
        with ucp_path.open() as f:
            self._ucp_metadata = json.load(f)

    def _initialize_products(self):
        """Load products from a JSON file and store them for lookup (fallback)."""
        # Only load static products if not using SCAPI or as a fallback
        if not self._use_scapi:
            base_path = Path(__file__).parent
            products_path = base_path / "data" / "products.json"
            try:
                with products_path.open() as f:
                    products_data = json.load(f)
                    for product_data in products_data:
                        # we only have products in the json file
                        product = Product.model_validate(product_data)
                        self._products[product.product_id] = product
                logger.info(f"Loaded {len(self._products)} products from JSON")
            except Exception as e:
                logger.warning(f"Failed to load products from JSON: {e}")

    def search_products(self, query: str) -> ProductResults:
        """Search the product catalog for products that match the given query.

        Args:
            query (str): shopping query

        Returns:
            ProductResults: product items that match the criteria of the query

        """
        # Use SCAPI if available, otherwise fall back to static products
        if self._use_scapi and self._scapi_client:
            try:
                logger.info(f"SCAPI searching for: {query}")
                scapi_products = self._scapi_client.search_products(query, count=50)
                
                if scapi_products:
                    products = []
                    for p_data in scapi_products:
                        product = Product(**p_data)
                        self._products[product.product_id] = product
                        products.append(product)
                    
                    logger.info(f"Found {len(products)} products from SCAPI (Sync)")
                    return ProductResults(results=products)
                else:
                    logger.info("No products found in SCAPI")
                    return ProductResults(results=[], content="No products found")
            except Exception as e:
                logger.error(f"SCAPI search failed: {e}. Falling back to static products.")
                # Fall through to static search
        
        # Fallback: search static products
        all_products = list(self._products.values())

        matching_products = {}

        keywords = query.lower().split()
        for keyword in keywords:
            for product in all_products:
                if product.product_id not in matching_products and (
                    keyword in product.name.lower()
                    or (
                        product.category
                        and keyword in product.category.lower()
                    )
                ):
                    matching_products[product.product_id] = product

        product_list = list(matching_products.values())
        if not product_list:
            return ProductResults(results=[], content="No products found")

        return ProductResults(results=product_list)

    def get_product(self, product_id: str) -> Product | None:
        """Retrieve a product by its SKU.

        Args:
            product_id (str): Product ID

        Returns:
            Product | None: Product object if found, None otherwise

        """
        # Check cache first
        if product_id in self._products:
            return self._products[product_id]
        
        # If using SCAPI, try to fetch from API
        if self._use_scapi and self._scapi_client:
            try:
                logger.info(f"Fetching product {product_id} from SCAPI (Sync)")
                scapi_product = self._scapi_client.get_product(product_id)
                
                if scapi_product:
                    product = Product.model_validate(scapi_product)
                    # Cache it
                    self._products[product.product_id] = product
                    return product
            except Exception as e:
                logger.error(f"Failed to fetch product from SCAPI: {e}")
        
        return None

    def _get_line_item(self, product: Product, quantity: int) -> LineItem:
        """Create a line item for a product.

        Args:
            product (Product): Product object
            quantity (int): Quantity of the product

        Returns:
            LineItem: Line item object

        """
        # read product.offers.price, convert to Decimal
        if not product.offers or not product.offers.price:
            raise ValueError(f"Product {product.name} does not have a price.")

        unit_price = int(Decimal(product.offers.price) * 100)

        image_url = None

        if isinstance(product.image, list):
            if isinstance(product.image, str):
                image_url = product.image
            elif isinstance(product.image, list) and product.image:
                first_image = product.image[0]
                if isinstance(first_image, str):
                    image_url = first_image
                elif isinstance(first_image, ImageObject):
                    image_url = first_image.url

        return LineItem(
            id=uuid4().hex,
            item=Item(
                id=product.product_id,
                price=unit_price,
                title=product.name,
                image_url=AnyUrl(image_url) if image_url else None,
            ),
            quantity=quantity,
            totals=[],
        )

    def add_to_checkout(
        self,
        metadata: UcpMetadata,
        product_id: str,
        quantity: int,
        checkout_id: str | None = None,
    ) -> Checkout:
        """Add a product to the checkout.

        Args:
            metadata (UcpMetadata): UCP metadata object
            product_id (str): Product ID of the product to add to checkout
            quantity (int): Quantity of the product to add
            checkout_id (str | None, optional): checkout identifier

        Returns:
            Checkout: checkout object

        """
        product = self.get_product(product_id)
        if not product:
            raise ValueError(f"Product with ID {product_id} is not found")

        # Use SCAPI if available
        if self._use_scapi and self._scapi_client:
            try:
                # 1. Create basket if it doesn't exist
                if not checkout_id:
                    logger.info("Creating new SCAPI basket (Sync)")
                    checkout_id = self._scapi_client.create_basket()
                    if not checkout_id:
                        raise ValueError("Failed to create SCAPI basket")
                    print(f"\n*** SCAPI BASKET CREATED: {checkout_id} ***\n")
                
                # 2. Add item to basket
                logger.info(f"Adding item {product_id} to SCAPI basket {checkout_id}")
                success = self._scapi_client.add_item_to_basket(checkout_id, product_id, quantity)
                if not success:
                    raise ValueError(f"Failed to add item to SCAPI basket {checkout_id}")
            except Exception as e:
                logger.error(f"SCAPI checkout action failed: {e}")
                # Don't fall back to local UUID if we meant to use SCAPI, 
                # keep it as None so we can either fail or re-create
                if not checkout_id:
                    checkout_id = str(uuid4())

        if not checkout_id:
            checkout_id = str(uuid4())
            checkout_type = get_checkout_type(metadata)
            checkout = checkout_type(
                id=checkout_id,
                ucp=metadata,
                line_items=[],
                currency=DEFAULT_CURRENCY,
                totals=[],
                status="incomplete",
                links=[],
                payment=PaymentResponse(
                    handlers=self._ucp_metadata["payment"]["handlers"]
                ),
            )
        else:
            checkout = self._checkouts.get(checkout_id)
            if not checkout:
                # If it's a SCAPI basket but not in local cache, create it
                checkout_type = get_checkout_type(metadata)
                checkout = checkout_type(
                    id=checkout_id,
                    ucp=metadata,
                    line_items=[],
                    currency=DEFAULT_CURRENCY,
                    totals=[],
                    status="incomplete",
                    links=[],
                    payment=PaymentResponse(
                        handlers=self._ucp_metadata["payment"]["handlers"]
                    ),
                )

        found = False
        for line_item in checkout.line_items:
            if line_item.item.id == product_id:
                line_item.quantity += quantity
                found = True
                break
        if not found:
            order_item = self._get_line_item(product, quantity)
            checkout.line_items.append(order_item)

        self._recalculate_checkout(checkout)
        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)

        return checkout

    def apply_discount(
        self, checkout_id: str, coupon_code: str
    ) -> Checkout:
        """Apply a discount/coupon code to the checkout.

        This method applies the coupon via SCAPI, extracts the actual discount
        from priceAdjustments, and syncs totals into UCP checkout.

        Args:
            checkout_id (str): ID of the checkout (SCAPI basket ID).
            coupon_code (str): The coupon/promo code to apply.

        Returns:
            Checkout: The updated checkout with discount info and synced totals.

        """
        checkout = self.get_checkout(checkout_id)
        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        basket_data = None
        discount_amount = 0
        discount_title = f"Coupon: {coupon_code}"

        # Step 1: Apply coupon to SCAPI basket and get updated basket data
        if self._use_scapi and self._scapi_client:
            try:
                logger.info(f"Applying coupon '{coupon_code}' to SCAPI basket {checkout_id}")
                basket_data = self._scapi_client.add_coupon_to_basket(
                    checkout_id, coupon_code
                )

                if basket_data:
                    # Extract discount from priceAdjustments (NOT productSubTotal - productTotal)
                    # SCAPI's productSubTotal and productTotal are both post-discount values
                    discount_amount, discount_title = self._extract_discount_from_basket(
                        basket_data, coupon_code
                    )
                    logger.info(
                        f"SCAPI discount extracted: {discount_title}, "
                        f"amount=${discount_amount/100:.2f}"
                    )
            except Exception as e:
                logger.error(f"SCAPI coupon application failed: {e}")

        # Step 2: Update UCP checkout state with actual discount
        applied_discount = AppliedDiscount(
            code=coupon_code,
            title=discount_title,
            amount=discount_amount,  # Real amount from SCAPI (cents)
            automatic=False,
        )

        checkout.discounts = DiscountsObject(
            codes=[coupon_code],
            applied=[applied_discount] if basket_data else [],
        )

        # Step 3: Sync SCAPI totals into UCP checkout
        if basket_data:
            self._sync_scapi_totals(checkout, basket_data)

        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)

        logger.info(
            f"UCP checkout updated with discount: code={coupon_code}, "
            f"discount_amount=${discount_amount/100:.2f}"
        )
        return checkout

    def _extract_discount_from_basket(
        self, basket_data: dict, coupon_code: str
    ) -> tuple[int, str]:
        """Extract the total discount amount and title from SCAPI priceAdjustments.

        SCAPI stores discounts on individual productItems as priceAdjustments.
        Each adjustment has a negative 'price' field representing the discount.

        Args:
            basket_data: SCAPI basket response dict.
            coupon_code: The coupon code to look for.

        Returns:
            (discount_cents, discount_title): Total discount in cents and its title.
        """
        total_discount = 0
        title = f"Coupon: {coupon_code}"

        for item in basket_data.get("productItems") or []:
            for adj in item.get("priceAdjustments") or []:
                if adj.get("couponCode") == coupon_code:
                    # priceAdjustments[].price is negative (e.g. -625.00)
                    adj_price = adj.get("price") or 0
                    total_discount += abs(adj_price)
                    # Use the promotion text as the discount title
                    if adj.get("itemText"):
                        title = adj["itemText"]

        discount_cents = round(total_discount * 100)
        logger.info(
            f"Extracted discount from priceAdjustments: "
            f"${total_discount:.2f} ({title})"
        )
        return discount_cents, title

    def _sync_scapi_totals(self, checkout: Checkout, basket_data: dict) -> None:
        """Sync SCAPI basket totals into UCP checkout totals.

        Reads the SCAPI basket response and updates the checkout's totals
        and line item totals to reflect SCAPI's calculated prices.
        Uses priceAdjustments for discount info and computes orderTotal
        when SCAPI returns null (before shipping is set).

        Args:
            checkout: The UCP checkout object to update.
            basket_data: The SCAPI basket response dict.
        """
        # Use 'or 0' because SCAPI may return explicit None values
        product_total = basket_data.get("productTotal") or 0
        shipping_total = basket_data.get("shippingTotal") or 0
        tax_total = basket_data.get("taxTotal") or 0
        order_total = basket_data.get("orderTotal")
        adjusted_tax = basket_data.get("adjustedMerchandizeTotalTax") or 0

        # Extract discount from priceAdjustments (authoritative source)
        total_discount = 0
        original_subtotal = 0
        for item in basket_data.get("productItems") or []:
            base_price = (item.get("basePrice") or 0)
            qty = item.get("quantity") or 1
            original_subtotal += base_price * qty
            for adj in item.get("priceAdjustments") or []:
                adj_price = adj.get("price") or 0
                total_discount += abs(adj_price)

        # Convert to cents (SCAPI returns dollars, UCP uses cents)
        original_subtotal_cents = round(original_subtotal * 100)
        discount_cents = round(total_discount * 100)
        discounted_subtotal_cents = round(product_total * 100)
        shipping_cents = round(shipping_total * 100)

        # For tax: use adjustedMerchandizeTotalTax if taxTotal is null (pre-shipping)
        # taxTotal includes shipping tax, adjustedMerchandizeTotalTax is product tax only
        if tax_total > 0:
            tax_cents = round(tax_total * 100)
        elif adjusted_tax > 0:
            tax_cents = round(adjusted_tax * 100)
        else:
            tax_cents = 0

        # Compute order total: use SCAPI's orderTotal if available,
        # otherwise calculate from components
        if order_total is not None and order_total > 0:
            order_total_cents = round(order_total * 100)
        else:
            order_total_cents = discounted_subtotal_cents + shipping_cents + tax_cents

        # Update line item totals with original price and discount
        for scapi_item in basket_data.get("productItems") or []:
            scapi_product_id = scapi_item.get("productId", "")
            base_price = round((scapi_item.get("basePrice") or 0) * 100)
            qty = scapi_item.get("quantity") or 1
            item_original = base_price * qty
            item_after_discount = round((scapi_item.get("priceAfterItemDiscount") or 0) * 100)

            # Sum up priceAdjustments for this item
            item_discount = 0
            for adj in scapi_item.get("priceAdjustments") or []:
                item_discount += abs(round((adj.get("price") or 0) * 100))

            for line_item in checkout.line_items:
                if line_item.item.id == scapi_product_id:
                    # Keep the original price on the line item for display
                    line_item.item.price = base_price
                    line_item.totals = [
                        Total(
                            type="subtotal",
                            display_text="Subtotal",
                            amount=item_original,
                        ),
                        Total(
                            type="items_discount",
                            display_text="Discount",
                            amount=item_discount,
                        ),
                        Total(
                            type="total",
                            display_text="Total",
                            amount=item_after_discount,
                        ),
                    ]
                    break

        # Build checkout-level totals
        totals = [
            Total(
                type="subtotal",
                display_text="Subtotal",
                amount=original_subtotal_cents,
            ),
        ]

        if discount_cents > 0:
            totals.append(
                Total(
                    type="discount",
                    display_text="Discount",
                    amount=discount_cents,
                )
            )

        if shipping_cents > 0:
            totals.append(
                Total(type="fulfillment", display_text="Shipping", amount=shipping_cents)
            )
        if tax_cents > 0:
            totals.append(
                Total(type="tax", display_text="Tax", amount=tax_cents)
            )

        totals.append(
            Total(type="total", display_text="Total", amount=order_total_cents)
        )

        checkout.totals = totals
        logger.info(
            f"Synced SCAPI totals: original=${original_subtotal:.2f}, "
            f"discount=${total_discount:.2f}, subtotal=${product_total:.2f}, "
            f"shipping=${shipping_total:.2f}, tax=${tax_cents/100:.2f}, "
            f"total=${order_total_cents/100:.2f}"
        )

    def get_checkout(self, checkout_id: str) -> Optional[Checkout]:
        """Retrieve a checkout from the store.

        Args:
            checkout_id (str): ID of the checkout to retrieve.

        Returns:
            Optional[Checkout]: The Checkout object if found, else None.

        """
        checkout = self._checkouts.get(checkout_id)
        if not checkout:
            checkout = self._load_checkout_from_db(checkout_id)
            if checkout:
                self._checkouts[checkout_id] = checkout
        return checkout

    def remove_from_checkout(
        self, checkout_id: str, product_id: str
    ) -> Checkout:
        """Remove a product from the checkout.

        Args:
            checkout_id (str): ID of the checkout to remove from
            product_id (str): Product ID of the product to remove from checkout

        Returns:
            Checkout: checkout object

        """
        checkout = self.get_checkout(checkout_id)

        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        for line_item in checkout.line_items:
            if line_item.item.id == product_id:
                checkout.line_items.remove(line_item)
                break

        self._recalculate_checkout(checkout)
        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)
        return checkout

    def update_checkout(
        self, checkout_id: str, product_id: str, quantity: int
    ) -> Checkout:
        """Update the quantity of a product in the checkout.

        Args:
            checkout_id (str): ID of the checkout to update
            product_id (str): ID of the product to update
            quantity (int): New quantity of the product

        Returns:
            Checkout: checkout object

        """
        checkout = self.get_checkout(checkout_id)

        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        for line_item in checkout.line_items:
            if line_item.item.id == product_id:
                line_item.quantity = quantity
                break

        self._recalculate_checkout(checkout)
        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)
        return checkout

    def _recalculate_checkout(self, checkout: Checkout) -> None:
        """Recalculate the checkout totals.

        Args:
            checkout: The checkout object to recalculate.

        """
        # reset the checkout status
        checkout.status = "incomplete"

        # When SCAPI is active and discounts exist, re-fetch basket from SCAPI
        # to get the latest totals (shipping, tax may have been updated)
        if (
            self._use_scapi
            and self._scapi_client
            and hasattr(checkout, 'discounts')
            and checkout.discounts
            and checkout.discounts.applied
        ):
            try:
                basket_data = self._scapi_client.get_basket(checkout.id)
                if basket_data:
                    self._sync_scapi_totals(checkout, basket_data)
                    checkout.continue_url = AnyUrl(
                        f"https://example.com/checkout?id={checkout.id}"
                    )
                    return
            except Exception as e:
                logger.error(f"Failed to re-fetch SCAPI basket for totals: {e}")
            # Fall through to local recalculation if SCAPI fetch fails
            checkout.continue_url = AnyUrl(
                f"https://example.com/checkout?id={checkout.id}"
            )
            return

        items_base_amount = 0
        items_discount = 0

        for line_item in checkout.line_items:
            item = line_item.item
            unit_price = item.price
            base_amount = unit_price * line_item.quantity
            discount = 0
            line_item.totals = [
                Total(
                    type="items_discount",
                    display_text="Items Discount",
                    amount=discount,
                ),
                Total(
                    type="subtotal",
                    display_text="Subtotal",
                    amount=base_amount - discount,
                ),
                Total(
                    type="total",
                    display_text="Total",
                    amount=base_amount - discount,
                ),
            ]

            items_base_amount += base_amount
            items_discount += discount

        subtotal = items_base_amount - items_discount
        discount = 0

        totals = [
            Total(
                type="items_discount",
                display_text="Items Discount",
                amount=items_discount,
            ),
            Total(
                type="subtotal",
                display_text="Subtotal",
                amount=items_base_amount - items_discount,
            ),
            Total(type="discount", display_text="Discount", amount=discount),
        ]

        final_total = subtotal - discount

        if isinstance(checkout, FulfillmentCheckout) and checkout.fulfillment:
            # add taxes and shipping if checkout has fulfillment address
            tax = round(subtotal * 0.1)  # assume 10% flat tax
            selected_fulfillment_option = None

            # Find selected option in the fulfillment structure
            if checkout.fulfillment.root.methods:
                for method in checkout.fulfillment.root.methods:
                    if method.groups:
                        for group in method.groups:
                            if group.selected_option_id:
                                for option in group.options or []:
                                    if option.id == group.selected_option_id:
                                        selected_fulfillment_option = option
                                        break

            if selected_fulfillment_option:
                shipping = 0
                for total in selected_fulfillment_option.totals:
                    if total.type == "total":
                        shipping = total.amount
                        break
                totals.append(
                    Total(
                        type="fulfillment",
                        display_text="Shipping",
                        amount=shipping,
                    )
                )
                totals.append(Total(type="tax", display_text="Tax", amount=tax))
                final_total += shipping + tax

        totals.append(
            Total(type="total", display_text="Total", amount=final_total)
        )
        checkout.totals = totals
        checkout.continue_url = AnyUrl(
            f"https://example.com/checkout?id={checkout.id}"
        )

    def add_delivery_address(
        self, checkout_id: str, address: PostalAddress
    ) -> Checkout:
        """Add a delivery address to the checkout.

        Args:
            checkout_id (str): ID of the checkout to update.
            address: The delivery address.

        Returns:
            Checkout: The updated checkout object.

        """
        checkout = self.get_checkout(checkout_id)
        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        if isinstance(checkout, FulfillmentCheckout):
            dest_id = f"dest_{uuid4().hex[:8]}"
            destination = FulfillmentDestinationResponse(
                root=ShippingDestinationResponse(
                    id=dest_id, **address.model_dump()
                )
            )

            # If using SCAPI, sync address/customer
        # If using SCAPI, sync address/customer
        if self._use_scapi and self._scapi_client:
            try:
                logger.info(f"Syncing customer/address for basket {checkout_id} to SCAPI (Sync)")
                
                # Map UCP address to SCAPI format with ISO codes
                scapi_address = {
                    "firstName": address.first_name,
                    "lastName": address.last_name,
                    "address1": address.street_address,
                    "city": address.address_locality,
                    "postalCode": address.postal_code,
                    "stateCode": get_state_code(address.address_region),
                    "countryCode": get_country_code(address.address_country)
                }
                
                # 1. Add Billing Address
                self._scapi_client.add_billing_address(checkout_id, scapi_address)
                
                # 2. Update Shipment
                self._scapi_client.update_shipment(checkout_id, scapi_address, "001")

            except Exception as e:
                logger.error(f"SCAPI address sync failed: {e}")

            fulfillment_options = self._get_fulfillment_options()
            selected_option_id = fulfillment_options[0].id

            line_item_ids = [li.item.id for li in checkout.line_items]

            group = FulfillmentGroupResponse(
                id=f"package_{uuid4().hex[:8]}",
                line_item_ids=line_item_ids,
                options=fulfillment_options,
                selected_option_id=selected_option_id,
            )

            method = FulfillmentMethodResponse(
                id=f"method_{uuid4().hex[:8]}",
                type="shipping",
                line_item_ids=line_item_ids,
                destinations=[destination],
                selected_destination_id=dest_id,
                groups=[group],
            )

            checkout.fulfillment = Fulfillment(
                root=FulfillmentResponse(methods=[method])
            )

        self._recalculate_checkout(checkout)
        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)
        return checkout

    def start_payment(self, checkout_id: str) -> Checkout | str:
        """Start the payment process for the checkout.

        Args:
            checkout_id (str): ID of the checkout to start.

        Returns:
            Checkout | str: The updated checkout object or error message.

        """
        checkout = self.get_checkout(checkout_id)
        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        if checkout.status == "ready_for_complete":
            return checkout

        messages = []
        if checkout.buyer is None:
            messages.append("Provide a buyer email address")

        if (
            isinstance(checkout, FulfillmentCheckout)
            and checkout.fulfillment is None
        ):
            messages.append("Provide a fulfillment address")

        if messages:
            return "\n".join(messages)

        self._recalculate_checkout(checkout)
        checkout.status = "ready_for_complete"
        self._checkouts[checkout_id] = checkout
        self._save_checkout_to_db(checkout)
        return checkout

    def place_order(self, checkout_id: str) -> Checkout:
        """Place an order.

        Args:
            checkout_id (str): ID of the checkout to place the order for.

        Returns:
            Checkout: The Checkout object with order confirmation.

        """
        checkout = self.get_checkout(checkout_id)
        if checkout is None:
            raise ValueError(f"Checkout with ID {checkout_id} not found")

        order_id = f"ORD-{checkout_id}"

        # Use SCAPI if available
        if self._use_scapi and self._scapi_client:
            try:
                # UCP Traceability: The checkout_id here is actually the SCAPI basketId 
                # which was stored in the ucp_sdk.CheckoutResponse object during initialization.
                logger.info(f"Finalizing order for basket {checkout_id} in SCAPI (Sync)")
                
                # 1. Add Customer Email (SCAPI API handled via UCP context)
                email = checkout.buyer.email if checkout.buyer and checkout.buyer.email else "customer@example.com"
                self._scapi_client.add_customer(checkout_id, email)

                # 2. Apply any pending coupons that were added via apply_discount()
                # UCP: Coupons are already applied via the apply_discount tool,
                # no hardcoded coupon here — it's user-driven via the agent

                # 3. Add Payment Instrument (SCAPI API)
                self._scapi_client.add_payment_instrument(checkout_id)

                # 4. Sync final SCAPI basket totals into UCP checkout  
                # This ensures the order amount matches Salesforce's calculations
                # (with discounts, shipping, tax all applied server-side)
                basket_data = self._scapi_client.get_basket(checkout_id)
                if basket_data:
                    self._sync_scapi_totals(checkout, basket_data)
                    logger.info(f"Final basket totals synced from SCAPI: ${basket_data.get('orderTotal', 0)}")
                
                # 5. Create Order (SCAPI API)
                scapi_order_no = self._scapi_client.create_order(checkout_id)

                if scapi_order_no:
                    # UCP Traceability: We map the SCAPI 'order_no' to the UCP Order ID.
                    order_id = scapi_order_no
                    logger.info(f"SCAPI Order created: {order_id}")
                    print(f"\n\n*** SCAPI ORDER PLACED: {order_id} ***\n\n")
                else:
                    logger.warning("SCAPI Order creation failed, falling back to local ID")
            except Exception as e:
                logger.error(f"SCAPI order placement failed: {e}")

        checkout.status = "completed"
        checkout.order = OrderConfirmation(
            id=order_id,
            permalink_url=f"https://example.com/order?id={order_id}",
        )

        self._orders[order_id] = checkout
        self._save_order_to_db(order_id, checkout)
        # Clear the checkout after placing the order
        del self._checkouts[checkout_id]
        if self._db_client:
            try:
                self._db_client.execute("DELETE FROM agent_checkouts WHERE id = ?", (checkout_id,))
            except Exception as e:
                logger.error(f"Failed to delete checkout from Turso: {e}")
        return checkout

    def _get_fulfillment_options(self) -> list[FulfillmentOptionResponse]:
        """Return a list of available fulfillment options.

        Returns:
            list[FulfillmentOptionResponse]: Available fulfillment options.

        """
        return [
            FulfillmentOptionResponse(
                id="standard",
                title="Standard Shipping",
                description="Arrives in 4-5 days",
                carrier="USPS",
                totals=[
                    Total(type="subtotal", display_text="Subtotal", amount=500),
                    Total(type="tax", display_text="Tax", amount=0),
                    Total(type="total", display_text="Total", amount=500),
                ],
            ),
            FulfillmentOptionResponse(
                id="express",
                title="Express Shipping",
                description="Arrives in 1-2 days",
                carrier="FedEx",
                totals=[
                    Total(
                        type="subtotal",
                        display_text="Subtotal",
                        amount=1000,
                    ),
                    Total(type="tax", display_text="Tax", amount=0),
                    Total(type="total", display_text="Total", amount=1000),
                ],
            ),
        ]

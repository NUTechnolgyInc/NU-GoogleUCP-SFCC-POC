"""Salesforce Commerce Cloud SCAPI Sync Client.

Synchronous client for interacting with Salesforce Commerce Cloud SCAPI endpoints
including authentication, product search, basket management, and order processing.
"""

import base64
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import httpx
from .config import SCAPIConfig
from .models import (
    SCAPIProductSearchResponse,
    SCAPIProductSearchHit,
    SCAPIAddress,
    SCAPIBasketItem,
    SCAPIShipmentUpdate,
    SCAPIShippingAddress,
    SCAPIShippingMethod,
    SCAPIPaymentInstrument,
    SCAPIPaymentCard,
    SCAPICustomer,
    SCAPIOrderRequest,
    SCAPICoupon,
    SCAPICustomerAddress,
    SCAPICustomerProfile,
    map_scapi_product_to_ucp,
)

logger = logging.getLogger(__name__)


class SalesforceSyncClient:
    """Synchronous client for Salesforce Commerce Cloud SCAPI."""

    def __init__(self, config: Optional[SCAPIConfig] = None):
        """Initialize the SCAPI client.

        Args:
            config: SCAPI configuration. If not provided, loads from environment.
        """
        self.config = config or SCAPIConfig.from_env()
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        self._client = httpx.Client(timeout=30.0)
        # Passwordless auth state
        self._passwordless_access_token: Optional[str] = None
        self._passwordless_token_expires_at: Optional[datetime] = None
        self._passwordless_customer_id: Optional[str] = None
        self._passwordless_refresh_token: Optional[str] = None
        self._passwordless_usid: Optional[str] = None

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _get_basic_auth_header(self) -> str:
        """Generate Basic auth header for OAuth2 token request."""
        credentials = f"{self.config.client_id}:{self.config.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self._access_token or not self._token_expires_at:
            return True
        return datetime.now() >= (self._token_expires_at - timedelta(seconds=60))

    def _is_passwordless_token_expired(self) -> bool:
        """Check if the passwordless access token is expired."""
        if not self._passwordless_access_token or not self._passwordless_token_expires_at:
            return True
        return datetime.now() >= (self._passwordless_token_expires_at - timedelta(seconds=60))

    @property
    def is_authenticated(self) -> bool:
        """Check if a passwordless (registered user) token is active."""
        return not self._is_passwordless_token_expired()

    @property
    def customer_id(self) -> Optional[str]:
        """Get the authenticated customer's ID."""
        return self._passwordless_customer_id

    def _get_access_token(self) -> str:
        """Get a valid access token.

        Prefers passwordless token (registered user) over guest token.
        Falls back to client_credentials (guest) if no passwordless token.
        """
        # Prefer passwordless token if available and not expired
        if not self._is_passwordless_token_expired():
            logger.debug("Using passwordless access token (registered user)")
            return self._passwordless_access_token

        # Fallback to guest token
        if not self._is_token_expired():
            return self._access_token

        logger.info("Requesting new SLAS guest access token (Sync)...")

        headers = {
            "Authorization": self._get_basic_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        data = {
            "grant_type": "client_credentials",
            "channel_id": self.config.channel_id,
        }

        response = self._client.post(self.config.auth_url, headers=headers, data=data)
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 1800)
        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

        logger.info("Successfully obtained guest access token (Sync)")
        return self._access_token

    def _get_auth_headers(self, token: str) -> Dict[str, str]:
        """Get standard headers for SCAPI requests."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def search_products(self, query: str, count: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Search for products using SCAPI product search."""
        try:
            token = self._get_access_token()
            url = self.config.product_search_url()

            params = {
                "siteId": self.config.site_id,
                "q": query,
                "limit": count,
                "offset": offset
            }

            response = self._client.get(
                url,
                headers=self._get_auth_headers(token),
                params=params,
            )
            response.raise_for_status()

            data = response.json()
            search_response = SCAPIProductSearchResponse(**data)

            ucp_products = []
            for hit in search_response.hits:
                ucp_product = map_scapi_product_to_ucp(hit)
                ucp_products.append(ucp_product)

            return ucp_products

        except Exception as e:
            logger.error(f"Product search failed: {e}")
            return []

    def get_product(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific product by ID."""
        products = self.search_products(product_id, count=1)
        if products:
            return products[0]
        return None

    def create_basket(self) -> Optional[str]:
        """Create a new shopping basket."""
        try:
            token = self._get_access_token()
            url = self.config.create_basket_url()

            response = self._client.post(
                url,
                headers=self._get_auth_headers(token),
                json={},
            )
            response.raise_for_status()

            data = response.json()
            basket_id = data.get("basketId")
            logger.info(f"SCAPI Basket created: {basket_id}")
            return basket_id

        except Exception as e:
            logger.error(f"Failed to create basket: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def add_item_to_basket(self, basket_id: str, product_id: str, quantity: int = 1) -> bool:
        """Add an item to a basket."""
        try:
            token = self._get_access_token()
            url = self.config.basket_items_url(basket_id)

            item = SCAPIBasketItem(product_id=product_id, quantity=quantity)

            response = self._client.post(
                url,
                headers=self._get_auth_headers(token),
                json=[item.model_dump(by_alias=True)],
            )
            response.raise_for_status()
            logger.info(f"Added item {product_id} to basket {basket_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add item to basket: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def add_billing_address(self, basket_id: str, address: Dict[str, str]) -> bool:
        """Add billing address to basket."""
        try:
            token = self._get_access_token()
            url = self.config.basket_billing_url(basket_id)

            response = self._client.put(
                url,
                headers=self._get_auth_headers(token),
                json=address,
            )
            response.raise_for_status()
            logger.info(f"Added billing address to basket {basket_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add billing address: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def add_customer(self, basket_id: str, email: str) -> bool:
        """Add customer email to basket."""
        try:
            token = self._get_access_token()
            url = self.config.basket_customer_url(basket_id)

            customer = SCAPICustomer(email=email)

            response = self._client.put(
                url,
                headers=self._get_auth_headers(token),
                json=customer.model_dump(),
            )
            response.raise_for_status()
            logger.info(f"Added customer {email} to basket {basket_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add customer: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def update_shipment(self, basket_id: str, shipping_address: Dict[str, str], shipping_method_id: str = "001") -> bool:
        """Update shipment with shipping address and method."""
        try:
            token = self._get_access_token()
            url = self.config.basket_shipment_url(basket_id)

            shipment_update = SCAPIShipmentUpdate(
                shipping_address=SCAPIShippingAddress(**shipping_address),
                shipping_method=SCAPIShippingMethod(id=shipping_method_id),
            )

            response = self._client.patch(
                url,
                headers=self._get_auth_headers(token),
                json=shipment_update.model_dump(by_alias=True),
            )
            response.raise_for_status()
            logger.info(f"Updated shipment for basket {basket_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update shipment: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def add_payment_instrument(self, basket_id: str, payment_method_id: str = "CREDIT_CARD", card_type: str = "Visa") -> bool:
        """Add payment instrument to basket."""
        try:
            token = self._get_access_token()
            url = self.config.basket_payment_url(basket_id)

            payment = SCAPIPaymentInstrument(
                payment_method_id=payment_method_id,
                payment_card=SCAPIPaymentCard(card_type=card_type),
            )

            response = self._client.post(
                url,
                headers=self._get_auth_headers(token),
                json=payment.model_dump(by_alias=True),
            )
            response.raise_for_status()
            logger.info(f"Added payment instrument to basket {basket_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to add payment instrument: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def get_basket(self, basket_id: str) -> Optional[Dict]:
        """Get basket details including totals and applied discounts.

        Args:
            basket_id: The basket ID to fetch.

        Returns:
            Dict with basket data including orderTotal, productSubTotal, etc.
            None if the request fails.
        """
        try:
            token = self._get_access_token()
            url = self.config.basket_url(basket_id)

            response = self._client.get(
                url,
                headers=self._get_auth_headers(token),
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Fetched basket {basket_id}: total={data.get('orderTotal')}")
            return data

        except Exception as e:
            logger.error(f"Failed to get basket {basket_id}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def add_coupon_to_basket(self, basket_id: str, coupon_code: str) -> Optional[Dict]:
        """Add a coupon to a basket.

        Returns the full basket response dict with updated totals/discounts,
        or None if the request fails.
        """
        try:
            token = self._get_access_token()
            url = self.config.basket_coupons_url(basket_id)

            coupon = SCAPICoupon(code=coupon_code)

            response = self._client.post(
                url,
                headers=self._get_auth_headers(token),
                json=coupon.model_dump(),
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                f"Applied coupon {coupon_code} to basket {basket_id}. "
                f"New total: {data.get('orderTotal')}"
            )
            return data

        except Exception as e:
            logger.error(f"Failed to apply coupon {coupon_code}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def create_order(self, basket_id: str) -> Optional[str]:
        """Create an order from a basket."""
        try:
            token = self._get_access_token()
            url = self.config.create_order_url()

            order_request = SCAPIOrderRequest(basket_id=basket_id)

            response = self._client.post(
                url,
                headers=self._get_auth_headers(token),
                json=order_request.model_dump(by_alias=True),
            )
            if response.status_code >= 400:
                logger.error(f"Order creation failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
            
            response.raise_for_status()

            data = response.json()
            order_no = data.get("orderNo")
            logger.info(f"SCAPI Order created: {order_no}")
            return order_no

        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None
    def get_order(self, order_no: str) -> Optional[Dict[str, Any]]:
        """Get order details by order number."""
        try:
            token = self._get_access_token()
            url = self.config.order_url(order_no)

            response = self._client.get(
                url,
                headers=self._get_auth_headers(token),
            )
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Failed to retrieve order {order_no}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    # ── Passwordless Authentication ─────────────────────────────────────

    def request_passwordless_login(
        self,
        user_id: str,
        mode: str = "email",
        locale: str = "en-us",
    ) -> bool:
        """Request passwordless OTP login — sends a 6-digit code to the user's email.

        Args:
            user_id: The registered customer's email/login.
            mode: Delivery mode for the OTP (default: "email").
            locale: Locale for the email content (default: "en-us").

        Returns:
            True if OTP was sent successfully, False otherwise.
        """
        try:
            headers = {
                "Authorization": self._get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "channel_id": self.config.channel_id,
                "user_id": user_id,
                "mode": mode,
                "locale": locale,
            }

            response = self._client.post(
                self.config.passwordless_login_url,
                headers=headers,
                data=data,
            )
            response.raise_for_status()

            logger.info(f"Passwordless OTP sent to {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to request passwordless login: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return False

    def get_passwordless_token(self, pwdless_login_token: str) -> Optional[Dict[str, Any]]:
        """Exchange the 6-digit OTP for a passwordless access token.

        Args:
            pwdless_login_token: The 6-digit code the user received via email.

        Returns:
            Token response dict with access_token, customer_id, etc.
            None if the exchange fails.
        """
        try:
            headers = {
                "Authorization": self._get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            }

            data = {
                "grant_type": "client_credentials",
                "hint": "pwdless_login",
                "pwdless_login_token": pwdless_login_token,
            }

            response = self._client.post(
                self.config.passwordless_token_url,
                headers=headers,
                data=data,
            )
            response.raise_for_status()

            token_data = response.json()

            # Store passwordless token state
            self._passwordless_access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 1800)
            self._passwordless_token_expires_at = datetime.now() + timedelta(seconds=expires_in)
            self._passwordless_customer_id = token_data.get("customer_id")
            self._passwordless_refresh_token = token_data.get("refresh_token")
            self._passwordless_usid = token_data.get("usid")

            logger.info(
                f"Passwordless token obtained. customer_id={self._passwordless_customer_id}"
            )
            return token_data

        except Exception as e:
            logger.error(f"Failed to exchange passwordless OTP for token: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def clear_passwordless_session(self):
        """Clear passwordless auth state (logout)."""
        self._passwordless_access_token = None
        self._passwordless_token_expires_at = None
        self._passwordless_customer_id = None
        self._passwordless_refresh_token = None
        self._passwordless_usid = None
        logger.info("Passwordless session cleared")

    # ── Customer APIs ───────────────────────────────────────────────────

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer profile with all saved addresses.

        Args:
            customer_id: The customer ID from passwordless token response.

        Returns:
            Customer profile dict including 'addresses' list, or None.
        """
        try:
            token = self._get_access_token()
            url = self.config.get_customer_url(customer_id)

            response = self._client.get(
                url,
                headers=self._get_auth_headers(token),
            )
            response.raise_for_status()

            data = response.json()
            logger.info(
                f"Fetched customer {customer_id}: "
                f"{len(data.get('addresses', []))} addresses found"
            )
            return data

        except Exception as e:
            logger.error(f"Failed to fetch customer {customer_id}: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

    def get_customer_address(
        self, customer_id: str, address_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific customer address by addressId.

        Args:
            customer_id: The customer ID.
            address_id: The addressId label (e.g. 'Home Address').

        Returns:
            Address dict or None.
        """
        try:
            token = self._get_access_token()
            url = self.config.get_customer_address_url(customer_id, address_id)

            response = self._client.get(
                url,
                headers=self._get_auth_headers(token),
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Fetched address '{address_id}' for customer {customer_id}")
            return data

        except Exception as e:
            logger.error(f"Failed to fetch address '{address_id}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response body: {e.response.text}")
            return None

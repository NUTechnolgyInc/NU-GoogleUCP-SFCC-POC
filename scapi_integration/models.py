"""Data models for SCAPI integration."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SCAPIProduct(BaseModel):
    """SCAPI product model (from product search response)."""

    product_id: str = Field(alias="id")
    product_name: str = Field(alias="productName")
    price: Optional[float] = None
    currency: Optional[str] = None
    image_url: Optional[str] = None
    brand: Optional[str] = None

    class Config:
        populate_by_name = True


class SCAPIProductSearchHit(BaseModel):
    """Individual hit from SCAPI product search."""

    product_id: str = Field(alias="productId")
    product_name: str = Field(alias="productName")
    represented_product: Dict[str, Any] = Field(alias="representedProduct", default_factory=dict)
    price: Optional[float] = None
    currency: Optional[str] = None
    image: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class SCAPIProductSearchResponse(BaseModel):
    """SCAPI product search response."""

    hits: List[SCAPIProductSearchHit] = Field(default_factory=list)
    total: int = 0
    count: int = 0
    offset: int = 0

    class Config:
        populate_by_name = True


class SCAPIAddress(BaseModel):
    """SCAPI address model."""

    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    address1: str
    city: str
    postal_code: str = Field(alias="postalCode")
    state_code: str = Field(alias="stateCode")
    country_code: str = Field(alias="countryCode")

    class Config:
        populate_by_name = True


class SCAPIBasketItem(BaseModel):
    """SCAPI basket item."""

    product_id: str = Field(alias="productId")
    quantity: int = 1

    class Config:
        populate_by_name = True


class SCAPIShippingAddress(BaseModel):
    """SCAPI shipping address."""

    first_name: str = Field(alias="firstName")
    last_name: str = Field(alias="lastName")
    address1: str
    city: str
    postal_code: str = Field(alias="postalCode")
    state_code: str = Field(alias="stateCode")
    country_code: str = Field(alias="countryCode")

    class Config:
        populate_by_name = True


class SCAPIShippingMethod(BaseModel):
    """SCAPI shipping method."""

    id: str

    class Config:
        populate_by_name = True


class SCAPIShipmentUpdate(BaseModel):
    """SCAPI shipment update."""

    shipping_address: SCAPIShippingAddress = Field(alias="shippingAddress")
    shipping_method: SCAPIShippingMethod = Field(alias="shippingMethod")

    class Config:
        populate_by_name = True


class SCAPIPaymentCard(BaseModel):
    """SCAPI payment card."""

    card_type: str = Field(alias="cardType")

    class Config:
        populate_by_name = True


class SCAPIPaymentInstrument(BaseModel):
    """SCAPI payment instrument."""

    payment_method_id: str = Field(alias="paymentMethodId")
    payment_card: SCAPIPaymentCard = Field(alias="paymentCard")

    class Config:
        populate_by_name = True


class SCAPICustomer(BaseModel):
    """SCAPI customer."""

    email: str


class SCAPIOrderRequest(BaseModel):
    """SCAPI order creation request."""

    basket_id: str = Field(alias="basketId")

    class Config:
        populate_by_name = True


class SCAPICoupon(BaseModel):
    """SCAPI coupon model."""

    code: str

    class Config:
        populate_by_name = True


class SCAPICustomerAddress(BaseModel):
    """SCAPI customer saved address model."""

    address_id: str = Field(alias="addressId")
    address1: str = ""
    address2: Optional[str] = None
    city: str = ""
    state_code: str = Field(default="", alias="stateCode")
    postal_code: str = Field(default="", alias="postalCode")
    country_code: str = Field(default="US", alias="countryCode")
    first_name: str = Field(default="", alias="firstName")
    last_name: str = Field(default="", alias="lastName")
    full_name: Optional[str] = Field(default=None, alias="fullName")
    phone: Optional[str] = None
    company_name: Optional[str] = Field(default=None, alias="companyName")
    preferred: bool = False

    class Config:
        populate_by_name = True


class SCAPICustomerProfile(BaseModel):
    """SCAPI customer profile model."""

    customer_id: str = Field(alias="customerId")
    customer_no: Optional[str] = Field(default=None, alias="customerNo")
    email: Optional[str] = None
    login: Optional[str] = None
    first_name: Optional[str] = Field(default=None, alias="firstName")
    last_name: Optional[str] = Field(default=None, alias="lastName")
    auth_type: Optional[str] = Field(default=None, alias="authType")
    addresses: List[SCAPICustomerAddress] = Field(default_factory=list)

    class Config:
        populate_by_name = True


def map_scapi_product_to_ucp(scapi_hit: SCAPIProductSearchHit, base_url: str = "") -> Dict[str, Any]:
    """Map SCAPI product search hit to UCP Product format.

    Args:
        scapi_hit: SCAPI product search hit
        base_url: Base URL for constructing product URLs

    Returns:
        Dictionary in UCP Product schema.org format
    """
    # Extract variant product ID from representedProduct
    variant_id = scapi_hit.represented_product.get("id", scapi_hit.product_id)
    
    # Extract price information
    price = None
    currency = "USD"
    if scapi_hit.price is not None:
        price = str(scapi_hit.price)
    elif "pricePerUnit" in scapi_hit.represented_product:
        price = str(scapi_hit.represented_product["pricePerUnit"])
    
    # Extract image URL
    image_url = None
    if scapi_hit.image:
        if "link" in scapi_hit.image:
            image_url = scapi_hit.image["link"]
        elif "url" in scapi_hit.image:
            image_url = scapi_hit.image["url"]

    # Build UCP Product format
    return {
        "@type": "Product",
        "productID": variant_id,
        "name": scapi_hit.product_name,
        "sku": variant_id,
        "image": [image_url] if image_url else [],
        "brand": {
            "@type": "Brand",
            "name": scapi_hit.represented_product.get("brand", "Unknown")
        },
        "offers": {
            "@type": "Offer",
            "price": price or "0.00",
            "priceCurrency": currency,
            "availability": "https://schema.org/InStock",
            "itemCondition": "https://schema.org/NewCondition"
        },
        "url": f"{base_url}/product/{variant_id}" if base_url else "",
        "description": scapi_hit.product_name,
        "category": ""
    }


def get_state_code(state_name: str) -> str:
    """Map state names to 2-letter codes for SCAPI RefArch."""
    states = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
        "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
        "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
        "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY"
    }
    # Return as-is if already a 2-char code or not found
    if len(state_name) == 2:
        return state_name.upper()
    return states.get(state_name, state_name)


def get_country_code(country_name: str) -> str:
    """Map country names to 2-letter codes for SCAPI RefArch."""
    countries = {
        "United States": "US",
        "United States of America": "US",
        "USA": "US",
        "United Kingdom": "GB",
        "Great Britain": "GB",
        "UK": "GB",
        "Canada": "CA",
        "France": "FR",
        "Germany": "DE",
        "Italy": "IT",
        "Japan": "JP",
        "India": "IN",
        "Australia": "AU"
    }
    # Return as-is if already a 2-char code or not found
    if len(country_name) == 2:
        return country_name.upper()
    return countries.get(country_name, country_name)

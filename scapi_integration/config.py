"""Configuration management for Salesforce SCAPI."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class SCAPIConfig:
    """Configuration for Salesforce Commerce Cloud SCAPI."""

    host: str
    org_id: str
    client_id: str
    client_secret: str
    channel_id: str
    site_id: str

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "SCAPIConfig":
        """Load configuration from environment variables.

        Args:
            env_file: Optional path to .env file. If not provided, looks for
                     .env in the scapi_integration directory.

        Returns:
            SCAPIConfig instance with loaded configuration.

        Raises:
            ValueError: If required environment variables are missing.
        """
        # Load from .env file if it exists
        if env_file:
            load_dotenv(env_file)
        else:
            # Try to load from scapi_integration/.env
            base_path = Path(__file__).parent
            env_path = base_path / ".env"
            if env_path.exists():
                load_dotenv(env_path)

        # Get required configuration values
        host = os.getenv("SCAPI_HOST") or os.getenv("HOST")
        org_id = os.getenv("SCAPI_ORG_ID") or os.getenv("ORG_ID")
        client_id = os.getenv("SCAPI_CLIENT_ID") or os.getenv("CLIENT_ID")
        client_secret = os.getenv("SCAPI_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
        channel_id = os.getenv("SCAPI_CHANNEL_ID") or os.getenv("CHANNEL_ID")
        site_id = os.getenv("SCAPI_SITE_ID") or os.getenv("SITE_ID")

        # Validate required values
        missing = []
        if not host:
            missing.append("HOST")
        if not org_id:
            missing.append("ORG_ID")
        if not client_id:
            missing.append("CLIENT_ID")
        if not client_secret:
            missing.append("CLIENT_SECRET")
        if not channel_id:
            missing.append("CHANNEL_ID")
        if not site_id:
            missing.append("SITE_ID")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        return cls(
            host=host,
            org_id=org_id,
            client_id=client_id,
            client_secret=client_secret,
            channel_id=channel_id,
            site_id=site_id,
        )

    @property
    def auth_url(self) -> str:
        """Get the OAuth2 token URL."""
        return f"{self.host}/shopper/auth/v1/organizations/{self.org_id}/oauth2/token"

    def product_search_url(self) -> str:
        """Get the base product search URL."""
        return f"{self.host}/search/shopper-search/v1/organizations/{self.org_id}/product-search"

    def create_basket_url(self) -> str:
        """Get the create basket URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets"
            f"?siteId={self.site_id}"
        )

    def basket_url(self, basket_id: str) -> str:
        """Get the basket URL for a specific basket."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}"
            f"?siteId={self.site_id}"
        )

    def basket_items_url(self, basket_id: str) -> str:
        """Get the basket items URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/items"
            f"?siteId={self.site_id}"
        )

    def basket_billing_url(self, basket_id: str) -> str:
        """Get the basket billing address URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/billing-address"
            f"?siteId={self.site_id}"
        )

    def basket_customer_url(self, basket_id: str) -> str:
        """Get the basket customer URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/customer"
            f"?siteId={self.site_id}"
        )

    def basket_shipment_url(self, basket_id: str) -> str:
        """Get the basket shipment URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/shipments/me"
            f"?siteId={self.site_id}"
        )

    def basket_payment_url(self, basket_id: str) -> str:
        """Get the basket payment instruments URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/payment-instruments"
            f"?siteId={self.site_id}"
        )

    def basket_coupons_url(self, basket_id: str) -> str:
        """Get the basket coupons URL."""
        return (
            f"{self.host}/checkout/shopper-baskets/v1/organizations/{self.org_id}/baskets/{basket_id}/coupons"
            f"?siteId={self.site_id}"
        )

    def create_order_url(self) -> str:
        """Get the create order URL."""
        return (
            f"{self.host}/checkout/shopper-orders/v1/organizations/{self.org_id}/orders"
            f"?siteId={self.site_id}"
        )

    def order_url(self, order_no: str) -> str:
        """Get the order URL for a specific order."""
        return (
            f"{self.host}/checkout/shopper-orders/v1/organizations/{self.org_id}/orders/{order_no}"
            f"?siteId={self.site_id}"
        )

    @property
    def passwordless_login_url(self) -> str:
        """Get the passwordless login URL (sends OTP to user's email)."""
        return (
            f"{self.host}/shopper/auth/v1/organizations/{self.org_id}"
            f"/oauth2/passwordless/login?register_customer=true"
        )

    @property
    def passwordless_token_url(self) -> str:
        """Get the passwordless token URL (exchanges OTP for access token)."""
        return (
            f"{self.host}/shopper/auth/v1/organizations/{self.org_id}"
            f"/oauth2/passwordless/token"
        )

    def get_customer_url(self, customer_id: str) -> str:
        """Get the customer profile URL."""
        return (
            f"{self.host}/customer/shopper-customers/v1/organizations/{self.org_id}"
            f"/customers/{customer_id}?siteId={self.site_id}"
        )

    def get_customer_address_url(self, customer_id: str, address_id: str) -> str:
        """Get the customer address URL for a specific address."""
        return (
            f"{self.host}/customer/shopper-customers/v1/organizations/{self.org_id}"
            f"/customers/{customer_id}/addresses/{address_id}?siteId={self.site_id}"
        )

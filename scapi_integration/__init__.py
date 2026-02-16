"""Salesforce SCAPI Integration Package.

This package provides integration with Salesforce Commerce Cloud SCAPI
for product search, basket management, and order processing.
"""

from .scapi_sync_client import SalesforceSyncClient
from .config import SCAPIConfig
from .models import SCAPICustomerAddress, SCAPICustomerProfile

__all__ = [
    "SalesforceSyncClient",
    "SCAPIConfig",
    "SCAPICustomerAddress",
    "SCAPICustomerProfile",
]

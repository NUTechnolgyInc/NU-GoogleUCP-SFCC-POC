# Salesforce SCAPI Integration for UCP

This module provides integration between the Universal Commerce Protocol (UCP) and Salesforce Commerce Cloud SCAPI (Shopper API).

## Features

- **SLAS Authentication**: Automatic OAuth2 token management with refresh
- **Product Search**: Search products using SCAPI with UCP format mapping
- **Basket Management**: Create baskets and add items
- **Complete Checkout Flow**: Full e-commerce checkout from basket to order
- **Error Handling**: Robust error handling and logging
- **UCP Compatible**: Maps SCAPI responses to UCP Product schema

## Architecture

```
scapi_integration/
├── __init__.py          # Package exports
├── config.py            # Configuration management
├── models.py            # Data models and UCP mapping
├── scapi_client.py      # Main SCAPI client
├── test_scapi.py        # Integration tests
├── .env                 # Configuration (gitignored)
└── .env.example         # Example configuration
```

## Setup

### 1. Install Dependencies

The integration requires the following Python packages (already included in the UCP business agent):
- `httpx` - Async HTTP client
- `python-dotenv` - Environment variable management
- `pydantic` - Data validation

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your Salesforce Commerce Cloud credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```env
HOST=https://kv7kzm78.api.commercecloud.salesforce.com
ORG_ID=f_ecom_zypo_002
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
CHANNEL_ID=RefArch
SITE_ID=RefArch
```

## Usage

### Standalone Testing

Test the SCAPI integration independently:

```bash
cd samples/scapi_integration
python test_scapi.py
```

This will run three test scenarios:
1. **Authentication** - Verify SLAS token retrieval
2. **Product Search** - Search for products
3. **Full Checkout Flow** - Complete basket → order flow

### Integration with UCP Agent

The SCAPI client is integrated into the UCP business agent's `store.py`. When you run the UCP agent, it will automatically use SCAPI for product search instead of the static `products.json`.

```bash
cd samples/a2a/business_agent
export GOOGLE_API_KEY=your-key
uv run business_agent --host localhost --port 10999
```

## API Flow

### Authentication (SLAS Guest Private Client)

```
POST /shopper/auth/v1/organizations/{ORG_ID}/oauth2/token
Headers:
  Authorization: Basic {base64(CLIENT_ID:CLIENT_SECRET)}
  Content-Type: application/x-www-form-urlencoded
Body:
  grant_type=client_credentials&channel_id={CHANNEL_ID}

Response:
  {
    "access_token": "...",
    "expires_in": 1800
  }
```

### Product Search

```
GET /search/shopper-search/v1/organizations/{ORG_ID}/product-search
Query Params:
  siteId={SITE_ID}
  q={query}
  count=50
  offset=0
Headers:
  Authorization: Bearer {token}
  x-vc-site: {SITE_ID}

Response:
  {
    "hits": [
      {
        "productId": "...",
        "productName": "...",
        "representedProduct": {
          "id": "variant-id",
          "pricePerUnit": 29.99
        },
        "image": {...}
      }
    ],
    "total": 100
  }
```

### Checkout Flow

1. **Create Basket**: `POST /checkout/shopper-baskets/v1/organizations/{ORG_ID}/baskets`
2. **Add Item**: `POST /baskets/{basketId}/items`
3. **Add Billing**: `PUT /baskets/{basketId}/billing-address`
4. **Add Customer**: `PUT /baskets/{basketId}/customer`
5. **Update Shipment**: `PATCH /baskets/{basketId}/shipments/me`
6. **Add Payment**: `POST /baskets/{basketId}/payment-instruments`
7. **Create Order**: `POST /checkout/shopper-orders/v1/organizations/{ORG_ID}/orders`
8. **Get Order**: `GET /orders/{orderNo}`

## UCP Mapping

SCAPI product search results are automatically mapped to UCP Product schema:

```python
# SCAPI Format
{
  "productId": "12345M",
  "productName": "Blue Shirt",
  "representedProduct": {
    "id": "12345-S-BLUE",  # Variant ID
    "pricePerUnit": 29.99
  }
}

# UCP Format
{
  "@type": "Product",
  "productID": "12345-S-BLUE",  # Uses variant ID
  "name": "Blue Shirt",
  "offers": {
    "@type": "Offer",
    "price": "29.99",
    "priceCurrency": "USD"
  }
}
```

## Manual Testing with curl

### 1. Get Access Token

```bash
curl -X POST "https://kv7kzm78.api.commercecloud.salesforce.com/shopper/auth/v1/organizations/f_ecom_zypo_002/oauth2/token" \
  -H "Authorization: Basic $(echo -n '5183e119-364e-41e2-ae80-bd76190aef6d:cXUQNz6SkGJikc98njwhi9QvqQoEJf1jpie7t6Q8y6w' | base64)" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&channel_id=RefArch"
```

### 2. Search Products

```bash
# Replace {TOKEN} with the access_token from step 1
curl -X GET "https://kv7kzm78.api.commercecloud.salesforce.com/search/shopper-search/v1/organizations/f_ecom_zypo_002/product-search?siteId=RefArch&q=shirt&count=10" \
  -H "Authorization: Bearer {TOKEN}" \
  -H "x-vc-site: RefArch"
```

### 3. Create Basket

```bash
curl -X POST "https://kv7kzm78.api.commercecloud.salesforce.com/checkout/shopper-baskets/v1/organizations/f_ecom_zypo_002/baskets?siteId=RefArch" \
  -H "Authorization: Bearer {TOKEN}" \
  -H "x-vc-site: RefArch" \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Logging

The client uses Python's standard logging module. Configure logging level in your application:

```python
import logging
logging.basicConfig(level=logging.INFO)
```

Log output includes:
- Authentication token requests
- API calls with URLs and parameters
- Success/failure status
- Error messages with details

## Error Handling

The client implements:
- Automatic token refresh on expiration
- HTTP error catching and logging
- Graceful fallback to empty results on search failures
- Detailed error messages in logs

## Troubleshooting

### "Missing required environment variables"
- Ensure `.env` file exists in `scapi_integration/` directory
- Verify all required variables are set: HOST, ORG_ID, CLIENT_ID, CLIENT_SECRET, CHANNEL_ID, SITE_ID

### "Failed to obtain access token"
- Check CLIENT_ID and CLIENT_SECRET are correct
- Verify CHANNEL_ID matches your Commerce Cloud setup
- Check network connectivity to the HOST

### "No products found"
- Try different search queries
- Verify SITE_ID is correct
- Check product catalog is populated in Commerce Cloud

### "Failed to create basket/order"
- Ensure access token is valid
- Verify all required fields are provided
- Check Commerce Cloud site configuration

## Integration Points

The SCAPI client is used by:
- `store.py` - `search_products()` method calls `scapi_client.search_products()`
- `store.py` - `get_product()` method calls `scapi_client.get_product()`

Products are cached in-memory to reduce API calls during agent interactions.

## License

Apache 2.0 (same as UCP samples)

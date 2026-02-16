
import asyncio
import logging
import sys
from pathlib import Path
import httpx
from urllib.parse import quote

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scapi_integration import SalesforceClient, SCAPIConfig

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    config = SCAPIConfig.from_env()
    
    # 1. Test EXACTLY like Postman (supposedly)
    # URL: .../product-search?siteId=RefArch&q=white shirt
    # We will try to simulate this with params
    
    logger.info("--- TEST 1: Standard httpx params ---")
    async with SalesforceClient(config) as client:
        token = await client._get_access_token()
        base_url = config.product_search_url() # This is now just the base path
        
        params = {
            "siteId": "RefArch",
            "q": "white shirt",
            "limit": 50,
            "offset": 0
        }
        
        headers = client._get_auth_headers(token)
        
        try:
            r = await client._client.get(base_url, headers=headers, params=params)
            logger.info(f"URL: {r.url}")
            data = r.json()
            logger.info(f"Hits: {data.get('total', 'Unknown')}")
            
            # Print first hit name if any
            if data.get('hits'):
                print(f"First hit: {data['hits'][0]['productName']}")
                
        except Exception as e:
            logger.error(f"Error: {e}")

    # 2. Test without limit/offset (closer to Postman)
    logger.info("\n--- TEST 2: No limit/offset ---")
    async with SalesforceClient(config) as client:
        token = await client._get_access_token()
        params = {
            "siteId": "RefArch",
            "q": "white shirt"
        }
        headers = client._get_auth_headers(token)
        r = await client._client.get(base_url, headers=headers, params=params)
        logger.info(f"URL: {r.url}")
        logger.info(f"Hits: {r.json().get('total', 'Unknown')}")

    # 3. Test "shirt" only (known good)
    logger.info("\n--- TEST 3: 'shirt' only ---")
    async with SalesforceClient(config) as client:
        token = await client._get_access_token()
        params = {
            "siteId": "RefArch",
            "q": "shirt"
        }
        headers = client._get_auth_headers(token)
        r = await client._client.get(base_url, headers=headers, params=params)
        logger.info(f"URL: {r.url}")
        logger.info(f"Hits: {r.json().get('total', 'Unknown')}")


if __name__ == "__main__":
    asyncio.run(run_test())

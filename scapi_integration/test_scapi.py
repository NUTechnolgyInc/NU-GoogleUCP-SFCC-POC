"""Test script for SCAPI integration (Synchronous).

This script tests the Salesforce Commerce Cloud SCAPI integration
including authentication, product search, and full checkout flow.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scapi_integration import SalesforceSyncClient, SCAPIConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_authentication():
    """Test SLAS authentication flow."""
    logger.info("\n=== Testing Authentication ===")
    
    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            token = client._get_access_token()
            logger.info(f"✓ Successfully obtained access token")
            return True
    except Exception as e:
        logger.error(f"✗ Authentication failed: {e}")
        return False


def test_product_search():
    """Test product search."""
    logger.info("\n=== Testing Product Search ===")
    
    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            # Search for products
            products = client.search_products("shirt", count=5)
            
            if products:
                logger.info(f"✓ Found {len(products)} products")
                for i, product in enumerate(products[:3], 1):
                    logger.info(f"  {i}. {product['name']} - ID: {product['productID']} - Price: {product['offers']['price']}")
                return True, products
            else:
                logger.warning("✗ No products found")
                return False, []
    except Exception as e:
        logger.error(f"✗ Product search failed: {e}")
        return False, []


def test_full_checkout_flow():
    """Test complete checkout flow from basket to order."""
    logger.info("\n=== Testing Full Checkout Flow ===")
    
    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            # Step 1: Search for a product
            logger.info("Step 1: Searching for products...")
            products = client.search_products("shirt", count=1)
            
            if not products:
                logger.error("✗ No products found for checkout")
                return False
            
            product_id = products[0]["productID"]
            logger.info(f"✓ Selected product: {products[0]['name']} (ID: {product_id})")
            
            # Step 2: Create basket
            logger.info("Step 2: Creating basket...")
            basket_id = client.create_basket()
            
            if not basket_id:
                logger.error("✗ Failed to create basket")
                return False
            
            logger.info(f"✓ Created basket: {basket_id}")
            
            # Step 3: Add item to basket
            logger.info("Step 3: Adding item to basket...")
            success = client.add_item_to_basket(basket_id, product_id, quantity=1)
            
            if not success:
                logger.error("✗ Failed to add item to basket")
                return False
            
            logger.info("✓ Added item to basket")
            
            # Step 4: Add billing address
            logger.info("Step 4: Adding billing address...")
            billing_address = {
                "firstName": "Stephanie",
                "lastName": "Miller",
                "address1": "104 Presidential Way",
                "city": "Woburn",
                "postalCode": "01801",
                "stateCode": "MA",
                "countryCode": "US"
            }
            success = client.add_billing_address(basket_id, billing_address)
            
            if not success:
                logger.error("✗ Failed to add billing address")
                return False
            
            logger.info("✓ Added billing address")
            
            # Step 5: Add customer email
            logger.info("Step 5: Adding customer email...")
            success = client.add_customer(basket_id, "clavery@salesforce.com")
            
            if not success:
                logger.error("✗ Failed to add customer")
                return False
            
            logger.info("✓ Added customer email")
            
            # Step 6: Update shipment
            logger.info("Step 6: Updating shipment...")
            shipping_address = {
                "firstName": "Terrance",
                "lastName": "Grahn",
                "address1": "18911 marathon Rd",
                "city": "Austin",
                "postalCode": "78758",
                "stateCode": "TX",
                "countryCode": "US"
            }
            success = client.update_shipment(basket_id, shipping_address, "001")
            
            if not success:
                logger.error("✗ Failed to update shipment")
                return False
            
            logger.info("✓ Updated shipment")
            
            # Step 7.5: Apply Coupon
            logger.info("Step 7.5: Applying coupon...")
            # Note: This might fail if the coupon code is not valid in the sandbox, 
            # but we test the API connectivity here.
            success = client.add_coupon_to_basket(basket_id, "BIRTHDAY")
            
            if not success:
                logger.warning("! Coupon application failed (expected if code invalid), continuing checkout...")
            else:
                logger.info("✓ Applied coupon successfully")

            # Step 8: Add payment instrument
            success = client.add_payment_instrument(basket_id, "CREDIT_CARD", "Visa")
            
            if not success:
                logger.error("✗ Failed to add payment instrument")
                return False
            
            logger.info("✓ Added payment instrument")
            
            # Step 8: Create order
            logger.info("Step 8: Creating order...")
            order_no = client.create_order(basket_id)
            
            if not order_no:
                logger.error("✗ Failed to create order")
                return False
            
            logger.info(f"✓ Created order: {order_no}")
            
            # Step 9: Get order details
            logger.info("Step 9: Retrieving order details...")
            order = client.get_order(order_no)
            
            if not order:
                logger.error("✗ Failed to retrieve order")
                return False
            
            logger.info(f"✓ Retrieved order successfully")
            logger.info(f"   Order Number: {order.get('orderNo')}")
            logger.info(f"   Order Total: {order.get('orderTotal')}")
            
            return True
            
    except Exception as e:
        logger.error(f"✗ Checkout flow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    logger.info("Starting SCAPI Integration Tests (Sync)\n")
    
    results = []
    
    # Test 1: Authentication
    results.append(("Authentication", test_authentication()))
    
    # Test 2: Product Search
    search_result, products = test_product_search()
    results.append(("Product Search", search_result))
    
    # Test 3: Full Checkout Flow
    results.append(("Full Checkout Flow", test_full_checkout_flow()))
    
    # Summary
    logger.info("\n=== Test Summary ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"{test_name}: {status}")
    
    logger.info(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

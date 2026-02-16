"""Test script for SCAPI integration — Guest and Registered User flows.

Tests the complete checkout flows for both authentication modes:
- Guest: Uses client_credentials token (anonymous checkout)
- Registered: Uses passwordless OTP login (authenticated checkout)

Both flows go through product search, basket, address, payment, and order.

Usage:
    python test_guest_registered_flows.py
    python test_guest_registered_flows.py --mode guest
    python test_guest_registered_flows.py --mode registered --email vijey.anbarasan@nulogic.io
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scapi_integration import SalesforceSyncClient, SCAPIConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
#  GUEST USER FLOW
# ═══════════════════════════════════════════════════════════════════════


def test_guest_authentication():
    """Test guest authentication using client_credentials grant."""
    logger.info("\n=== [GUEST] Testing Authentication ===")

    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            # Guest auth: no passwordless token, uses client_credentials
            assert not client.is_authenticated, "Should NOT be authenticated as registered user"
            token = client._get_access_token()
            assert token is not None, "Guest token should not be None"
            logger.info("✓ Guest access token obtained (client_credentials grant)")
            return True
    except Exception as e:
        logger.error(f"✗ Guest authentication failed: {e}")
        return False


def test_guest_product_search():
    """Test product search as a guest user."""
    logger.info("\n=== [GUEST] Testing Product Search ===")

    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            products = client.search_products("shirt", count=5)

            if products:
                logger.info(f"✓ Found {len(products)} products")
                for i, product in enumerate(products[:3], 1):
                    logger.info(
                        f"  {i}. {product['name']} - "
                        f"ID: {product['productID']} - "
                        f"Price: {product['offers']['price']}"
                    )
                return True, products
            else:
                logger.warning("✗ No products found")
                return False, []
    except Exception as e:
        logger.error(f"✗ Product search failed: {e}")
        return False, []


def test_guest_full_checkout():
    """Test complete guest checkout flow: basket → address → payment → order."""
    logger.info("\n=== [GUEST] Testing Full Checkout Flow ===")

    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            # Verify we're in guest mode
            assert not client.is_authenticated
            logger.info("Auth mode: Guest (client_credentials)")

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

            # Step 4: Add billing address (manually provided — guest flow)
            logger.info("Step 4: Adding billing address (manual)...")
            billing_address = {
                "firstName": "Vijey",
                "lastName": "Anbarasan",
                "address1": "104 Presidential Way",
                "city": "Woburn",
                "postalCode": "01801",
                "stateCode": "CA",
                "countryCode": "US",
            }
            success = client.add_billing_address(basket_id, billing_address)
            if not success:
                logger.error("✗ Failed to add billing address")
                return False
            logger.info("✓ Added billing address")

            # Step 5: Add customer email
            logger.info("Step 5: Adding customer email...")
            success = client.add_customer(basket_id, "vijey.anbarasan@nulogic.io")
            if not success:
                logger.error("✗ Failed to add customer email")
                return False
            logger.info("✓ Added customer email")

            # Step 6: Update shipment (same address for shipping)
            logger.info("Step 6: Updating shipment...")
            shipping_address = {
                "firstName": "Vijey",
                "lastName": "Anbarasan",
                "address1": "104 Presidential Way",
                "city": "Woburn",
                "postalCode": "01801",
                "stateCode": "CA",
                "countryCode": "US",
            }
            success = client.update_shipment(basket_id, shipping_address, "001")
            if not success:
                logger.error("✗ Failed to update shipment")
                return False
            logger.info("✓ Updated shipment")

            # Step 7: Apply coupon (optional)
            logger.info("Step 7: Applying coupon...")
            success = client.add_coupon_to_basket(basket_id, "BIRTHDAY")
            if not success:
                logger.warning("! Coupon application failed (may be invalid), continuing...")
            else:
                logger.info("✓ Applied coupon successfully")

            # Step 8: Add payment instrument
            logger.info("Step 8: Adding payment instrument...")
            success = client.add_payment_instrument(basket_id, "CREDIT_CARD", "Visa")
            if not success:
                logger.error("✗ Failed to add payment instrument")
                return False
            logger.info("✓ Added payment instrument")

            # Step 9: Create order
            logger.info("Step 9: Creating order...")
            order_no = client.create_order(basket_id)
            if not order_no:
                logger.error("✗ Failed to create order")
                return False
            logger.info(f"✓ Created order: {order_no}")

            # Step 10: Get order details
            logger.info("Step 10: Retrieving order details...")
            order = client.get_order(order_no)
            if not order:
                logger.error("✗ Failed to retrieve order")
                return False
            logger.info(f"✓ Order Number: {order.get('orderNo')}")
            logger.info(f"  Order Total: {order.get('orderTotal')}")
            return True

    except Exception as e:
        logger.error(f"✗ Guest checkout flow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════
#  REGISTERED USER FLOW
# ═══════════════════════════════════════════════════════════════════════


def test_registered_passwordless_login(email: str):
    """Test passwordless OTP request (sends email with 6-digit code)."""
    logger.info("\n=== [REGISTERED] Testing Passwordless OTP Login ===")

    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            assert not client.is_authenticated, "Should start unauthenticated"

            success = client.request_passwordless_login(email)
            if success:
                logger.info(f"✓ OTP sent to {email}")
                logger.info("  ⏳ Check your email for the 6-digit code")
                return True
            else:
                logger.error(f"✗ Failed to send OTP to {email}")
                return False
    except Exception as e:
        logger.error(f"✗ Passwordless login request failed: {e}")
        return False


def test_registered_otp_verification(otp_code: str):
    """Test OTP verification and token exchange.

    NOTE: This test requires a valid OTP code from email.
    """
    logger.info("\n=== [REGISTERED] Testing OTP Verification ===")

    try:
        config = SCAPIConfig.from_env()
        with SalesforceSyncClient(config) as client:
            token_data = client.get_passwordless_token(otp_code)

            if token_data:
                logger.info("✓ OTP verified — passwordless token obtained")
                logger.info(f"  customer_id: {token_data.get('customer_id')}")
                logger.info(f"  token_type: {token_data.get('token_type')}")
                logger.info(f"  expires_in: {token_data.get('expires_in')} seconds")
                assert client.is_authenticated, "Should be authenticated now"
                assert client.customer_id is not None, "Customer ID should be set"
                return True, client
            else:
                logger.error("✗ OTP verification failed (invalid or expired code)")
                return False, None
    except Exception as e:
        logger.error(f"✗ OTP verification failed: {e}")
        return False, None


def test_registered_customer_addresses(client: SalesforceSyncClient):
    """Test fetching customer saved addresses."""
    logger.info("\n=== [REGISTERED] Testing Customer Address Fetch ===")

    try:
        customer_id = client.customer_id
        assert customer_id is not None, "Must be authenticated to fetch addresses"

        customer_data = client.get_customer(customer_id)
        if not customer_data:
            logger.error("✗ Failed to fetch customer profile")
            return False, []

        addresses = customer_data.get("addresses", [])
        logger.info(f"✓ Found {len(addresses)} saved addresses for customer {customer_id}")

        for i, addr in enumerate(addresses, 1):
            logger.info(
                f"  {i}. [{addr.get('addressId')}] "
                f"{addr.get('address1')}, {addr.get('city')}, "
                f"{addr.get('stateCode')} {addr.get('postalCode')}"
            )

        if addresses:
            # Test fetching a specific address
            address_id = addresses[0].get("addressId")
            logger.info(f"\n  Fetching specific address: '{address_id}'...")
            specific_addr = client.get_customer_address(customer_id, address_id)
            if specific_addr:
                logger.info(f"  ✓ Fetched address '{address_id}' successfully")
                return True, addresses
            else:
                logger.warning(f"  ! Could not fetch specific address '{address_id}'")
                return True, addresses  # Still pass since we got the list

        return True, addresses

    except Exception as e:
        logger.error(f"✗ Customer address fetch failed: {e}")
        return False, []


def test_registered_full_checkout(client: SalesforceSyncClient, address: dict):
    """Test complete registered user checkout flow with saved address."""
    logger.info("\n=== [REGISTERED] Testing Full Checkout Flow ===")

    try:
        assert client.is_authenticated, "Must be authenticated"
        logger.info(f"Auth mode: Registered (passwordless token, customer_id={client.customer_id})")

        # Step 1: Search for a product (uses passwordless token)
        logger.info("Step 1: Searching for products (authenticated)...")
        products = client.search_products("jacket", count=1)
        if not products:
            logger.error("✗ No products found")
            return False
        product_id = products[0]["productID"]
        logger.info(f"✓ Selected product: {products[0]['name']} (ID: {product_id})")

        # Step 2: Create basket (uses passwordless token)
        logger.info("Step 2: Creating basket (authenticated)...")
        basket_id = client.create_basket()
        if not basket_id:
            logger.error("✗ Failed to create basket")
            return False
        logger.info(f"✓ Created basket: {basket_id}")

        # Step 3: Add item to basket
        logger.info("Step 3: Adding item to basket...")
        success = client.add_item_to_basket(basket_id, product_id, quantity=1)
        if not success:
            logger.error("✗ Failed to add item")
            return False
        logger.info("✓ Added item to basket")

        # Step 4: Use saved address for billing (from customer profile)
        logger.info("Step 4: Adding saved address as billing address...")
        billing_address = {
            "firstName": address.get("firstName", ""),
            "lastName": address.get("lastName", ""),
            "address1": address.get("address1", ""),
            "city": address.get("city", ""),
            "postalCode": address.get("postalCode", ""),
            "stateCode": address.get("stateCode", ""),
            "countryCode": address.get("countryCode", "US"),
        }
        success = client.add_billing_address(basket_id, billing_address)
        if not success:
            logger.error("✗ Failed to add billing address")
            return False
        logger.info(f"✓ Added saved address '{address.get('addressId')}' as billing")

        # Step 5: Add customer email
        logger.info("Step 5: Adding customer email...")
        customer_data = client.get_customer(client.customer_id)
        email = customer_data.get("email", "customer@example.com") if customer_data else "customer@example.com"
        success = client.add_customer(basket_id, email)
        if not success:
            logger.error("✗ Failed to add customer email")
            return False
        logger.info(f"✓ Added customer email: {email}")

        # Step 6: Update shipment with saved address
        logger.info("Step 6: Updating shipment with saved address...")
        success = client.update_shipment(basket_id, billing_address, "001")
        if not success:
            logger.error("✗ Failed to update shipment")
            return False
        logger.info("✓ Updated shipment")

        # Step 7: Add payment instrument
        logger.info("Step 7: Adding payment instrument...")
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

        # Step 9: Retrieve order details
        logger.info("Step 9: Retrieving order details...")
        order = client.get_order(order_no)
        if not order:
            logger.error("✗ Failed to retrieve order")
            return False
        logger.info(f"✓ Order Number: {order.get('orderNo')}")
        logger.info(f"  Order Total: {order.get('orderTotal')}")
        return True

    except Exception as e:
        logger.error(f"✗ Registered checkout flow failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ═══════════════════════════════════════════════════════════════════════
#  TEST RUNNERS
# ═══════════════════════════════════════════════════════════════════════


def run_guest_tests():
    """Run all guest user tests."""
    logger.info("\n" + "=" * 60)
    logger.info(" GUEST USER FLOW TESTS")
    logger.info("=" * 60)

    results = []

    results.append(("Guest Authentication", test_guest_authentication()))

    search_ok, products = test_guest_product_search()
    results.append(("Guest Product Search", search_ok))

    results.append(("Guest Full Checkout", test_guest_full_checkout()))

    return results


def run_registered_tests(email: str, otp_code: str = None):
    """Run all registered user tests.

    Args:
        email: Registered user's email address.
        otp_code: The 6-digit OTP code from email (if already received).
    """
    logger.info("\n" + "=" * 60)
    logger.info(" REGISTERED USER FLOW TESTS")
    logger.info("=" * 60)

    results = []

    # Test 1: Send OTP
    results.append(("Passwordless OTP Request", test_registered_passwordless_login(email)))

    if not otp_code:
        logger.info("\n" + "-" * 40)
        logger.info("PAUSING: Check your email for the 6-digit code.")
        otp_code = input("Enter OTP code: ").strip()
        logger.info("-" * 40)

    if not otp_code:
        logger.error("No OTP code provided. Skipping remaining registered tests.")
        results.append(("OTP Verification", False))
        return results

    # Test 2: Verify OTP
    otp_ok, client = test_registered_otp_verification(otp_code)
    results.append(("OTP Verification", otp_ok))

    if not otp_ok or not client:
        logger.error("OTP verification failed. Skipping remaining tests.")
        return results

    # Test 3: Customer addresses
    addr_ok, addresses = test_registered_customer_addresses(client)
    results.append(("Customer Address Fetch", addr_ok))

    # Test 4: Full checkout with saved address
    if addresses:
        address = addresses[0]  # Use first saved address
        results.append(("Registered Full Checkout", test_registered_full_checkout(client, address)))
    else:
        logger.warning("No saved addresses found. Skipping registered checkout test.")
        results.append(("Registered Full Checkout", False))

    return results


def print_summary(results: list):
    """Print test summary."""
    logger.info("\n" + "=" * 60)
    logger.info(" TEST SUMMARY")
    logger.info("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        logger.info(f"  {test_name}: {status}")

    logger.info(f"\n  Total: {passed}/{total} tests passed")
    return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Test SCAPI Guest and Registered User Checkout Flows"
    )
    parser.add_argument(
        "--mode",
        choices=["guest", "registered", "both"],
        default="both",
        help="Which flow to test (default: both)",
    )
    parser.add_argument(
        "--email",
        default="vijey.anbarasan@nulogic.io",
        help="Registered user email for passwordless login",
    )
    parser.add_argument(
        "--otp",
        default=None,
        help="Pre-provide the 6-digit OTP code (otherwise prompted interactively)",
    )

    args = parser.parse_args()

    logger.info("Starting SCAPI Integration Tests — Guest & Registered Flows\n")

    all_results = []

    if args.mode in ("guest", "both"):
        all_results.extend(run_guest_tests())

    if args.mode in ("registered", "both"):
        all_results.extend(run_registered_tests(args.email, args.otp))

    all_passed = print_summary(all_results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

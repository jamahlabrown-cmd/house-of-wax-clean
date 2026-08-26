#!/usr/bin/env python3
"""House Of Wax -- daily payment-flow health check.

Runs a REAL end-to-end transaction through the exact same app.py functions
the live site uses (not a re-implementation of the logic), using two
permanent, clearly-labeled internal test accounts, then cleans up after
itself. If this fails, real buyers are very likely hitting the same
failure -- this is what would have caught the 2026-08-26 NaN-crash
incident automatically, before a real customer hit it.

Required environment variables:
  SUPABASE_URL, SUPABASE_ANON_KEY   -- same values the live app itself uses
  DIAG_TEST_SELLER_PASSWORD         -- password for internal-diagnostics-test-seller@shophouseofwax.com
  DIAG_TEST_BUYER_PASSWORD          -- password for internal-diagnostics-test-buyer@shophouseofwax.com
  RESEND_API_KEY, DIAGNOSTIC_ALERT_TO (optional) -- reuses the same alert email as diagnostics.py

Test entities (fixed ids, created once, reused every run):
  seller_id=15, buyer_id=131, product_id=893
"""
import os
import sys
import importlib.util
import requests

REPO_ROOT = os.environ.get("HOUSE_OF_WAX_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP_PATH = os.path.join(REPO_ROOT, "app.py")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]
TEST_SELLER_EMAIL = "internal-diagnostics-test-seller@shophouseofwax.com"
TEST_SELLER_PASSWORD = os.environ["DIAG_TEST_SELLER_PASSWORD"]
TEST_BUYER_EMAIL = "internal-diagnostics-test-buyer@shophouseofwax.com"
TEST_BUYER_PASSWORD = os.environ["DIAG_TEST_BUYER_PASSWORD"]
TEST_SELLER_ID = 15
TEST_BUYER_ID = 131
TEST_PRODUCT_ID = 893
REQUEST_TIMEOUT = 15

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_TO = os.environ.get("DIAGNOSTIC_ALERT_TO", "hello@shophouseofwax.com")

# app.py reads Supabase config from env vars first (config_value()), so this
# must be set before importing it.
os.environ["SUPABASE_URL"] = SUPABASE_URL
os.environ["SUPABASE_ANON_KEY"] = SUPABASE_ANON_KEY

spec = importlib.util.spec_from_file_location("app", APP_PATH)
hw_app = importlib.util.module_from_spec(spec)
sys.modules["app"] = hw_app
spec.loader.exec_module(hw_app)

if not hw_app.hosted_enabled():
    print("FATAL: SUPABASE_URL/SUPABASE_ANON_KEY not detected by app.py -- cannot run a live check.")
    sys.exit(2)


def sign_in(email, password):
    r = requests.post(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=REQUEST_TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def set_session(access_token, user_id, email):
    hw_app.st.session_state["auth_session"] = {"user_id": user_id, "email": email, "access_token": access_token}


results = []
new_purchase_id = [None]


def check(name, fn):
    try:
        fn()
        results.append((name, True, "OK"))
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))


def step_publish_live():
    seller_token = sign_in(TEST_SELLER_EMAIL, TEST_SELLER_PASSWORD)
    set_session(seller_token, "diag-seller", TEST_SELLER_EMAIL)
    ok = hw_app.core_update(
        "products", {"listing_status": "Live", "price": 1.00, "updated_at": hw_app.now()},
        {"id": TEST_PRODUCT_ID, "seller_id": TEST_SELLER_ID},
        "UPDATE products SET listing_status=?,price=?,updated_at=? WHERE id=? AND seller_id=?",
        ("Live", 1.00, hw_app.now(), TEST_PRODUCT_ID, TEST_SELLER_ID),
    )
    if not ok:
        raise RuntimeError("Could not publish the test listing Live (seller-side write failed)")


def step_add_to_cart():
    buyer_token = sign_in(TEST_BUYER_EMAIL, TEST_BUYER_PASSWORD)
    set_session(buyer_token, "diag-buyer", TEST_BUYER_EMAIL)
    product = hw_app.hosted_select("products", {"id": TEST_PRODUCT_ID}, limit=1).iloc[0].to_dict()
    cart_id = hw_app.add_to_cart(TEST_BUYER_ID, product)
    if not cart_id:
        raise RuntimeError("add_to_cart did not return a cart row id")


def step_checkout():
    cart_rows_df = hw_app.buyer_cart_items(TEST_BUYER_ID)
    matching = cart_rows_df[cart_rows_df["product_id"] == TEST_PRODUCT_ID]
    if matching.empty:
        raise RuntimeError("Test item is not in the cart -- previous step must have failed silently")
    row = matching.iloc[0]
    cart_rows = [{"id": int(row["id"]), "product_id": int(row["product_id"])}]
    result = hw_app.checkout_seller_cart_group(TEST_BUYER_ID, TEST_SELLER_ID, cart_rows)
    if not result.get("created_purchase_request_ids") or not result["created_purchase_request_ids"][0]:
        raise RuntimeError(f"Checkout did not create a real purchase request: {result}")
    new_purchase_id[0] = result["created_purchase_request_ids"][0]


def step_payment_summary_computes():
    # This is the exact function that crashed for a real buyer on 2026-08-26
    # (ValueError: cannot convert float NaN to integer).
    groups = hw_app.seller_ready_to_pay_groups(TEST_BUYER_ID)
    match = next((g for g in groups if g["seller_id"] == TEST_SELLER_ID), None)
    if not match:
        raise RuntimeError("Ready-to-pay group not found after checkout")
    total = match["total"]
    if total != total:  # NaN != NaN is the standard float NaN check
        raise RuntimeError("Payment total is NaN")
    if not total or total <= 0:
        raise RuntimeError(f"Payment total is missing, zero, or negative: {total!r}")


def step_reservation_recorded():
    row = hw_app.hosted_select("purchase_requests", {"id": new_purchase_id[0]}, limit=1)
    if row.empty:
        raise RuntimeError("Purchase request row not found after checkout")
    if not hw_app.safe(row.iloc[0].get("payment_due_at")):
        raise RuntimeError("payment_due_at was never set -- listing reservation may have silently failed")


def step_buyer_activity_tables_does_not_crash():
    # Real incident: this crashed for ANY page a buyer visited when they had
    # an unrelated listing_inquiries row with a null product_id. Calling it
    # directly here for the test buyer confirms the fix holds.
    hw_app.buyer_activity_tables(TEST_BUYER_ID)


def cleanup():
    # Must run as the SELLER -- closing a purchase request and resetting the
    # listing's own status are seller-permissioned writes under RLS, same as
    # a real seller managing their own inventory. Re-authenticate explicitly
    # rather than trusting whatever session was left over from earlier steps.
    seller_token = sign_in(TEST_SELLER_EMAIL, TEST_SELLER_PASSWORD)
    set_session(seller_token, "diag-seller", TEST_SELLER_EMAIL)
    if new_purchase_id[0]:
        # Closing, not deleting -- purchase_requests has no delete RLS policy
        # for buyer/seller roles (admin-only, confirmed empirically), and
        # Closed is the correct real terminal state anyway, same as how a
        # real seller ends an order. This also reverts the product's
        # listing_status back to Live on its own, since no other active
        # purchase request exists for it -- the explicit Draft reset below
        # still runs afterward regardless.
        hw_app.update_purchase_request_status(new_purchase_id[0], "Closed", seller_id=TEST_SELLER_ID, quiet=True)
    ok = hw_app.core_update(
        "products", {"listing_status": "Draft", "updated_at": hw_app.now()},
        {"id": TEST_PRODUCT_ID, "seller_id": TEST_SELLER_ID},
        "UPDATE products SET listing_status=?,updated_at=? WHERE id=? AND seller_id=?",
        ("Draft", hw_app.now(), TEST_PRODUCT_ID, TEST_SELLER_ID),
    )
    if not ok:
        raise RuntimeError("Could not reset the test listing back to Draft after the run")

    buyer_token = sign_in(TEST_BUYER_EMAIL, TEST_BUYER_PASSWORD)
    set_session(buyer_token, "diag-buyer", TEST_BUYER_EMAIL)
    leftover = hw_app.buyer_cart_items(TEST_BUYER_ID)
    if not leftover.empty:
        for _, r in leftover[leftover["product_id"] == TEST_PRODUCT_ID].iterrows():
            hw_app.remove_from_cart(int(r["id"]))


check("Seller can publish the internal test listing Live", step_publish_live)
check("Buyer can add the test listing to cart", step_add_to_cart)
check("Checkout completes and creates a real purchase request", step_checkout)
check("Payment summary computes a real, non-NaN total", step_payment_summary_computes)
check("Payment deadline was recorded (reservation succeeded)", step_reservation_recorded)
check("Buyer activity pages do not crash (regression guard)", step_buyer_activity_tables_does_not_crash)

try:
    cleanup()
    results.append(("Cleanup completed", True, "OK"))
except Exception as e:
    results.append(("Cleanup completed", False, f"{type(e).__name__}: {e}"))

for name, ok, message in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {message}")

failures = [(n, m) for n, ok, m in results if not ok]

if failures and RESEND_API_KEY:
    body_lines = ["House Of Wax PAYMENT FLOW check found a problem -- this may be blocking real sales right now:", ""]
    for name, message in failures:
        body_lines.append(f"- {name}: {message}")
    body_lines += ["", "Checked via the automated daily payment-flow diagnostic."]
    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": "House Of Wax Diagnostics <hello@shophouseofwax.com>",
            "to": [ALERT_TO],
            "subject": f"🚨 House Of Wax: payment flow check failed ({len(failures)} issue(s))",
            "text": "\n".join(body_lines),
        },
        timeout=REQUEST_TIMEOUT,
    )

if failures:
    sys.exit(1)
print("\nAll payment-flow checks passed.")
sys.exit(0)

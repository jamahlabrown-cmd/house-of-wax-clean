"""
Smoke tests for House Of Wax, using Streamlit's built-in AppTest
(streamlit.testing.v1) -- no browser, no server, no Supabase secrets
required. These run against the local SQLite fallback path.

Run with:
    pip install pytest
    pytest tests/test_smoke.py -v

What this DOES cover: navigation between pages doesn't crash, form
validation logic (password length, matching confirmation, required
fields), and the Add Inventory Step 1 structure (the artist/title
fields that drive the price box, fixed in V25.43.84-85).

What this does NOT cover: anything that only happens against real
Supabase Auth (e.g. the sign-up/sign-in email-confirmation messaging
fixed in V25.43.86) -- hosted_enabled() is False with no secrets
configured, so those code paths aren't exercised here. See
tests/README.md for how to run a second pass against a staging
Supabase project once one exists.
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from streamlit.testing.v1 import AppTest


def fresh_app():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception, f"App failed to load: {at.exception}"
    return at


def goto(at, page, area_key="marketplace_navigation"):
    at.sidebar.radio(key=area_key).set_value(page).run()
    assert not at.exception, f"Navigating to {page!r} raised: {at.exception}"
    return at


# ---------- Baseline ----------

def test_app_loads_without_exception():
    fresh_app()


def test_home_page_renders():
    at = fresh_app()
    assert any("House Of Wax" in md.value for md in at.markdown)


# ---------- Navigation smoke pass ----------

@pytest.mark.parametrize("page", ["Home", "Search Music", "Knowledge Hub", "My Account", "Seller Stores"])
def test_marketplace_pages_render_without_crashing(page):
    at = fresh_app()
    goto(at, page)


# ---------- Account creation: form validation (pure logic, no network) ----------

def test_create_account_rejects_missing_fields():
    at = fresh_app()
    goto(at, "My Account")
    at.button(key="FormSubmitter:create_account_form-Create House Of Wax Account").click().run()
    assert any("required" in a.value.lower() for a in at.error), "Expected a 'required' validation error"


def test_create_account_rejects_short_password():
    at = fresh_app()
    goto(at, "My Account")
    at.text_input(key="create_name").set_value("QA Tester").run()
    at.text_input(key="create_email").set_value("qa-tester@example.com").run()
    at.text_input(key="create_password").set_value("short").run()
    at.text_input(key="create_confirm").set_value("short").run()
    at.button(key="FormSubmitter:create_account_form-Create House Of Wax Account").click().run()
    assert any("8 characters" in a.value for a in at.error), "Expected the 8-character password error"


def test_create_account_rejects_mismatched_confirmation():
    at = fresh_app()
    goto(at, "My Account")
    at.text_input(key="create_name").set_value("QA Tester").run()
    at.text_input(key="create_email").set_value("qa-tester@example.com").run()
    at.text_input(key="create_password").set_value("LongEnoughPassword1").run()
    at.text_input(key="create_confirm").set_value("DoesNotMatch1").run()
    at.button(key="FormSubmitter:create_account_form-Create House Of Wax Account").click().run()
    assert any("does not match" in a.value.lower() for a in at.error), "Expected a confirmation-mismatch error"


def test_create_account_rejects_invalid_email():
    at = fresh_app()
    goto(at, "My Account")
    at.text_input(key="create_name").set_value("QA Tester").run()
    at.text_input(key="create_email").set_value("not-an-email").run()
    at.text_input(key="create_password").set_value("LongEnoughPassword1").run()
    at.text_input(key="create_confirm").set_value("LongEnoughPassword1").run()
    at.button(key="FormSubmitter:create_account_form-Create House Of Wax Account").click().run()
    assert any("valid email" in a.value.lower() for a in at.error), "Expected an invalid-email error"


# ---------- Commission split (V25.43.100) ----------

def test_commission_fee_uses_nine_percent_default():
    import app as hw_app
    assert hw_app.commission_percent() == 9.0
    assert hw_app.fee(100) == 9.0
    assert hw_app.fee(45.50) == round(45.50 * 0.09, 2)


def test_house_of_wax_paypal_link_is_seeded():
    import app as hw_app
    fresh_app()
    assert hw_app.setting("house_of_wax_paypal_link") == "mojo71mojo@yahoo.com"


# ---------- Add Inventory: Step 1 structure (regression guard for V25.43.84-85) ----------

def test_add_inventory_step1_artist_title_are_outside_the_form():
    # These specific keys only exist because Artist/Title were deliberately
    # moved outside st.form so the price box can react to them live -- see
    # the V25.43.84 fix. If a future refactor moves them back inside the
    # form, these keys will disappear and this test will fail loudly.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert not at.exception

    headings = [m.value for m in at.markdown]
    assert any("Step 1: What are you selling" in h for h in headings)

    live_artist_keys = [t.key for t in at.text_input if t.key and t.key.startswith("upload_live_artist_")]
    live_title_keys = [t.key for t in at.text_input if t.key and t.key.startswith("upload_live_title_")]
    assert live_artist_keys and live_title_keys, "Live artist/title fields should exist outside the form"


def test_core_update_fails_loudly_without_sql_in_local_mode():
    # Regression guard: core_update used to silently return True in local-
    # SQLite mode when a caller omitted sql/params, meaning "nothing was
    # written" could get reported as success -- the exact bug shape as the
    # V25.43.86 sign-up fix. It should now raise instead of lying.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    with pytest.raises(ValueError):
        hw_app.core_update("buyers", {"name": "x"}, {"id": 1})


def test_want_list_notify_surfaces_rpc_failure_instead_of_swallowing_it(monkeypatch):
    # Regression guard: find_want_list_matches_for_notify() used to have a
    # bare "except Exception: return []" around the find_want_list_matches
    # RPC call -- if that RPC was ever missing, misconfigured, or rejected,
    # want-list match emails would silently never fire, with no error
    # anywhere to show it. WANT_LIST_NOTIFY_STATUS didn't exist before this
    # fix, so this test fails outright against the pre-fix code.
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    monkeypatch.setattr(hw_app, "supabase_config", lambda: ("https://example.invalid", "fake-anon-key"))

    def boom(*args, **kwargs):
        raise ConnectionError("simulated RPC failure")
    monkeypatch.setattr(hw_app.requests, "post", boom)

    hw_app.WANT_LIST_NOTIFY_STATUS["last_error"] = ""
    result = hw_app.find_want_list_matches_for_notify("Some Artist", "Some Title")
    assert result == []
    assert "simulated RPC failure" in hw_app.WANT_LIST_NOTIFY_STATUS["last_error"], (
        "Expected the RPC failure to be recorded, not silently swallowed"
    )


def test_culture_posts_seller_spotlight_shows_on_seller_profile():
    # Regression guard: culture_posts (backing the admin "Seller Spotlight"
    # tool) had no seller_id column at all, so a spotlight post could never
    # be linked back to a seller or displayed anywhere -- it was written but
    # nothing could ever read it by seller. Confirms the seller_id column
    # exists in local mode (via the mig-dict addcol migration) and that
    # seller_profile() actually renders spotlight posts for that seller.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    _, seller_id, _, _ = hw_app.seed_all()
    hw_app.run(
        "INSERT INTO culture_posts(seller_id,title,category,author,body,image_url,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (seller_id, "Seller Spotlight: Test Store", "Seller Spotlight", "House Of Wax", "Great store.", "", "Published", hw_app.now()),
    )
    at = fresh_app()
    goto(at, "Seller Stores")
    at.session_state["seller_id"] = int(seller_id)
    at.run()
    assert not at.exception
    headings = [s.value for s in at.subheader]
    assert any("House Of Wax Spotlight" in h for h in headings), (
        "Expected the seller's public profile to show the Seller Spotlight post"
    )


def test_add_inventory_price_box_shows_why_when_no_discogs_token():
    # No Supabase/Discogs secrets are configured for this local run, so typing
    # an artist should hit the explicit "no token configured" caption instead
    # of silently showing nothing -- the whole point of the V25.43.82 fix.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()

    artist_key = next(t.key for t in at.text_input if t.key and t.key.startswith("upload_live_artist_"))
    title_key = next(t.key for t in at.text_input if t.key and t.key.startswith("upload_live_title_"))
    at.text_input(key=artist_key).set_value("Technotronic").run()
    at.text_input(key=title_key).set_value("Pump Up The Jam").run()
    assert not at.exception

    captions = [c.value for c in at.caption]
    assert any("no discogs_token configured" in c.lower() for c in captions), (
        "Expected the explicit 'no token configured' caption, not silence"
    )


def test_real_signed_in_seller_can_reach_bulk_import_tools():
    # Regression guard: the "More Tools" tabs (Bulk import / Announcements /
    # Events-drops) were only ever rendered in the admin/testing-mode branch
    # of seller_dashboard(). A real signed-in seller's branch called
    # seller_inventory_visibility_summary(sid) and returned immediately after
    # -- the tabs code below it was unreachable for anyone but an admin or a
    # Testing Mode session. Real sellers had no way to bulk-import a CSV, post
    # a store announcement, or create an event/drop, even though both
    # store_announcements and seller_events are displayed on the seller's own
    # public profile page (seller_profile()).
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception

    buyer_id, seller_id, buyer_email, seller_email = hw_app.seed_all()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        ("real-seller-uuid", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )

    at.session_state["auth_session"] = {"user_id": "real-seller-uuid", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard", area_key="marketplace_navigation")
    at.radio(key="seller_tools_primary_section_auth").set_value("More Tools").run()
    assert not at.exception

    tab_labels = [t.proto.label for t in at.tabs]
    assert tab_labels == ["Bulk import", "Announcements", "Events/drops"], (
        f"Expected a real seller to reach the Bulk import/Announcements/Events tabs, got {tab_labels}"
    )


def test_seller_status_banner_removed_from_dashboard():
    # seller_status_notice() (the "Enabled" badge + "You're approved to
    # sell..." text) used to render as a big colored banner at the top of
    # every Seller Dashboard page -- first deduped from 2 copies down to 1,
    # then removed entirely per founder feedback ("those big buttons that
    # say approved and ready to sell can go"). Confirms it's gone for good,
    # on the dashboard itself and on every sub-tab.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")

    def count_status_banner():
        texts = [w.value for w in at.warning] + [s.value for s in at.success]
        return sum(1 for t in texts if "approved to sell" in t.lower() or "approved to publish listings" in t.lower())

    assert count_status_banner() == 0, "Expected the approved-to-sell banner to be fully removed from Seller Dashboard"

    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert count_status_banner() == 0, "Add Inventory should not show the seller status banner"

    at.radio(key="seller_tools_primary_section").set_value("My Inventory").run()
    assert count_status_banner() == 0, "My Inventory should not show the seller status banner"


def test_buyer_can_save_avatar_url_to_profile():
    # Regression guard: buyers had no photo/avatar column at all (unlike
    # sellers, which have logo_url/banner_url), so there was no way for a
    # buyer to add a profile photo. Confirms the avatar_url column exists
    # (via the mig-dict addcol migration) and round-trips through core_update
    # the same way seller logo_url/banner_url already do.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    buyer_id, seller_id, buyer_email, seller_email = hw_app.seed_all()
    ok = hw_app.core_update(
        "buyers", {"avatar_url": "house_of_wax_uploads/buyer_avatars/test.png"}, {"id": buyer_id},
        "UPDATE buyers SET avatar_url=? WHERE id=?", ("house_of_wax_uploads/buyer_avatars/test.png", buyer_id),
    )
    assert ok
    b = hw_app.get_buyer(buyer_id)
    assert b.get("avatar_url") == "house_of_wax_uploads/buyer_avatars/test.png"


def _new_isolated_product(hw_app, seller_id, title):
    # ensure_product() reuses whatever product row already exists in the
    # shared SQLite file, which collides across tests in the same pytest
    # run for anything that mutates listing_status/purchase_requests (like
    # the payment-window tests below). Insert a dedicated row instead.
    hw_app.run(
        '''INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (seller_id, '', '', '', '', 'Vinyl Records', 'Isolated Test Artist', title, 'Vinyl', '', '1999', 'Soul', 'VG+', 'VG', '', 'Isolated test product.', 24.99, 1, 5.00, '', '', '', '', 'Live', 'Fixed Price', hw_app.now(), hw_app.now()),
    )
    return int(hw_app.df("SELECT id FROM products WHERE title=? ORDER BY id DESC LIMIT 1", (title,)).iloc[0]['id'])


def _new_isolated_buyer(hw_app, email_prefix):
    # ensure_buyer() reuses whatever buyer row already exists in the shared
    # SQLite file (same reasoning as _new_isolated_product above) -- and
    # _real_buyer_session's app_users row is keyed on a unique auth_user_id
    # AND a unique email, so any two tests sharing a buyer would collide on
    # both. Give each test needing a real signed-in session its own buyer.
    email = f"{email_prefix}@example.com"
    return hw_app.create_buyer(email, email_prefix.replace("_", " ").title())


def _real_buyer_session(at, hw_app, buyer_id, buyer_email):
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,buyer_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-buyer-uuid-{buyer_id}", buyer_email, "Real Buyer", "Buyer", buyer_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": "real-buyer-uuid", "email": buyer_email, "access_token": "fake"}
    at.run()


def test_buy_now_reserves_listing_and_starts_five_day_payment_window():
    # Regression guard for the new payment-window policy: clicking Buy Now
    # used to create a purchase_request at status='New' and leave the
    # listing_status untouched (Live) until the seller manually clicked
    # "Mark Seller Accepted" -- an unbounded wait with no deadline, and the
    # item stayed buyable by someone else in the meantime. Buy Now should now
    # go straight to 'Seller Accepted', reserve the listing (Pending
    # Pickup/Payment) so nobody else can buy it, and set a payment_due_at
    # five days out -- all in the same click, no seller action required.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = hw_app.ensure_buyer()
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Buy Now Window Test Album")
    buyer = hw_app.get_buyer(buyer_id)

    _real_buyer_session(at, hw_app, buyer_id, buyer["email"])
    goto(at, "Search Music", area_key="marketplace_navigation")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    buy_button = next(b for b in at.button if b.key == f"purchase_buy_now_product_{product_id}")
    buy_button.click().run()
    assert not at.exception, at.exception

    pr = hw_app.df("SELECT * FROM purchase_requests WHERE product_id=? ORDER BY id DESC LIMIT 1", (product_id,))
    assert not pr.empty, "Expected a purchase_requests row to be created"
    row = pr.iloc[0]
    assert row["status"] == "Seller Accepted", f"Expected instant reservation, got status={row['status']!r}"
    assert row["payment_due_at"], "Expected payment_due_at to be set"

    from datetime import datetime as _dt
    due = _dt.fromisoformat(row["payment_due_at"])
    days_out = (due - _dt.now()).total_seconds() / 86400
    assert 4.9 <= days_out <= 5.1, f"Expected ~5 days out, got {days_out:.2f} days"

    product = hw_app.df("SELECT listing_status FROM products WHERE id=?", (product_id,))
    assert product.iloc[0]["listing_status"] == "Pending Pickup/Payment", (
        "Expected the listing to be reserved (taken off the market) immediately on Buy Now"
    )

    successes = [s.value for s in at.success]
    assert any("Pay by" in s for s in successes), f"Expected a 'Pay by <date>' message, got {successes}"


def test_missed_payment_window_releases_listing_and_strikes_buyer():
    # Regression guard: the auto-expiration side of the same policy. If a
    # buyer's payment_due_at passes while still 'Seller Accepted', the
    # request should flip to 'Buyer Did Not Pay', the listing should go back
    # to Live (so someone else can buy it), and the buyer should get a
    # strike on their account -- all without any admin/seller action, since
    # Streamlit has no background scheduler and this runs lazily from
    # header() on the next page load.
    import app as hw_app
    from datetime import datetime as _dt, timedelta as _td
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"

    buyer_id = hw_app.ensure_buyer()
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Missed Payment Window Test Album")
    starting_strikes = int(hw_app.get_buyer(buyer_id).get("strikes") or 0)

    overdue_due = (_dt.now() - _td(days=1)).isoformat(timespec="seconds")
    hw_app.run(
        "INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,status,payment_due_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (product_id, seller_id, buyer_id, "Overdue Buyer", "overdue@example.com", "Seller Accepted", overdue_due, hw_app.now(), hw_app.now()),
    )
    hw_app.run("UPDATE products SET listing_status='Pending Pickup/Payment' WHERE id=?", (product_id,))

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()  # header() runs on this first load -- the sweep has no prior throttle timestamp yet
    assert not at.exception, at.exception

    pr = hw_app.df("SELECT * FROM purchase_requests WHERE product_id=? AND buyer_name='Overdue Buyer'", (product_id,))
    assert pr.iloc[0]["status"] == "Buyer Did Not Pay", f"Expected auto-expiry, got status={pr.iloc[0]['status']!r}"

    product = hw_app.df("SELECT listing_status FROM products WHERE id=?", (product_id,))
    assert product.iloc[0]["listing_status"] == "Live", "Expected the listing to be released back to Live"

    ending_strikes = int(hw_app.get_buyer(buyer_id).get("strikes") or 0)
    assert ending_strikes == starting_strikes + 1, f"Expected a strike added, got {starting_strikes} -> {ending_strikes}"


def test_account_page_has_no_buying_selling_metric_banners():
    # Regression guard: My Account used to show three big st.metric banners
    # (Account / Buying / Selling) right under "Signed in as..." -- founder
    # feedback: "Buying selling banners at the top need to go", since the
    # same info is already in the Account/Buying/Selling tabs right below.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    buyer_id, seller_id, buyer_email, seller_email = hw_app.seed_all()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,buyer_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        ("real-account-uuid", buyer_email, "Real Buyer", "Buyer", buyer_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": "real-account-uuid", "email": buyer_email, "access_token": "fake"}
    at.run()
    goto(at, "My Account")
    assert not at.exception, at.exception

    metric_labels = [m.label for m in at.get("metric")]
    assert metric_labels == [], f"Expected no metric banners on My Account, got {metric_labels}"


def _reservation_failure_probe():
    import app as hw_app
    hw_app.reserve_listing_for_payment(1, 1)


def _restore_pending_action_probe():
    import app as hw_app
    hw_app.restore_pending_action()


def test_reservation_failure_is_surfaced_not_silently_swallowed(monkeypatch):
    # Regression guard for a real production bug: reserve_listing_for_payment()
    # updates BOTH products.listing_status and purchase_requests.payment_due_at.
    # In production this update to `products` happens under the BUYER's own
    # RLS session (they're the one clicking Buy Now), but no RLS policy ever
    # granted a buyer UPDATE rights on products -- so the write was silently
    # rejected while the purchase_requests row still saved fine. The buyer
    # saw a raw "Supabase update failed for products: HTTP 403" error banner
    # sitting right next to the "Bought!" success message, which read as
    # "none of the buttons work" (reported directly by the founder). Fixed
    # with a new RLS policy (supabase_core_policies.sql: "buyer reserve
    # product for own purchase") AND by checking the result here instead of
    # assuming success -- this test guards the latter half, since RLS itself
    # can't be exercised against local SQLite (no RLS engine at all).
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    monkeypatch.setattr(hw_app, "core_update", lambda table_name, *a, **k: table_name != "products")

    at = AppTest.from_function(_reservation_failure_probe, default_timeout=30)
    at.run()
    assert not at.exception, at.exception

    errors = [e.value for e in at.error]
    assert any("could not reserve the listing" in e for e in errors), (
        f"Expected the reservation-failure error to be surfaced, got errors={errors}"
    )


def _payment_expiry_sweep_probe():
    import app as hw_app
    hw_app.expire_overdue_purchase_requests()


def test_expiry_sweep_buyer_strike_failure_is_quiet_not_a_random_error_banner(monkeypatch):
    # Regression guard for a second real production bug found in the same
    # audit as the reservation-failure fix above: expire_overdue_purchase_
    # requests() also writes a strike to buyers.strikes, but that sweep runs
    # lazily on EVERY page load for WHOEVER is browsing -- often a seller
    # checking their own dashboard, not the buyer being struck. No RLS
    # policy ever let a seller's session touch a buyers row that wasn't
    # their own, so the write was silently rejected -- and because this
    # background sweep called the normal (loud) core_update, any seller
    # loading ANY page could see an out-of-context "Supabase update failed
    # for buyers: HTTP 403" error banner for a write they had no part in.
    # Fixed with a new RLS policy ("seller strike buyer for own unpaid
    # order") AND by making every write inside this sweep quiet=True,
    # recording failures to PAYMENT_EXPIRY_STATUS instead of popping an
    # unrelated error on the current page.
    import pandas as pd
    from datetime import datetime as _dt, timedelta as _td
    import app as hw_app

    overdue_row = {
        "id": 1, "product_id": 1, "seller_id": 1, "buyer_id": 1,
        "status": "Seller Accepted",
        "payment_due_at": (_dt.now() - _td(days=1)).isoformat(timespec="seconds"),
    }

    def fake_hosted_select(table_name, filters=None, **kwargs):
        if table_name == "purchase_requests":
            return pd.DataFrame([overdue_row])
        if table_name == "products":
            return pd.DataFrame([{"id": 1, "listing_status": "Pending Pickup/Payment"}])
        return pd.DataFrame()

    def fake_core_update(table_name, *a, **k):
        if table_name == "buyers":
            hw_app.SUPABASE_STATUS["last_error"] = "buyers: HTTP 403 new row violates row-level security policy"
            return False
        return True

    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    monkeypatch.setattr(hw_app, "hosted_select", fake_hosted_select)
    monkeypatch.setattr(hw_app, "get_buyer", lambda bid: {"id": bid, "strikes": 0})
    monkeypatch.setattr(hw_app, "core_update", fake_core_update)
    hw_app.PAYMENT_EXPIRY_STATUS["last_error"] = ""

    at = AppTest.from_function(_payment_expiry_sweep_probe, default_timeout=30)
    at.run()
    assert not at.exception, at.exception

    assert list(at.error) == [], f"Expected no error banner from the background sweep, got {[e.value for e in at.error]}"
    assert hw_app.PAYMENT_EXPIRY_STATUS["last_error"], "Expected the strike-write failure to be recorded, not silently dropped"


# ---------- Cart (slice 2: add-to-cart) ----------

def test_add_to_cart_is_idempotent_and_shows_in_cart_badge():
    # A real signed-in buyer clicks Add to Cart on the product detail page --
    # confirms exactly one cart_items row is created, and clicking again (or
    # just re-rendering the page) doesn't create a duplicate: is_in_cart()
    # should make add_to_cart() a no-op and the button should be replaced by
    # an "In Cart" badge.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = _new_isolated_buyer(hw_app, "add_to_cart_test_buyer")
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Add To Cart Test Album")
    buyer = hw_app.get_buyer(buyer_id)

    _real_buyer_session(at, hw_app, buyer_id, buyer["email"])
    goto(at, "Search Music", area_key="marketplace_navigation")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    add_button = next(b for b in at.button if b.key == f"cart_add_detail_{product_id}")
    add_button.click().run()
    assert not at.exception, at.exception

    cart_rows = hw_app.df("SELECT * FROM cart_items WHERE buyer_id=? AND product_id=?", (buyer_id, product_id))
    assert len(cart_rows) == 1, f"Expected exactly one cart_items row, got {len(cart_rows)}"

    # Re-render: the button should now be gone, replaced by the "In Cart" badge.
    at.run()
    assert not at.exception, at.exception
    add_buttons = [b for b in at.button if b.key == f"cart_add_detail_{product_id}"]
    assert add_buttons == [], "Expected the Add to Cart button to be replaced by an In Cart badge"

    cart_rows_after = hw_app.df("SELECT * FROM cart_items WHERE buyer_id=? AND product_id=?", (buyer_id, product_id))
    assert len(cart_rows_after) == 1, f"Expected still exactly one cart_items row after re-render, got {len(cart_rows_after)}"


def test_anonymous_add_to_cart_resumes_after_sign_in():
    # Anonymous visitor clicks Add to Cart -> gets redirected to sign in with
    # a pending action saved -- then, once signed in, restore_pending_action()
    # (called automatically post sign-in in the real app) should complete the
    # add instead of just reopening a form, since Add to Cart has no form to
    # reopen.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = _new_isolated_buyer(hw_app, "anon_add_to_cart_test_buyer")
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Anonymous Add To Cart Test Album")
    buyer = hw_app.get_buyer(buyer_id)

    goto(at, "Search Music", area_key="marketplace_navigation")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    add_button = next(b for b in at.button if b.key == f"cart_add_detail_{product_id}")
    add_button.click().run()
    assert not at.exception, at.exception

    action = at.session_state["pending_action"] if "pending_action" in at.session_state else {}
    assert action.get("action_type") == "Add to Cart", f"Expected a pending Add to Cart action, got {action}"
    assert hw_app.df("SELECT * FROM cart_items WHERE product_id=?", (product_id,)).empty, (
        "Nothing should be in the cart yet -- the visitor was never signed in"
    )

    # Resume as a fresh probe rather than continuing to drive the same `at`
    # through My Account: product_detail() rendered a Report Listing form
    # above (report_listing_form), and AppTest's widget-state diffing trips
    # on that form's keys surviving a goto() to an unrelated page -- a
    # framework quirk, not something restore_pending_action() itself does.
    # Carry the pending action + auth session over as plain session_state
    # (not widget state) into a fresh probe that calls the exact same
    # function the real "Back to Item" button calls.
    resume_at = AppTest.from_function(_restore_pending_action_probe, default_timeout=30)
    resume_at.session_state["pending_action"] = {
        "action_type": "Add to Cart", "product_id": product_id, "seller_id": seller_id, "return_page": "Search Music",
    }
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,buyer_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-buyer-uuid-{buyer_id}", buyer["email"], "Real Buyer", "Buyer", buyer_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    resume_at.session_state["auth_session"] = {"user_id": f"real-buyer-uuid-{buyer_id}", "email": buyer["email"], "access_token": "fake"}
    resume_at.run()
    assert not resume_at.exception, resume_at.exception

    cart_rows = hw_app.df("SELECT * FROM cart_items WHERE buyer_id=? AND product_id=?", (buyer_id, product_id))
    assert len(cart_rows) == 1, f"Expected the cart add to complete after sign-in, got {len(cart_rows)} rows"

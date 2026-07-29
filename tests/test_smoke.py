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


# ---------- Add Inventory: Step 2 structure (regression guard for V25.43.84-85) ----------

def test_add_inventory_step2_artist_title_are_outside_the_form():
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
    assert any("Step 1: Search by barcode" in h for h in headings)
    assert any("Step 2: What are you selling" in h for h in headings)

    live_artist_keys = [t.key for t in at.text_input if t.key and t.key.startswith("upload_live_artist_")]
    live_title_keys = [t.key for t in at.text_input if t.key and t.key.startswith("upload_live_title_")]
    assert live_artist_keys and live_title_keys, "Live artist/title fields should exist outside the form"


# ---------- Dead-end query-param screens have a way back (regression guard for the Patti Hansen "white screen" report) ----------

def test_privacy_policy_screen_has_a_way_back():
    # Regression guard: ?legal=privacy runs before the sidebar/menu exists
    # and calls st.stop() right after rendering -- and the query param
    # persists across reruns, so without an escape button a visitor who
    # clicked "Privacy Policy" was stuck there permanently, with no menu,
    # until they manually edited the URL or closed the browser. This is the
    # "white screen, had to close the browser" bug from the UX review.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["legal"] = "privacy"
    at.run()
    assert not at.exception
    back_buttons = [b for b in at.button if b.key == "privacy_policy_back"]
    assert back_buttons, "Privacy policy screen should have a way back to the app"
    back_buttons[0].click().run()
    assert not at.exception
    assert "legal" not in at.query_params


def test_terms_of_service_screen_has_a_way_back():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["legal"] = "terms"
    at.run()
    assert not at.exception
    back_buttons = [b for b in at.button if b.key == "terms_of_service_back"]
    assert back_buttons, "Terms of service screen should have a way back to the app"
    back_buttons[0].click().run()
    assert not at.exception
    assert "legal" not in at.query_params


def test_invalid_password_reset_link_screen_has_a_way_back():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["recovery_token"] = "expired-or-bogus-token"
    at.run()
    assert not at.exception
    back_buttons = [b for b in at.button if b.key == "password_reset_screen_back"]
    assert back_buttons, "Password reset screen should have a way back to the app"
    back_buttons[0].click().run()
    assert not at.exception
    assert "recovery_token" not in at.query_params


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


def test_my_inventory_hides_sold_listings_by_default():
    # Additional suggestion from the Patti Hansen UX review: "allow
    # completed listings to be archived or hidden" -- My Inventory used to
    # show every listing forever in one flat table, so a seller's Sold
    # history permanently cluttered the view with no way to get it out of
    # the way. Sold/removed listings should now be hidden by default,
    # behind a "Show sold/removed listings" checkbox.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = _new_isolated_seller(hw_app, "Archive Test Seller")
    live_id = _new_isolated_product(hw_app, seller_id, "Still For Sale")
    sold_id = _new_isolated_product(hw_app, seller_id, "Already Sold")
    hw_app.run("UPDATE products SET listing_status='Sold' WHERE id=?", (sold_id,))

    at.session_state["seller_tool_seller_id"] = seller_id
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("My Inventory").run()
    assert not at.exception

    listing_ids = [str(i) for i in at.selectbox(key="primary_my_inventory_listing_id").options]
    assert str(live_id) in listing_ids, "Live listing should be visible by default"
    assert str(sold_id) not in listing_ids, "Sold listing should be hidden by default"

    checkboxes = [c for c in at.checkbox if c.key == "primary_my_inventory_show_sold"]
    assert checkboxes, "Expected a 'Show sold/removed listings' checkbox"
    checkboxes[0].set_value(True).run()

    listing_ids = [str(i) for i in at.selectbox(key="primary_my_inventory_listing_id").options]
    assert str(sold_id) in listing_ids, "Sold listing should appear once the checkbox is checked"


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


def _new_isolated_seller(hw_app, store_name):
    # ensure_seller() reuses whatever seller row already exists in the
    # shared SQLite file (same reasoning as _new_isolated_product below).
    # Give each test needing its own seller/inventory a dedicated row.
    email = store_name.lower().replace(" ", "-") + "@example.com"
    data = {'store_name': store_name, 'owner_name': 'Test Owner', 'email': email, 'phone': '', 'city': '', 'state': '', 'website': '', 'instagram': '', 'store_bio': '', 'seller_story': '', 'specialties': '', 'logo_url': '', 'banner_url': '', 'status': 'Approved Seller', 'seller_level': 'Verified Seller', 'rating': 100, 'completed_sales': 0, 'disputes': 0, 'strikes': 0, 'auction_override': 'Yes', 'access_code': '', 'created_at': hw_app.now()}
    keys = list(data.keys())
    placeholders = ",".join("?" for _ in keys)
    hw_app.run(f"INSERT INTO sellers({','.join(keys)}) VALUES({placeholders})", tuple(data[k] for k in keys))
    return int(hw_app.df("SELECT id FROM sellers WHERE email=? ORDER BY id DESC LIMIT 1", (email,)).iloc[0]['id'])


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


# ---------- Admin content must not leak into consumer-facing pages via the public Testing Mode toggle ----------

def test_founder_knowledge_section_requires_real_admin_not_just_testing_mode():
    # Founder: "make sure the admin side does not mix with consumer side."
    # The Knowledge Hub is a public, consumer-facing page -- but its "Admin /
    # Founder Knowledge" section (funding roadmap, launch wedge notes) was
    # gated by is_admin_unlocked(), which any anonymous visitor can trigger
    # via the public Testing Mode toggle with no real login. It must require
    # real admin auth (is_admin_user()) instead.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Knowledge Hub")
    assert not at.exception

    all_text = [m.value for m in at.markdown]
    assert not any("Admin / Founder Knowledge" in t for t in all_text), (
        "Testing mode alone (no real admin login) should not unlock founder/business content on a public page"
    )
    assert not any("funding roadmap" in t.lower() for t in all_text), (
        "Business-sensitive content should not be reachable via the public Testing Mode toggle"
    )


# ---------- Buyer/seller trust tier (founder: grade based on volume + averaged feedback) ----------

def test_trust_tier_gates_silver_and_gold_behind_a_real_average():
    # Founder: "grade based on how many items they buy and sell... averaged
    # based on your feedback and reviews." Design constraint from the
    # follow-up discussion: volume alone must not be enough to reach
    # Silver/Gold -- a high-volume account with a mediocre average should
    # stay capped at Bronze.
    import app as hw_app

    assert hw_app.compute_trust_tier(0, None) == "New"
    assert hw_app.compute_trust_tier(0, {"average": 5.0, "count": 3}) == "New", (
        "Zero completed transactions should be New regardless of review average"
    )
    assert hw_app.compute_trust_tier(1, None) == "Bronze", "Any completed transaction with no reviews yet should be Bronze"
    assert hw_app.compute_trust_tier(25, {"average": 2.0, "count": 25}) == "Bronze", (
        "High volume with a poor average must NOT reach Silver/Gold"
    )
    assert hw_app.compute_trust_tier(3, {"average": 5.0, "count": 3}) == "Bronze", (
        "A perfect average with too few transactions should not reach Silver yet"
    )
    assert hw_app.compute_trust_tier(5, {"average": 4.0, "count": 5}) == "Silver"
    assert hw_app.compute_trust_tier(19, {"average": 5.0, "count": 19}) == "Silver", (
        "Just under the Gold volume threshold should stay Silver even with a perfect average"
    )
    assert hw_app.compute_trust_tier(20, {"average": 4.5, "count": 20}) == "Gold"
    assert hw_app.compute_trust_tier(20, {"average": 4.4, "count": 20}) == "Silver", (
        "Just under the Gold average threshold should stay Silver even at high volume"
    )


def test_seller_profile_shows_real_trust_tier_not_static_fake_rating():
    # The old "Rating {s['rating']}%" caption was a static field set to 100
    # at seller creation and never recalculated by anything -- a fake number
    # sitting next to the real review average shown further down the same
    # page. It should be gone, replaced by the real tier/average.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    goto(at, "Seller Stores", area_key="marketplace_navigation")
    at.session_state["seller_id"] = int(seller_id)
    at.run()
    assert not at.exception

    all_text = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert not any("Rating 100%" in t for t in all_text), "Static fake rating should be gone"
    assert any(">New Seller<" in t or ">Bronze Seller<" in t for t in all_text), (
        f"Expected a real trust-tier badge, got: {[t for t in all_text if 'Seller' in t]}"
    )
    assert any("completed seller transaction" in t for t in all_text), "Expected the real transaction-count caption"


def test_seller_can_review_buyer_after_sale_and_it_feeds_the_buyers_tier():
    # New capability: sellers previously had no way to review a buyer at all
    # (only buyer -> seller reviews existed). This is the seller-side mirror,
    # and it should be reflected the next time that buyer's tier is computed.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    buyer_id = hw_app.ensure_buyer()
    product_id = _new_isolated_product(hw_app, seller_id, "Buyer Review Test Album")
    hw_app.run(
        "INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        (product_id, seller_id, buyer_id, "Review Test Buyer", "reviewtest@example.com", "Sold", hw_app.now(), hw_app.now()),
    )

    assert hw_app.buyer_review_summary(buyer_id) is None, "Should start with no buyer reviews"

    at.session_state["seller_tool_seller_id"] = seller_id
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Buyer Requests").run()
    assert not at.exception

    rating_slider = next(s for s in at.slider if s.key and s.key.startswith("buyer_review_rating_"))
    rating_slider.set_value(4).run()
    submit_button = next(b for b in at.button if b.key and b.key.startswith("FormSubmitter:buyer_review_form_"))
    submit_button.click().run()
    assert not at.exception

    summary = hw_app.buyer_review_summary(buyer_id)
    assert summary is not None, "Expected a buyer review to have been saved"
    assert summary["average"] == 4.0
    assert summary["count"] == 1
    assert hw_app.compute_trust_tier(hw_app.buyer_completed_purchases_count(buyer_id), summary) == "Bronze"


# ---------- Buy Now removal + redundant Verified Seller badge removal (founder feedback) ----------

def test_buy_button_is_gone_from_search_music_and_product_detail():
    # Founder: "Buy is the same thing as add to cart for me. That can go."
    # Buy Now was removed as a purchase path -- Add to Cart is now the only
    # one. Regression guard against it creeping back in.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Buy Removal Test Album")

    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception

    button_keys = [b.key for b in at.button if b.key]
    assert any(k.startswith("item_") for k in button_keys), "Expected the seeded listing card to actually render"
    assert not any(k.startswith("buy_request_item_") for k in button_keys), "Buy button should be gone from listing cards"
    button_labels = [b.proto.label for b in at.button]
    assert "Buy" not in button_labels, f"Unexpected 'Buy' button still present: {button_labels}"

    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception
    detail_button_keys = [b.key for b in at.button if b.key]
    assert not any("purchase" in k.lower() for k in detail_button_keys), f"Unexpected purchase-related button on product_detail: {detail_button_keys}"


def test_verified_seller_badge_is_gone():
    # Founder: "Verified seller can go as well. That is redundant. If you
    # are on here with postings, that means you can sell."
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    _new_isolated_product(hw_app, seller_id, "Verified Badge Removal Test Album")

    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception
    all_text = [m.value for m in at.markdown]
    assert any("Verified Badge Removal Test Album" in t for t in all_text), "Expected the seeded listing card to actually render"
    assert not any("Verified Seller" in t for t in all_text), "Verified Seller badge should no longer render"

    goto(at, "Seller Stores", area_key="marketplace_navigation")
    at.session_state["seller_id"] = int(seller_id)
    at.run()
    assert not at.exception
    all_text = [m.value for m in at.markdown]
    assert not any("Verified Seller" in t for t in all_text), "Verified Seller badge should not render on a seller's public profile"


def test_listing_card_has_no_live_badge_or_reference_image_label():
    # Founder: "Showing the listing is live needs to go too, we know it's by
    # it being there" and "Reference photo label needs to go but leave the
    # photo, take away the words." The photo itself (and genuinely useful
    # negative signals like Pending/Sold) should still render.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Live Badge Removal Test Album")

    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception
    all_text = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert any("Live Badge Removal Test Album" in t for t in all_text), "Expected the seeded listing card to actually render"
    assert not any(">Live<" in t for t in all_text), "Redundant 'Live' badge should be gone"
    assert not any("Reference image" in t for t in all_text), "'Reference image' label should be gone"

    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception
    detail_text = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert not any("Reference image" in t for t in detail_text), "'Reference image' label should be gone from product detail too"


def test_seller_profile_has_no_auto_trust_badges():
    # Founder: "profile complete, Approved Listing, Quality Listing trusted
    # seller button can all go" -- these are the buyer-facing auto-generated
    # badges from render_seller_trust_badges(sid, 'public'). The seller's own
    # dashboard self-diagnostic view (context='seller') is a different call
    # site and should be unaffected. Note: "New Seller" is NOT in this list
    # -- that's now a legitimate label from the new real trust-tier system
    # (render_trust_tier), coincidentally reusing wording from the old fake
    # heuristic badges this test guards against.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    _new_isolated_product(hw_app, seller_id, "Trust Badge Removal Test Album")

    goto(at, "Seller Stores", area_key="marketplace_navigation")
    at.session_state["seller_id"] = int(seller_id)
    at.run()
    assert not at.exception
    all_text = [m.value for m in at.markdown]
    for phrase in ["Profile Complete", "Approved Listings", "Quality Listings", "Trusted Seller"]:
        assert not any(phrase in t for t in all_text), f"Expected '{phrase}' badge to be gone from the public seller profile"


def test_signed_out_ask_seller_explains_why_youre_on_the_sign_in_page():
    # Founder reported "Ask the seller doesn't work" -- root cause: clicking
    # Ask Seller while signed out silently redirects to a bare Sign In form
    # with zero context, which reads as the button doing nothing. Sign in
    # should now explain what it's resuming.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    _new_isolated_product(hw_app, seller_id, "Ask Seller Redirect Test Album")

    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception

    ask_button = next(b for b in at.button if b.key and b.key.startswith("ask_item_"))
    ask_button.click().run()
    assert not at.exception

    nav = at.session_state["marketplace_navigation"] if "marketplace_navigation" in at.session_state else None
    assert nav == "My Account", "Expected the redirect to My Account"
    infos = [i.value for i in at.info]
    assert any("ask the seller" in i.lower() for i in infos), f"Expected a contextual sign-in message, got {infos}"


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


# ---------- Cart (slice 3/4: cart page + checkout) ----------

def test_checkout_creates_seller_accepted_purchase_requests_and_reserves_listings():
    # Checking out one seller's cart group should be the multi-item version
    # of Buy Now: each item becomes a purchase_requests row straight at
    # 'Seller Accepted' with a ~5-day payment_due_at, each product is
    # reserved (Pending Pickup/Payment), and only THAT seller's cart_items
    # rows are consumed -- an item from a different seller in the same cart
    # must be left untouched, proving checkout is scoped per seller-group.
    import app as hw_app
    from datetime import datetime as _dt
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"

    buyer_id = _new_isolated_buyer(hw_app, "checkout_test_buyer")
    seller_a = hw_app.ensure_seller()
    hw_app.run(
        '''INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        ('Checkout Test Seller B', 'Owner B', 'checkout-seller-b@example.com', '', '', '', '', '', '', '', '', '', '', 'Approved Seller', 'Verified Seller', 100, 0, 0, 0, 'Yes', '', hw_app.now()),
    )
    seller_b = int(hw_app.df("SELECT id FROM sellers WHERE email=?", ('checkout-seller-b@example.com',)).iloc[0]['id'])

    product_a1 = _new_isolated_product(hw_app, seller_a, "Checkout Seller A Item 1")
    product_a2 = _new_isolated_product(hw_app, seller_a, "Checkout Seller A Item 2")
    product_b1 = _new_isolated_product(hw_app, seller_b, "Checkout Seller B Item 1")

    for pid, sid in [(product_a1, seller_a), (product_a2, seller_a), (product_b1, seller_b)]:
        hw_app.run(
            "INSERT INTO cart_items(buyer_id,product_id,seller_id,added_price,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (buyer_id, pid, sid, 24.99, hw_app.now(), hw_app.now()),
        )

    cart_a_rows = hw_app.df("SELECT id,product_id FROM cart_items WHERE buyer_id=? AND seller_id=?", (buyer_id, seller_a))
    result = hw_app.checkout_seller_cart_group(buyer_id, seller_a, cart_a_rows.to_dict("records"))

    assert len(result["created_purchase_request_ids"]) == 2, result
    assert result["skipped"] == [], result

    prs = hw_app.df("SELECT * FROM purchase_requests WHERE buyer_id=? AND seller_id=?", (buyer_id, seller_a))
    assert len(prs) == 2
    for _, pr in prs.iterrows():
        assert pr["status"] == "Seller Accepted", pr["status"]
        assert pr["payment_due_at"], "Expected payment_due_at to be set"
        days_out = (_dt.fromisoformat(pr["payment_due_at"]) - _dt.now()).total_seconds() / 86400
        assert 4.9 <= days_out <= 5.1, f"Expected ~5 days out, got {days_out:.2f}"

    for pid in (product_a1, product_a2):
        status = hw_app.df("SELECT listing_status FROM products WHERE id=?", (pid,)).iloc[0]["listing_status"]
        assert status == "Pending Pickup/Payment", f"product {pid} status={status}"

    remaining_cart = hw_app.df("SELECT * FROM cart_items WHERE buyer_id=?", (buyer_id,))
    assert len(remaining_cart) == 1, f"Expected only seller B's item left in cart, got {len(remaining_cart)} rows"
    assert int(remaining_cart.iloc[0]["product_id"]) == product_b1


def test_checkout_skips_item_bought_out_from_under_buyer():
    # Simulate another buyer beating this one to an item between it being
    # added to the cart and checkout: the sold item should be reported under
    # `skipped` with a reason (not silently dropped) and stay in the cart,
    # while the still-available sibling item in the same seller group still
    # succeeds normally.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"

    buyer_id = _new_isolated_buyer(hw_app, "checkout_skip_test_buyer")
    seller_id = hw_app.ensure_seller()
    product_ok = _new_isolated_product(hw_app, seller_id, "Checkout Skip Test Still Available")
    product_sold = _new_isolated_product(hw_app, seller_id, "Checkout Skip Test Already Sold")

    for pid in (product_ok, product_sold):
        hw_app.run(
            "INSERT INTO cart_items(buyer_id,product_id,seller_id,added_price,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (buyer_id, pid, seller_id, 24.99, hw_app.now(), hw_app.now()),
        )
    hw_app.run("UPDATE products SET listing_status='Sold' WHERE id=?", (product_sold,))

    cart_rows = hw_app.df("SELECT id,product_id FROM cart_items WHERE buyer_id=? AND seller_id=?", (buyer_id, seller_id))
    result = hw_app.checkout_seller_cart_group(buyer_id, seller_id, cart_rows.to_dict("records"))

    assert len(result["created_purchase_request_ids"]) == 1, result
    assert len(result["skipped"]) == 1, result
    assert result["skipped"][0]["product_id"] == product_sold

    remaining_cart = hw_app.df("SELECT product_id FROM cart_items WHERE buyer_id=?", (buyer_id,))
    assert list(remaining_cart["product_id"]) == [product_sold], (
        "Expected the sold item to remain in the cart and the purchased item to be gone"
    )

    prs = hw_app.df("SELECT product_id FROM purchase_requests WHERE buyer_id=?", (buyer_id,))
    assert list(prs["product_id"]) == [product_ok]


def test_cart_page_shows_unavailable_item_without_crashing():
    # A cart can sit untouched for days -- the listing it points to may have
    # sold, been hidden, or been removed since it was added. The Cart page
    # should surface that clearly instead of raising.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = _new_isolated_buyer(hw_app, "cart_unavailable_test_buyer")
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Cart Unavailable Test Album")
    hw_app.run(
        "INSERT INTO cart_items(buyer_id,product_id,seller_id,added_price,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (buyer_id, product_id, seller_id, 24.99, hw_app.now(), hw_app.now()),
    )
    hw_app.run("UPDATE products SET listing_status='Sold' WHERE id=?", (product_id,))

    buyer = hw_app.get_buyer(buyer_id)
    _real_buyer_session(at, hw_app, buyer_id, buyer["email"])
    goto(at, "Cart", area_key="marketplace_navigation")
    assert not at.exception, at.exception

    warnings = [w.value for w in at.warning]
    assert any("no longer available" in w.lower() for w in warnings), (
        f"Expected an unavailable-listing message, got warnings={warnings}"
    )


def test_checkout_confirmation_still_shows_after_cart_group_empties():
    # Regression guard: a seller's cart group disappears the instant checkout
    # succeeds (its items just left cart_items) -- render_seller_cart_group()
    # is only called for groups still present in the cart, so the very
    # success message checkout was supposed to produce never rendered. Caught
    # by hand in a live browser check, not by the direct-function checkout
    # tests above (which don't exercise the page's post-checkout render at
    # all). Clicking Checkout on the Cart page should show a confirmation
    # even though the group it was for is now gone.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = _new_isolated_buyer(hw_app, "checkout_confirmation_test_buyer")
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Checkout Confirmation Test Album")
    hw_app.run(
        "INSERT INTO cart_items(buyer_id,product_id,seller_id,added_price,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (buyer_id, product_id, seller_id, 24.99, hw_app.now(), hw_app.now()),
    )

    buyer = hw_app.get_buyer(buyer_id)
    _real_buyer_session(at, hw_app, buyer_id, buyer["email"])
    goto(at, "Cart", area_key="marketplace_navigation")
    assert not at.exception, at.exception

    checkout_button = next(b for b in at.button if b.key == f"cart_checkout_{seller_id}")
    checkout_button.click().run()
    assert not at.exception, at.exception

    successes = [s.value for s in at.success]
    assert any("Bought 1 item" in s for s in successes), (
        f"Expected a post-checkout confirmation to survive the now-empty cart group, got successes={successes}"
    )
    assert hw_app.df("SELECT * FROM cart_items WHERE buyer_id=?", (buyer_id,)).empty
    assert hw_app.df("SELECT * FROM purchase_requests WHERE buyer_id=? AND product_id=?", (buyer_id, product_id)).iloc[0]["status"] == "Seller Accepted"


# ---------- Cart (slice 5: combined per-seller payment) ----------

def test_seller_ready_to_pay_groups_combines_multiple_items_into_one_total():
    # The actual point of a cart, per Discogs: pay once per seller, not once
    # per item. Three purchase_requests for the same buyer+seller, each tied
    # to a different-priced product, should collapse into exactly one group
    # whose total is the sum of all three -- not three separate line items.
    # This is also the test that exercises the buyer_activity_tables()
    # local-SQL fix (it was missing p.price, so every total silently came
    # out to $0.00 in local/test mode before that fix).
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"

    buyer_id = _new_isolated_buyer(hw_app, "combined_payment_test_buyer")
    seller_id = hw_app.ensure_seller()
    prices = [24.99, 15.00, 40.50]
    for i, price in enumerate(prices):
        product_id = _new_isolated_product(hw_app, seller_id, f"Combined Payment Test Album {i}")
        hw_app.run("UPDATE products SET price=? WHERE id=?", (price, product_id))
        hw_app.run(
            "INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,status,payment_due_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (product_id, seller_id, buyer_id, "Combined Test Buyer", "combined@example.com", "Seller Accepted", hw_app.payment_due_at_string(), hw_app.now(), hw_app.now()),
        )

    groups = hw_app.seller_ready_to_pay_groups(buyer_id)
    assert len(groups) == 1, f"Expected exactly one seller group, got {len(groups)}"
    group = groups[0]
    assert group["seller_id"] == seller_id
    assert len(group["line_items"]) == 3, group["line_items"]
    assert group["total"] == round(sum(prices), 2), f"Expected combined total {sum(prices)}, got {group['total']}"


def test_my_orders_shows_one_combined_payment_per_seller_not_per_item():
    # Full page-level check: two Seller Accepted orders from the same seller
    # should render as ONE "Pay the seller" payment line under My Account ->
    # My Orders -> Ready to pay, not two.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    buyer_id = _new_isolated_buyer(hw_app, "my_orders_combined_test_buyer")
    seller_id = hw_app.ensure_seller()
    for i in range(2):
        product_id = _new_isolated_product(hw_app, seller_id, f"My Orders Combined Test Album {i}")
        hw_app.run(
            "INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,status,payment_due_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (product_id, seller_id, buyer_id, "My Orders Test Buyer", "myorders@example.com", "Seller Accepted", hw_app.payment_due_at_string(), hw_app.now(), hw_app.now()),
        )

    hw_app.run("UPDATE sellers SET paypal_link=? WHERE id=?", ("seller@paypal.example.com", seller_id))

    buyer = hw_app.get_buyer(buyer_id)
    _real_buyer_session(at, hw_app, buyer_id, buyer["email"])
    goto(at, "My Account", area_key="marketplace_navigation")
    assert not at.exception, at.exception

    writes = [m.value for m in at.markdown]
    total_lines = [w for w in writes if w.startswith("**Total:")]
    assert len(total_lines) == 1, f"Expected exactly one combined total line for this seller, got {total_lines}"
    assert "49.98" in total_lines[0], (
        f"Expected the combined total of both items ($24.99 demo price each = $49.98), got {total_lines[0]}"
    )


def test_mobile_quick_nav_bar_includes_cart():
    # Regression guard: mobile_navigation_bar() (the "Go to" quick-nav row
    # shown at the top of every page) keeps its own hardcoded button list,
    # entirely separate from the sidebar's marketplace_menu -- adding 'Cart'
    # to the sidebar list earlier did nothing for this bar, so the Cart page
    # was unreachable from the prominent top-of-page nav that most people,
    # especially on mobile, actually use.
    import app as hw_app
    at = fresh_app()
    goto(at, "Home")
    assert not at.exception, at.exception

    cart_buttons = [b for b in at.button if b.key == "mobile_nav_cart"]
    assert len(cart_buttons) == 1, f"Expected exactly one Cart button in the mobile quick-nav, got {len(cart_buttons)}"

    cart_buttons[0].click().run()
    assert not at.exception, at.exception
    headers = [h.value for h in at.header]
    assert any("My Cart" in h for h in headers), f"Expected the Cart button to navigate to the Cart page, got headers={headers}"


def test_knowledge_hub_does_not_point_public_visitors_at_hidden_tester_section():
    # The Knowledge Hub is a public, consumer-facing page. It carried an
    # unconditional caption pointing every visitor at "Tester Start Here" on
    # the Home page -- but that section only renders for is_admin_unlocked(),
    # so a real customer got sent looking for something they can't see. The
    # caption should only appear for admin/testing-mode visitors, same as the
    # section it references.
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception

    all_text = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert not any("Tester Start Here" in t for t in all_text), (
        "Public visitors should not be told about the admin-only Tester Start Here section"
    )


# ---------- Knowledge Hub AI research queue (founder: grow the Knowledge Hub daily via web research, reviewed before publish) ----------

def test_ai_research_queue_publish_flow():
    # A scheduled job (scripts/knowledge_hub_researcher.py) drafts one new
    # Knowledge Hub article a day via Claude + live web search, saved as
    # status='Draft', source_type='AI Research' -- never auto-published.
    # This guards the admin review queue: a pending draft shows up for
    # review, Publish flips it live, and it then actually reaches the
    # public-facing Knowledge Hub under its own byline.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    ts = hw_app.now()
    hw_app.run(
        """INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,source_type,sources,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("AI Research Queue Test Article", "Genre Education", "Collectors", "Beginner",
         "Test summary.", "Test body.", "Test tip.", "Draft", "No", "AI Research",
         "Example Source — https://example.com", ts, ts),
    )
    pid = int(hw_app.df("SELECT id FROM knowledge_posts WHERE title='AI Research Queue Test Article'").iloc[0]["id"])

    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Content Admin").run()
    assert not at.exception, at.exception

    title_inputs = [t for t in at.text_input if t.key == f"aiq_title_{pid}"]
    assert len(title_inputs) == 1, "Expected the pending AI draft to show up in the review queue"
    assert title_inputs[0].value == "AI Research Queue Test Article"

    publish_buttons = [b for b in at.button if b.key == f"aiq_publish_{pid}"]
    assert len(publish_buttons) == 1, "Expected a Publish button for the pending draft"
    publish_buttons[0].click().run()
    assert not at.exception, at.exception

    row = hw_app.df("SELECT status FROM knowledge_posts WHERE id=?", (pid,)).iloc[0]
    assert row["status"] == "Published", "Publish should flip the draft to Published"

    at2 = fresh_app()
    goto(at2, "Knowledge Hub")
    assert not at2.exception, at2.exception
    headings = [s.value for s in at2.subheader]
    assert any("AI Research Queue Test Article" in h for h in headings), (
        "Published AI-researched article should now appear on the public Knowledge Hub"
    )


def test_ai_research_queue_reject_deletes_draft():
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    ts = hw_app.now()
    hw_app.run(
        """INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,source_type,sources,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("AI Research Queue Reject Test Article", "Genre Education", "Collectors", "Beginner",
         "Test summary.", "Test body.", "Test tip.", "Draft", "No", "AI Research",
         "", ts, ts),
    )
    pid = int(hw_app.df("SELECT id FROM knowledge_posts WHERE title='AI Research Queue Reject Test Article'").iloc[0]["id"])

    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Content Admin").run()
    assert not at.exception, at.exception

    reject_buttons = [b for b in at.button if b.key == f"aiq_reject_{pid}"]
    assert len(reject_buttons) == 1
    reject_buttons[0].click().run()
    assert not at.exception, at.exception

    remaining = hw_app.df("SELECT id FROM knowledge_posts WHERE id=?", (pid,))
    assert remaining.empty, "Reject should delete the draft"


# ---------- Shared release photo library (founder: reuse photos across future listings of the same release) ----------

def test_photo_library_reuses_photo_across_listings_by_barcode():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    hw_app.photo_library_save("602547234567", "Test Artist", "Test Album", "https://example.com/cover.jpg", "Release Art")
    found = hw_app.photo_library_lookup("602547234567", "Different Artist Typed", "Different Title Typed")
    assert found == "https://example.com/cover.jpg", (
        "A later listing with the same barcode should reuse the cached photo even if the artist/title text differs"
    )


def test_photo_library_falls_back_to_artist_title_when_no_barcode():
    import app as hw_app
    hw_app.photo_library_save("", "Some Artist", "Some Album", "https://example.com/seller-photo.jpg", "Seller Photo", 5)
    found = hw_app.photo_library_lookup("", "some artist", "some album")
    assert found == "https://example.com/seller-photo.jpg", "Lookup should match on artist/title case-insensitively when there's no barcode"


def test_photo_library_prefers_official_release_art_over_seller_photo():
    import app as hw_app
    hw_app.photo_library_save("999888777", "Pref Artist", "Pref Album", "https://example.com/seller.jpg", "Seller Photo", 1)
    hw_app.photo_library_save("999888777", "Pref Artist", "Pref Album", "https://example.com/official.jpg", "Release Art")
    found = hw_app.photo_library_lookup("999888777", "Pref Artist", "Pref Album")
    assert found == "https://example.com/official.jpg", (
        "Official release art should be preferred over a seller's own photo when both are cached for the same release"
    )


def test_upload_product_prefills_reference_image_from_photo_library():
    # End-to-end guard: a photo cached from an earlier listing should actually
    # reach the Add Inventory "Reference image" field, not just the helper
    # functions in isolation.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    hw_app.photo_library_save("111222333444", "Library Artist", "Library Album", "https://example.com/from-library.jpg", "Release Art")

    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert not at.exception, at.exception

    artist_input = next(t for t in at.text_input if t.key and t.key.startswith("upload_live_artist_"))
    artist_input.set_value("Library Artist").run()
    title_input = next(t for t in at.text_input if t.key and t.key.startswith("upload_live_title_"))
    title_input.set_value("Library Album").run()
    barcode_input = next(t for t in at.text_input if (t.label or "").startswith("Barcode / UPC / EAN"))
    barcode_input.set_value("111222333444").run()
    assert not at.exception, at.exception

    ref_image_input = next(t for t in at.text_input if (t.label or "").startswith("Reference image"))
    assert ref_image_input.value == "https://example.com/from-library.jpg", (
        "Reference image should auto-fill from the photo library once artist/title/barcode match a cached entry"
    )


# ---------- Support / Contact page (founder: replace/supplement the per-listing Report button with a general support path) ----------

def test_support_page_reachable_via_query_param_and_has_a_way_back():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["support"] = "1"
    at.run()
    assert not at.exception, at.exception
    headers = [h.value for h in at.header]
    assert any("Support" in h for h in headers), "Expected the Support page to render"
    back_buttons = [b for b in at.button if b.key == "support_back"]
    assert back_buttons, "Support screen should have a way back to the app"
    back_buttons[0].click().run()
    assert not at.exception, at.exception
    assert "support" not in at.query_params


def test_support_request_submission_saves_and_shows_in_admin_queue():
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["support"] = "1"
    at.run()
    assert not at.exception, at.exception

    name_input = next(t for t in at.text_input if (t.label or "").startswith("Your name"))
    name_input.set_value("Test Person").run()
    email_input = next(t for t in at.text_input if (t.label or "").startswith("Your email"))
    email_input.set_value("test@example.com").run()
    message_input = next(t for t in at.text_area if (t.label or "").startswith("Tell us what is going on"))
    message_input.set_value("Cannot find my order confirmation.").run()
    submit_buttons = [b for b in at.button if (b.label or "") == "Send to House Of Wax"]
    assert submit_buttons, "Expected the support form submit button"
    submit_buttons[0].click().run()
    assert not at.exception, at.exception

    saved = hw_app.df("SELECT * FROM support_requests WHERE email='test@example.com'")
    assert len(saved) == 1, "Expected exactly one saved support request"
    assert saved.iloc[0]["message"] == "Cannot find my order confirmation."
    assert saved.iloc[0]["status"] == "Open"

    at2 = AppTest.from_file("app.py", default_timeout=30)
    at2.session_state["testing_mode_enabled"] = True
    at2.run()
    at2.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at2.sidebar.radio(key="admin_navigation").set_value("Support Requests").run()
    assert not at2.exception, at2.exception
    all_text = [m.value for m in at2.markdown]
    assert any("Cannot find my order confirmation." in t for t in all_text), (
        "Submitted support request should show up in the admin Support Requests queue"
    )


def test_insert_only_tables_use_return_minimal_not_representation(monkeypatch):
    # Regression guard: support_requests and release_photo_library both have
    # an anon/authenticated INSERT policy but deliberately no matching SELECT
    # policy (visitors shouldn't browse each other's submissions; the photo
    # library isn't meant to be queried row-by-row from the client). Without
    # being in INSERT_ONLY_NO_READBACK_TABLES, hosted_insert() defaults to
    # Prefer: return=representation, which asks Postgres to SELECT the row
    # back as part of the same statement -- that SELECT fails RLS, and
    # Postgres reports the *entire* insert as a row-level-security violation
    # even though (in Postgres generally) the write would otherwise have
    # gone through. This bug shipped once already (V25.43.135) and was hard
    # to diagnose live, because every other layer -- the policy itself,
    # `set role anon` in the SQL editor, table exposure, schema cache -- was
    # correct; only the Prefer header was wrong. Guard it so it can't ship
    # silently again for any future insert-only, no-readback table.
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    monkeypatch.setattr(hw_app, "supabase_config", lambda: ("https://example.invalid", "fake-anon-key"))
    monkeypatch.setattr(hw_app, "auth_access_token", lambda: "")

    captured_headers = {}

    class FakeResponse:
        status_code = 200
        ok = True
        text = "[]"
        def json(self):
            return []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        captured_headers["Prefer"] = (headers or {}).get("Prefer")
        return FakeResponse()

    monkeypatch.setattr(hw_app.requests, "request", fake_request)

    for table in ["support_requests", "release_photo_library", "tester_feedback", "listing_reports"]:
        assert table in hw_app.INSERT_ONLY_NO_READBACK_TABLES, (
            f"{table} has an insert policy but no anon/authenticated SELECT policy -- "
            "it must be in INSERT_ONLY_NO_READBACK_TABLES or inserts will fail with a "
            "misleading RLS error even though the policy itself is correct"
        )
        captured_headers.clear()
        hw_app.hosted_insert(table, {"created_at": "now"})
        assert captured_headers.get("Prefer") == "return=minimal", (
            f"Expected {table} insert to use Prefer: return=minimal, got {captured_headers.get('Prefer')!r}"
        )


# ---------- Glossary (founder: "it's blank and should show terms to get people clicking and wanting to learn") ----------

def test_glossary_shows_terms_without_needing_to_click():
    # Regression/design guard: the glossary used to be a plain list of
    # collapsed st.expander rows under a bare "Collector glossary" heading --
    # nothing was visible until a visitor already knew a term to search for
    # or clicked one open blind. Term name and definition should render
    # directly in a visible card.
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    markdown_text = [m.value for m in at.markdown]
    assert any("**Catalog Number**" in t for t in markdown_text), (
        "Expected the glossary term name to render directly as visible bold text, not hidden behind a click"
    )


def test_glossary_search_and_category_filter_narrow_results():
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception

    search_inputs = [t for t in at.text_input if (t.label or "") == "Search glossary"]
    assert search_inputs, "Expected a glossary search box"
    search_inputs[0].set_value("runout").run()
    assert not at.exception, at.exception
    markdown_text = [m.value for m in at.markdown]
    assert any("Matrix / Runout" in t for t in markdown_text)
    assert not any("Reissue" in t for t in markdown_text), "Search should narrow out non-matching terms"


# ---------- Add Inventory barcode-match cleanup (founder: artist/title didn't auto-fill, no price suggestion, remove SKU/None-of-these/External URL) ----------

def test_use_this_release_fills_sticky_artist_title_fields():
    # Regression guard: Artist/Title live outside st.form with explicit
    # widget keys (upload_live_artist_*/upload_live_title_*) so the price box
    # can react live to typing -- but a keyed Streamlit widget is "sticky"
    # and ignores a fresh value= once that key already holds a stored value.
    # Clicking "Use recommended match" updated v24_autofill_listing (so most
    # fields refreshed correctly) but never touched the artist/title keys
    # directly, so those two fields -- and the price suggestion, which is
    # gated on artist being non-empty -- stayed blank after picking a match.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert not at.exception, at.exception

    # Touch the sticky keys first, same as a fresh page load would (empty),
    # to prove the fix re-fills them rather than happening to work only
    # because they were never rendered yet.
    assert "upload_live_artist_primary_add_inventory" in at.session_state
    assert "upload_live_title_primary_add_inventory" in at.session_state

    fake_match = {
        "artist": "USA For Africa", "title": "We Are the World", "barcode": "4988005678901",
        "format": "Vinyl", "label": "Columbia", "release_year": "1985", "genre": "Pop",
        "catalog_number": "CAT123", "image_url": "", "external_url": "https://www.discogs.com/release/123",
        "source": "Discogs", "country": "US",
    }
    at.session_state["v25_best_match_primary_add_inventory"] = fake_match
    at.run()
    assert not at.exception, at.exception

    use_buttons = [b for b in at.button if b.key == "use_recommended_match_primary_add_inventory"]
    assert use_buttons, "Expected a 'Use recommended match' button for the seeded match"
    use_buttons[0].click().run()
    assert not at.exception, at.exception

    assert at.session_state["upload_live_artist_primary_add_inventory"] == "USA For Africa"
    assert at.session_state["upload_live_title_primary_add_inventory"] == "We Are the World"
    artist_inputs = [t for t in at.text_input if t.key == "upload_live_artist_primary_add_inventory"]
    assert artist_inputs and artist_inputs[0].value == "USA For Africa", (
        "Artist field should show the picked release's artist, not stay blank"
    )


def test_none_of_these_button_removed_and_sku_field_removed():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert not at.exception, at.exception

    button_labels = [b.label for b in at.button]
    assert not any("None of these" in (l or "") for l in button_labels), (
        "Founder: remove the 'None of these - search another way' button"
    )
    input_labels = [t.label for t in at.text_input]
    assert not any((l or "").startswith("SKU") for l in input_labels), "Founder: remove the SKU field"
    assert not any("External release URL" in (l or "") for l in input_labels), (
        "External release URL should no longer be a seller-editable field"
    )


def test_product_detail_does_not_link_buyers_to_discogs():
    # Founder: "We are letting people leave us and go to a competitor site."
    # st.link_button isn't tracked by at.button -- AppTest exposes it only
    # via the generic at.get("link_button").
    import app as hw_app
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Discogs Link Removal Test Album")
    hw_app.run(
        "UPDATE products SET external_release_url=? WHERE id=?",
        ("https://www.discogs.com/release/33282990", product_id),
    )
    at = fresh_app()
    goto(at, "Search Music")
    at.session_state["product_id"] = product_id
    at.run()
    assert not at.exception, at.exception
    link_buttons = at.get("link_button")
    assert not any("View release info" in (lb.label or "") for lb in link_buttons), (
        "Product detail should not send buyers to an external release URL"
    )


def test_photo_library_save_omits_seller_id_when_none_given(monkeypatch):
    # Regression guard: source_seller_id references sellers(id) with no
    # NOT NULL constraint, but photo_library_save() defaulted a missing
    # seller_id to the integer 0 instead of NULL -- 0 is never a real seller
    # id, so every "Release Art" save (no seller involved) violated the
    # foreign key constraint and failed outright in production.
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    monkeypatch.setattr(hw_app, "supabase_config", lambda: ("https://example.invalid", "fake-anon-key"))
    monkeypatch.setattr(hw_app, "auth_access_token", lambda: "")

    captured = {}

    class FakeResponse:
        status_code = 200
        ok = True
        text = "[]"
        def json(self):
            return []

    def fake_request(method, url, headers=None, params=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(hw_app.requests, "request", fake_request)
    monkeypatch.setattr(hw_app, "hosted_select", lambda *a, **k: __import__("pandas").DataFrame())

    hw_app.photo_library_save("602547234567", "Some Artist", "Some Album", "https://example.com/cover.jpg", "Release Art")
    assert "source_seller_id" not in captured["payload"], (
        "source_seller_id should be omitted (letting Postgres store NULL) when no seller is involved, "
        f"got payload {captured['payload']!r}"
    )


def test_barcode_flow_is_a_single_unified_search_no_duplicate_ui():
    # Founder, second round of feedback (after V25.43.138 only fixed one of
    # two parallel barcode-match code paths): "I don't want any reference to
    # use best match. I still see the discogs link. Why is smart match button
    # still there? mark recommended match should be gone. use recommended
    # match or add your own is the only choices. I don't want to see this
    # Backup source links -- only if smart search fails" (i.e. don't always
    # show it). This guards against the whole class of duplicate-UI
    # regressions, not just the one path fixed in V25.43.138.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("Add Inventory").run()
    assert not at.exception, at.exception

    # No separate "Smart Search" trigger -- only one search button ("Search"
    # for barcode, "Search all music sources" for artist/title), both landing
    # on the same recommended-match card.
    button_labels = [b.label or "" for b in at.button]
    assert not any("Smart Search" in l for l in button_labels), (
        "Founder: 'Why is smart match button still there?' -- there should be only one unified search"
    )
    assert not any("Mark recommended match as wrong" in l or "wrong" in l.lower() for l in button_labels), (
        "Founder: 'mark recommended match should be gone'"
    )

    # Backup source links must not render before any search has been
    # attempted -- founder: "Backup source links -- only if smart search
    # fails", i.e. not shown unconditionally.
    markdown_text = " ".join(m.value or "" for m in at.markdown)
    assert "Backup source links" not in markdown_text, (
        "Backup source links should only appear after a search is attempted and finds nothing"
    )

    fake_match = {
        "artist": "USA For Africa", "title": "We Are the World", "barcode": "4988005678901",
        "format": "Vinyl", "label": "Columbia", "release_year": "1985", "genre": "Pop",
        "catalog_number": "CAT123", "image_url": "", "external_url": "https://www.discogs.com/release/123",
        "source": "Discogs", "country": "US",
    }
    at.session_state["v25_best_match_primary_add_inventory"] = fake_match
    at.session_state["v25_search_attempted_primary_add_inventory"] = True
    at.run()
    assert not at.exception, at.exception

    button_labels = [b.label or "" for b in at.button]
    only_two_choices = {"Use recommended match", "Enter manually"}
    match_card_buttons = [
        b for b in at.button
        if (b.key or "").endswith("_primary_add_inventory") and (b.key or "").startswith(("use_recommended_match", "enter_manually_recommended"))
    ]
    assert {b.label for b in match_card_buttons} <= only_two_choices, (
        f"Recommended match card should only offer 'Use recommended match' / 'Enter manually', got {[b.label for b in match_card_buttons]}"
    )
    assert not any("Smart Search" in l for l in button_labels)
    assert not any("wrong" in l.lower() for l in button_labels)

    markdown_text = " ".join(m.value or "" for m in at.markdown)
    write_text = " ".join(str(w.value) for w in at.get("text") if getattr(w, "value", None))
    combined = markdown_text + " " + write_text
    assert "discogs.com" not in combined.lower(), (
        "Founder: 'I still see the discogs link' -- the recommended match card should not show the Discogs source URL"
    )
    assert "Source URL" not in combined
    # A match was found, so backup links still should not render.
    assert "Backup source links" not in markdown_text

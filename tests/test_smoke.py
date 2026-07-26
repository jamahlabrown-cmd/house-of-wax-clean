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

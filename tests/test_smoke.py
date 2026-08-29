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
import uuid
import pytest
import pandas as pd

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


def test_home_page_has_seller_recruitment_cta():
    # Launch-readiness audit: Home had no seller-facing pitch or CTA at all
    # -- the sidebar copy literally called this "Simple buyer path," and a
    # prospective seller had to already know to dig into My Account to find
    # out selling exists. The founder's stated goal is going public
    # specifically to attract sellers, so this needs to be visible without
    # hunting, and needs to say what selling costs before they commit.
    at = fresh_app()
    subheaders = [s.value for s in at.subheader]
    assert any("crates" in s.lower() or "sell" in s.lower() for s in subheaders), (
        f"Expected a seller-facing CTA subheader on Home, got: {subheaders}"
    )
    all_text = " ".join(m.value for m in at.markdown)
    assert "%" in all_text and "PayPal" in all_text, (
        "Expected the Home page seller pitch to mention the platform fee and PayPal payout"
    )
    become_seller_buttons = [b for b in at.button if b.key == "home_become_seller_cta"]
    assert become_seller_buttons, "Expected a 'Become a Seller' button on Home"


def _element_order(at):
    # Flat, render-order walk of the page, used to check relative position
    # of elements that live in different typed collections (markdown vs
    # caption vs info) -- at.markdown / at.caption alone can't answer
    # "which one renders first."
    order = []
    for el in at.main:
        val = getattr(el, "value", None)
        order.append(str(val) if val is not None else "")
    return order


def test_home_hero_renders_above_breadcrumb_and_admin_banner():
    # Founder: "I would like to move [the hero brand block] to the top" --
    # so it's the literal first thing on the page, above the breadcrumb and
    # the admin-only version banner that used to precede it.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    assert not at.exception, at.exception

    order = _element_order(at)
    # 'class="how-hero"' (not just "how-hero") -- the CSS block earlier on
    # the page defines a `.how-hero { ... }` rule, which also contains the
    # substring "how-hero" and would otherwise match first by mistake.
    hero_idx = next(i for i, v in enumerate(order) if 'class="how-hero"' in v)
    breadcrumb_idx = next(i for i, v in enumerate(order) if "House Of Wax Marketplace" in v and "→" in v)
    banner_idx = next(i for i, v in enumerate(order) if v.startswith("Running V25.43"))

    assert hero_idx < breadcrumb_idx, "Hero should render above the breadcrumb"
    assert hero_idx < banner_idx, "Hero should render above the admin-only version banner"


def test_home_hero_renders_above_quick_nav_bar():
    # Founder: "I want [House Of Wax] to be the star of the show ... I want
    # it to be the first thing they see." The hero itself was already first
    # among home()'s own content, but the site-wide "### Go to" quick-nav bar
    # (mobile_navigation_bar()) ran BEFORE home() was even called, from the
    # main dispatch script -- making it the true first thing on the page.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception, at.exception

    order = _element_order(at)
    hero_idx = next(i for i, v in enumerate(order) if 'class="how-hero"' in v)
    go_to_idx = next(i for i, v in enumerate(order) if v.strip() == "### Go to")
    assert hero_idx < go_to_idx, "Hero should render above the quick-nav 'Go to' bar on Home"


def test_quick_nav_bar_still_renders_on_other_marketplace_pages():
    # Regression guard for the fix above -- only Home should have the quick
    # nav bar moved below its own content; every other marketplace page
    # (e.g. Search Music) should still show it exactly as before.
    at = fresh_app()
    goto(at, "Search Music")
    assert any(md.value.strip() == "### Go to" for md in at.markdown), (
        "Quick-nav bar should still render on non-Home marketplace pages"
    )


def test_home_page_has_no_content_count_stat_tiles():
    # Founder: the Knowledge Articles / Glossary Terms / Marketplace Items /
    # Sellers st.metric() tiles looked "tacky" -- a KPI-dashboard widget
    # sitting in the middle of an editorial/storefront page, before any real
    # content has been shown. Agreed direction: cut them from Home entirely
    # and let the actual content (featured story, listings, knowledge posts)
    # carry that signal instead.
    at = fresh_app()
    metric_labels = {m.label for m in at.metric}
    assert not metric_labels & {"Knowledge Articles", "Glossary Terms", "Marketplace Items", "Sellers"}, (
        f"Home page should have no content-count stat tiles, found {metric_labels}"
    )


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


def test_terms_of_service_discloses_buyer_non_payment_consequence():
    # Launch-readiness audit: the ToS "Buying and selling" section said
    # nothing about what happens if a buyer never pays after Buy Now
    # reserves an item -- only a general "no warranty" disclaimer covered
    # it. The real mechanism (payment_due_at + buyer strike, PAYMENT_WINDOW_
    # DAYS=5) already exists in the app; the policy text should say so.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["legal"] = "terms"
    at.run()
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert f"{hw_app.PAYMENT_WINDOW_DAYS} days" in all_text and "flagged" in all_text, (
        "Expected the Terms of Service to state what happens if a buyer doesn't pay in time"
    )


def test_buyer_facing_copy_does_not_reference_removed_buy_now_button():
    # Buyer-funnel audit (2026-08-02): Buy Now was removed months ago
    # (V25.43.123) -- Add to Cart -> Checkout is the only purchase path
    # now. But four buyer-facing spots still describe "Buy Now" as if it
    # exists, and the Knowledge Hub even claimed payment "may not be live
    # yet" -- actively wrong, since payment has been live since V25.43.108.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert "may not be live yet" not in all_text, (
        "Knowledge Hub should not claim payment might not be live -- it has been since V25.43.108"
    )
    assert "Buy Now" not in all_text, (
        f"Knowledge Hub still references the removed Buy Now button: {all_text[:2000]}"
    )
    assert "Add to Cart" in all_text and "checkout" in all_text.lower(), (
        "Expected Knowledge Hub buying copy to describe the real Add to Cart -> Checkout path"
    )

    at2 = AppTest.from_file("app.py", default_timeout=30)
    at2.query_params["legal"] = "terms"
    at2.run()
    assert not at2.exception, at2.exception
    tos_text = " ".join(m.value for m in at2.markdown)
    assert "Buy Now" not in tos_text, (
        f"Terms of Service still references the removed Buy Now button: {tos_text[:2000]}"
    )

    buyer_id = _new_isolated_buyer(hw_app, "strike_copy_buyer")
    hw_app.run("UPDATE buyers SET strikes=1 WHERE id=?", (buyer_id,))
    buyer_email = hw_app.get_buyer(buyer_id)["email"]
    at3 = AppTest.from_file("app.py", default_timeout=30)
    at3.run()
    _real_buyer_session(at3, hw_app, buyer_id, buyer_email)
    goto(at3, "My Account")
    at3.run()
    assert not at3.exception, at3.exception
    warnings = [w.value for w in at3.warning]
    assert not any("Buy Now" in w for w in warnings), (
        f"My Account strike warning still references the removed Buy Now button: {warnings}"
    )


def test_trust_and_safety_copy_matches_real_tier_system():
    # Buyer-funnel audit: this copy described the OLD "Verified Seller"
    # badge (removed V25.43.123) instead of the real New/Bronze/Silver/Gold
    # tier system (compute_trust_tier), which requires a genuine review
    # average for Silver/Gold, not just profile completeness/listing count.
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert "profile completeness" not in all_text, (
        "Trust + Safety copy still describes the removed badge system"
    )
    assert "Bronze" in all_text and "Silver" in all_text and "Gold" in all_text, (
        "Expected Trust + Safety copy to describe the real tier system"
    )


def test_paypal_me_links_are_pre_filled_with_the_exact_split_amount():
    # Buyer-funnel audit: the split amount ($X to seller, $Y platform fee)
    # is shown as text above the "Pay with PayPal" button, but the button
    # itself never carried it -- nothing stopped a buyer from paying the
    # wrong amount after clicking through. paypal.me supports an amount
    # path suffix (paypal.me/name/22.74); use it for plain paypal.me
    # username links (not other http(s) links, whose path format we don't
    # control and could break by appending to).
    def _render():
        import app as hw_app
        hw_app.render_split_payment_line("Pay the seller", "paypal.me/somesellername", 22.74, "note", key="t1")
        hw_app.render_split_payment_line("Pay House Of Wax", "https://paypal.me/houseofwax", 2.25, "note", key="t2")
        hw_app.render_split_payment_line("Pay via email", "seller@example.com", 10.00, "note", key="t3")

    at = AppTest.from_function(_render, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    links = {lb.proto.id: lb.proto.url for lb in at.get("link_button")}
    t1 = next(url for lbid, url in links.items() if lbid.endswith("-t1"))
    t2 = next(url for lbid, url in links.items() if lbid.endswith("-t2"))
    assert t1 == "https://paypal.me/somesellername/22.74", links
    assert t2 == "https://paypal.me/houseofwax/2.25", links
    infos = [i.value for i in at.info]
    assert any("seller@example.com" in i for i in infos), (
        "Bare email PayPal info should still render as plain text, unchanged"
    )


def test_terms_of_service_covers_non_delivery_disputes_discogs_style():
    # Buyer-funnel audit flagged that nothing buyer-facing explains what
    # happens if a paid seller never delivers -- House Of Wax never holds
    # funds, so (per founder direction) this follows Discogs' actual model:
    # contact the seller first, PayPal handles the payment dispute (buyer
    # paid through PayPal directly), and reporting to House Of Wax within a
    # filing window affects the seller's standing on the platform -- mirrors
    # the buyer non-payment strike system that already exists.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["legal"] = "terms"
    at.run()
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown)
    assert "PayPal" in all_text and "seller" in all_text.lower(), all_text
    assert f"{hw_app.NON_DELIVERY_REPORT_WINDOW_DAYS} days" in all_text, (
        "Expected the Terms of Service to state a filing window for non-delivery reports"
    )
    assert "Report Listing" in all_text or "Report Seller" in all_text, (
        "Expected the Terms of Service to point buyers at the existing Report Listing/Seller flow"
    )


def test_report_reasons_include_non_delivery():
    import app as hw_app
    assert any("not received" in r.lower() or "not shipped" in r.lower() for r in hw_app.REPORT_REASONS), (
        f"Expected a non-delivery reason in REPORT_REASONS, got: {hw_app.REPORT_REASONS}"
    )


def test_admin_can_strike_seller_for_non_delivery_from_moderation_center():
    # Founder direction: follow Discogs' buyer/seller dispute model. The ToS
    # now says a non-delivery report "can affect a seller's standing" --
    # this makes that literally true. Unlike the buyer non-payment strike
    # (an automatic lazy sweep, since a missed payment_due_at is objectively
    # measurable), non-delivery has no shipping/tracking data to check
    # automatically, so this is a manual, admin-reviewed action from the
    # Moderation Center -- mirrors Discogs' own human-reviewed dispute model.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Strike Test Seller")
    starting_strikes = int(hw_app.get_seller(seller_id).get("strikes") or 0)
    assert starting_strikes == 0

    hw_app.run(
        "INSERT INTO listing_reports(listing_id,seller_id,reporter_name,reporter_contact,reason,details,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (0, seller_id, "Test Buyer", "buyer@example.com", "Paid but item not received", "Paid a week ago, no item, no response.", "Open", hw_app.now(), hw_app.now()),
    )
    report_id = int(hw_app.df("SELECT id FROM listing_reports WHERE seller_id=? ORDER BY id DESC LIMIT 1", (seller_id,)).iloc[0]["id"])

    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Moderation Center").run()
    assert not at.exception, at.exception

    pick = at.selectbox(key="moderation_report_pick")
    match = next(o for o in pick.options if o.startswith(f"{report_id} |"))
    pick.set_value(match).run()
    assert not at.exception, at.exception

    strike_buttons = [b for b in at.button if b.key == f"strike_seller_non_delivery_{report_id}"]
    assert strike_buttons, "Expected a Strike Seller (Non-Delivery) button in the Moderation Center"
    strike_buttons[0].click().run()
    assert not at.exception, at.exception

    ending_strikes = int(hw_app.get_seller(seller_id).get("strikes") or 0)
    assert ending_strikes == starting_strikes + 1, f"Expected a seller strike added, got {starting_strikes} -> {ending_strikes}"
    report_status = hw_app.df("SELECT status FROM listing_reports WHERE id=?", (report_id,)).iloc[0]["status"]
    assert report_status == "Resolved", f"Expected the report to be marked Resolved, got {report_status!r}"


def test_seller_sees_own_strike_count_in_selling_tab():
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Struck Seller Visibility Test")
    hw_app.run("UPDATE sellers SET strikes=1 WHERE id=?", (seller_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    goto(at, "My Account")
    assert not at.exception, at.exception

    warnings = [w.value for w in at.warning]
    assert any("strike" in w.lower() for w in warnings), (
        f"Expected the seller to see their own strike count on the Selling tab, got warnings: {warnings}"
    )


def test_legal_policies_draft_admin_page_is_removed():
    # Fine-tooth-comb audit: this admin page was a full set of "draft,
    # not final" placeholder policy text, superseded once the real Terms
    # of Service / Privacy Policy went live -- the page even told the
    # admin so itself ("edit those pages directly rather than this draft
    # section"). A whole nav item that exists only to point at a
    # different, real page is pure confusion, not a feature.
    import app as hw_app
    assert not hasattr(hw_app, "legal_policies"), "legal_policies() should be deleted, not just unreachable"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    assert not at.exception, at.exception
    admin_nav = at.sidebar.radio(key="admin_navigation")
    assert "Legal / Policies" not in admin_nav.options, (
        f"Expected 'Legal / Policies' removed from admin nav, got: {admin_nav.options}"
    )


def test_knowledge_hub_overview_does_not_repeat_the_vinyl_first_pitch():
    # Fine-tooth-comb audit: the same "we started with vinyl, everything
    # else builds outward" idea was said twice within seconds on the same
    # page -- once in the intro st.info, once again in the Overview tab.
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown) + " " + " ".join(i.value for i in at.info)
    assert "We started with vinyl" not in all_text, (
        "Expected the redundant second 'started with vinyl' sentence removed from the Overview tab"
    )
    assert "starting with vinyl" in all_text, (
        "Expected the intro's 'starting with vinyl' framing to still be present"
    )


def test_how_buying_works_does_not_duplicate_buyer_faq_checkout_explanation():
    # Fine-tooth-comb audit: "How Buying Works" and "Buyer FAQ" (two tabs
    # on the same Knowledge Hub page) explained the identical checkout
    # mechanic in near-identical words -- the FAQ version is the more
    # complete one (mentions the 5-day window and cart-combining).
    at = fresh_app()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    bullets = [m.value for m in at.markdown if m.value.startswith("- ")]
    assert not any(b == "- Checkout reserves the item and starts a payment window; you pay the seller and House Of Wax directly through PayPal." for b in bullets), (
        "Expected the How Buying Works bullet shortened to avoid duplicating the Buyer FAQ answer"
    )


def test_testing_mode_toggle_hidden_from_regular_visitors():
    # Founder, live: surprised that any random visitor could see and flip a
    # "Testing mode" sidebar toggle -- not actually a data-safety hole (RLS
    # blocks anon reads of anything private regardless of this toggle), but
    # it reads as "unfinished prototype" to someone being pitched as a
    # seller. Founder chose: keep it working for testers, stop showing it
    # to everyone else -- gate it behind a ?tester=1 link instead.
    at = fresh_app()
    toggles = at.get("toggle")
    assert not any("Testing mode" in (t.label or "") for t in toggles), (
        "A regular visitor with no ?tester=1 param should not see the Testing mode toggle"
    )

    at2 = AppTest.from_file("app.py", default_timeout=30)
    at2.query_params["tester"] = "1"
    at2.run()
    assert not at2.exception, at2.exception
    toggles2 = at2.get("toggle")
    assert any("Testing mode" in (t.label or "") for t in toggles2), (
        "A visitor with ?tester=1 should still see the Testing mode toggle"
    )


def test_merch_shop_cta_hidden_until_founder_configures_it():
    # Founder is planning a dropship t-shirt store on Shopify (via Printful/
    # Printify) that's fully separate from the marketplace's own PayPal
    # checkout -- House Of Wax just needs a link to it once it exists.
    # Reuses the existing homepage_blocks system (already has button_text/
    # button_target + an admin UI to edit it) instead of a new mechanism.
    # Must not show a dead/broken link before the founder actually sets the
    # block up.
    at = fresh_app()
    link_buttons = at.get("link_button")
    assert not any("merch" in (lb.label or "").lower() for lb in link_buttons), (
        "Should not show a merch shop link before the founder configures the homepage block"
    )


def test_merch_shop_cta_shows_once_configured():
    import app as hw_app
    hw_app.run(
        "INSERT INTO homepage_blocks(block_name,title,subtitle,body,button_text,button_target,status,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("merch_shop", "House Of Wax Merch", "Shirts and more", "Printed and shipped by our print partner.", "Shop Merch", "https://example-shop.myshopify.com", "Active", 0, hw_app.now(), hw_app.now()),
    )
    at = fresh_app()
    link_buttons = at.get("link_button")
    merch_links = [lb for lb in link_buttons if (lb.label or "") == "Shop Merch"]
    assert merch_links, f"Expected a 'Shop Merch' link button once configured, got: {[lb.label for lb in link_buttons]}"
    assert merch_links[0].proto.url == "https://example-shop.myshopify.com", merch_links[0].proto.url


def test_homepage_editor_supports_merch_shop_block():
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Homepage Editor").run()
    assert not at.exception, at.exception
    block_options = [s.options for s in at.selectbox if "hero" in (s.options or [])]
    assert block_options and "merch_shop" in block_options[0], (
        f"Expected 'merch_shop' as a selectable homepage block, got: {block_options}"
    )


def test_map_discogs_condition_handles_all_real_values():
    # Every condition string actually present in the founder's real Discogs
    # collection export -- confirmed by opening the file directly, not
    # guessed from memory of Discogs' format.
    import app as hw_app
    expected = {
        "Mint (M)": "Mint",
        "Near Mint (NM or M-)": "Near Mint",
        "Very Good Plus (VG+)": "VG+",
        "Very Good (VG)": "VG",
        "Good Plus (G+)": "Good+",
        "Good (G)": "Good",
        "Fair (F)": "Fair",
        "Poor (P)": "Poor",
    }
    for discogs_value, how_grade in expected.items():
        assert hw_app.map_discogs_condition(discogs_value) == how_grade, discogs_value
    # Sleeve-only values that aren't real conditions -- never guess a grade.
    for not_a_grade in ["Generic", "No Cover", "", None]:
        assert hw_app.map_discogs_condition(not_a_grade) == "", not_a_grade


def test_map_discogs_sleeve_condition_handles_no_cover_and_generic():
    # Founder: "I can understand the ones that don't have sleeves but for
    # the one[s] that do we should make that an option." Sleeve condition
    # gets two extra real, non-blank answers beyond an actual grade -- a
    # record with literally no cover has nothing to grade, and a generic/
    # unbranded sleeve is a real object that just isn't a graded condition
    # on Discogs. Neither should look like plain "still ungraded" blank.
    import app as hw_app
    assert hw_app.map_discogs_sleeve_condition("No Cover") == hw_app.NO_SLEEVE_VALUE
    assert hw_app.map_discogs_sleeve_condition("no cover") == hw_app.NO_SLEEVE_VALUE
    assert hw_app.map_discogs_sleeve_condition("Generic") == hw_app.GENERIC_SLEEVE_VALUE
    # Real condition grades still map exactly like map_discogs_condition.
    assert hw_app.map_discogs_sleeve_condition("Very Good Plus (VG+)") == "VG+"
    # Truly unknown/blank stays blank -- never guess.
    for not_a_grade in ["", None, "Not Graded"]:
        assert hw_app.map_discogs_sleeve_condition(not_a_grade) == "", not_a_grade


def test_is_discogs_collection_export_detects_real_header():
    import app as hw_app
    discogs_columns = ["Catalog#", "Artist", "Title", "Label", "Format", "Rating", "Released", "release_id", "CollectionFolder", "Date Added", "Collection Media Condition", "Collection Sleeve Condition", "Collection Notes"]
    discogs_df = pd.DataFrame([{c: "" for c in discogs_columns}])
    assert hw_app.is_discogs_collection_export(discogs_df) is True

    how_columns = ["barcode", "catalog_number", "matrix_runout", "artist", "title", "format", "label", "release_year", "genre", "price", "quantity", "image_url"]
    how_df = pd.DataFrame([{c: "" for c in how_columns}])
    assert hw_app.is_discogs_collection_export(how_df) is False


def test_parse_discogs_collection_csv_maps_fields_and_forces_draft():
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Discogs Import Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    seller = hw_app.get_seller(seller_id)
    assert hw_app.seller_can_publish_live(seller), "Test seller should be fully eligible to publish live"

    row = {
        "Catalog#": "T-587",
        "Artist": "Sidney Joe Qualls",
        "Title": "So Sexy",
        "Label": "20th Century Fox Records, Chi Sound Records",
        "Format": "LP, Album",
        "Released": "1979",
        "release_id": "1876018",
        "Collection Media Condition": "Near Mint (NM or M-)",
        "Collection Sleeve Condition": "Very Good Plus (VG+)",
        "Collection Notes": "",
    }
    df_in = pd.DataFrame([row])
    mapped = hw_app.parse_discogs_collection_csv(df_in, seller_id)
    assert len(mapped) == 1
    item = mapped[0]
    assert item["listing_status"] == "Draft", "Must stay Draft even though this seller CAN publish live -- no price data exists yet"
    assert item["price"] == 0
    assert item["quantity"] == 1
    assert item["artist"] == "Sidney Joe Qualls"
    assert item["title"] == "So Sexy"
    assert item["release_year"] == "1979"
    assert item["catalog_number"] == "T-587"
    assert item["media_grade"] == "Near Mint"
    assert item["sleeve_grade"] == "VG+"
    assert item["external_release_url"] == "https://www.discogs.com/release/1876018"
    assert item["category"] == "Vinyl Records"

    cass_row = dict(row)
    cass_row["Format"] = "Cass, Album"
    cass_mapped = hw_app.parse_discogs_collection_csv(pd.DataFrame([cass_row]), seller_id)[0]
    assert cass_mapped["category"] == "Cassettes"

    no_cover_row = dict(row)
    no_cover_row["Collection Sleeve Condition"] = "No Cover"
    no_cover_mapped = hw_app.parse_discogs_collection_csv(pd.DataFrame([no_cover_row]), seller_id)[0]
    assert no_cover_mapped["sleeve_grade"] == hw_app.NO_SLEEVE_VALUE
    assert no_cover_mapped["media_grade"] == "Near Mint", "Media grade mapping is untouched by the sleeve-specific fix"

    generic_row = dict(row)
    generic_row["Collection Sleeve Condition"] = "Generic"
    generic_mapped = hw_app.parse_discogs_collection_csv(pd.DataFrame([generic_row]), seller_id)[0]
    assert generic_mapped["sleeve_grade"] == hw_app.GENERIC_SLEEVE_VALUE


def test_enrich_next_discogs_batch_updates_image_only_leaves_price_and_status_alone(monkeypatch):
    # Founder: "I only want price suggestion to show when the item is being
    # inputted into the system. At that point the seller chooses how much
    # they want to list the item for." Enrichment must fetch cover art
    # only -- price stays exactly as it was (0 for a fresh import) even
    # when Discogs returns a real lowest_price, so the seller is the one
    # who actually sets it, guided by the (now-rounded) suggested range.
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Discogs Enrich Test Seller")
    hw_app.run(
        "INSERT INTO products(seller_id,artist,title,category,format,price,quantity,image_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (seller_id, "Test Artist", "Test Album", "Vinyl Records", "Vinyl", 0, 1, "", "https://www.discogs.com/release/1876018", "Draft", "Fixed Price", hw_app.now(), hw_app.now()),
    )
    product_id = int(hw_app.df("SELECT id FROM products WHERE seller_id=? ORDER BY id DESC LIMIT 1", (seller_id,)).iloc[0]["id"])

    monkeypatch.setattr(
        hw_app, "fetch_discogs_release_details",
        lambda release_id: {"image_url": "https://img.discogs.com/example.jpg", "lowest_price": 12.5},
    )
    monkeypatch.setattr(hw_app, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    result = hw_app.enrich_next_discogs_batch(seller_id, batch_size=25)
    assert result["enriched"] == 1
    assert result["remaining"] == 0

    row = hw_app.df("SELECT * FROM products WHERE id=?", (product_id,)).iloc[0]
    assert row["image_url"] == "https://img.discogs.com/example.jpg"
    assert float(row["price"]) == 0, "Price must stay unset -- the seller chooses it, enrichment never auto-fills it"
    assert row["listing_status"] == "Draft", "Enrichment must never flip status to Live on its own"


def test_enrich_next_discogs_batch_stops_retrying_items_discogs_has_nothing_for(monkeypatch):
    # Founder, live: after clicking through many batches, the count got
    # stuck at a small number ("7 remain") and the button never went away.
    # Root cause: an item where Discogs has neither a real image nor a
    # price never got any DB write at all, so it matched the same "pending"
    # query forever -- this asserts the fix, that such an item drops out of
    # the pending set permanently after being tried once, with a note
    # explaining why to the seller instead of a silent dead end.
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Discogs Stuck Item Test Seller")
    hw_app.run(
        "INSERT INTO products(seller_id,artist,title,category,format,price,quantity,image_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (seller_id, "Test Artist", "Dead Release", "Vinyl Records", "Vinyl", 0, 1, "", "https://www.discogs.com/release/999999", "Draft", "Fixed Price", hw_app.now(), hw_app.now()),
    )
    product_id = int(hw_app.df("SELECT id FROM products WHERE seller_id=? ORDER BY id DESC LIMIT 1", (seller_id,)).iloc[0]["id"])

    monkeypatch.setattr(hw_app, "fetch_discogs_release_details", lambda release_id: None)
    monkeypatch.setattr(hw_app, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    first = hw_app.enrich_next_discogs_batch(seller_id, batch_size=25)
    assert first["remaining"] == 0, "Item Discogs has nothing for should not still count as pending after being tried"

    row = hw_app.df("SELECT * FROM products WHERE id=?", (product_id,)).iloc[0]
    assert row["listing_status"] == "Draft"
    assert row["reviewer_notes"], "Expected a note explaining why this item couldn't be auto-enriched"

    # A second batch call must not re-select this item at all -- proves it's
    # actually excluded going forward, not just undercounted once.
    calls = []
    monkeypatch.setattr(hw_app, "fetch_discogs_release_details", lambda release_id: calls.append(release_id) or None)
    second = hw_app.enrich_next_discogs_batch(seller_id, batch_size=25)
    assert second["remaining"] == 0
    assert calls == [], "The permanently-unfetchable item should not be retried on later batches"


def test_enrich_next_discogs_batch_marks_no_image_items_as_resolved_without_writing_price(monkeypatch):
    # Partial case: Discogs returns a price but no cover art for a release.
    # That item should still leave the pending queue once tried, with a
    # note that a photo is missing -- and price must stay untouched, since
    # enrichment no longer auto-fills it (the seller sets it, guided by the
    # suggested range).
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Discogs Price Only Test Seller")
    hw_app.run(
        "INSERT INTO products(seller_id,artist,title,category,format,price,quantity,image_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (seller_id, "Test Artist", "No Cover Release", "Vinyl Records", "Vinyl", 0, 1, "", "https://www.discogs.com/release/555555", "Draft", "Fixed Price", hw_app.now(), hw_app.now()),
    )
    product_id = int(hw_app.df("SELECT id FROM products WHERE seller_id=? ORDER BY id DESC LIMIT 1", (seller_id,)).iloc[0]["id"])

    monkeypatch.setattr(hw_app, "fetch_discogs_release_details", lambda release_id: {"image_url": "", "lowest_price": 9.99})
    monkeypatch.setattr(hw_app, "time", type("T", (), {"sleep": staticmethod(lambda s: None)}))

    result = hw_app.enrich_next_discogs_batch(seller_id, batch_size=25)
    assert result["remaining"] == 0

    row = hw_app.df("SELECT * FROM products WHERE id=?", (product_id,)).iloc[0]
    assert float(row["price"]) == 0, "Price must stay unset even when Discogs returns a lowest_price"
    assert row["reviewer_notes"], "Expected a note that cover art specifically wasn't found"


def test_enrich_next_discogs_batch_requests_full_columns_from_supabase(monkeypatch):
    # Founder, live: clicking "Fetch next batch from Discogs" crashed with
    # "Something went wrong loading this page." Root cause: hosted_select()
    # defaults products queries to PRODUCTS_ANON_SAFE_SELECT, which
    # deliberately excludes reviewer_notes (internal moderation notes) --
    # callers that need it must pass select='*' explicitly (see the comment
    # at PRODUCTS_ANON_SAFE_SELECT's definition). enrich_next_discogs_batch
    # reads row['reviewer_notes'] but never asked for it, so on the real
    # hosted database (not local SQLite, which always returns every column
    # regardless and is why this passed locally the first time) that's a
    # KeyError. This calls hosted_select directly to check what it was
    # actually asked for, independent of local-vs-hosted DB behavior.
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    calls = []

    def fake_hosted_select(table_name, filters=None, order=None, limit=None, in_filters=None, select=None):
        calls.append(select)
        return pd.DataFrame()

    monkeypatch.setattr(hw_app, "hosted_select", fake_hosted_select)
    hw_app.enrich_next_discogs_batch(1)
    assert calls, "Expected enrich_next_discogs_batch to call hosted_select"
    assert calls[0] == "*", (
        f"enrich_next_discogs_batch must request select='*' to read reviewer_notes -- got select={calls[0]!r}"
    )


def test_my_inventory_shows_fetch_batch_button_when_pending_discogs_items_exist():
    # AppTest re-executes app.py's source fresh on every .run() (that's how
    # Streamlit re-runs scripts), so a plain monkeypatch.setattr on a
    # function doesn't reach the freshly-rebound version the rendered page
    # actually calls -- setting a real st.secrets value that
    # discogs_token_status() itself reads is the correct way to fake this.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Discogs Pending UI Test Seller")
    hw_app.run(
        "INSERT INTO products(seller_id,artist,title,category,format,price,quantity,image_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (seller_id, "Test Artist", "Test Album", "Vinyl Records", "Vinyl", 0, 1, "", "https://www.discogs.com/release/1876018", "Draft", "Fixed Price", hw_app.now(), hw_app.now()),
    )

    seller_email = hw_app.get_seller(seller_id)["email"]
    at = AppTest.from_file("app.py", default_timeout=30)
    at.secrets["DISCOGS_TOKEN"] = "fake-token-for-test"
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    assert not at.exception, at.exception

    fetch_buttons = [b for b in at.button if (b.label or "") == "Fetch next batch from Discogs"]
    assert fetch_buttons, "Expected a 'Fetch next batch from Discogs' button when pending imported items exist"
    all_text = " ".join(m.value for m in at.markdown) + " " + " ".join(i.value for i in at.info)
    assert "1" in all_text and "Discogs" in all_text


def test_hosted_database_prep_section_drops_obsolete_migration_checklist():
    # This admin diagnostics section still described a Supabase migration
    # as a future to-do ("move to hosted database before launch", a
    # "Supabase migration checklist" referencing version V25.28) -- the
    # migration to hosted Supabase happened long ago and has been the live
    # production database all session. A founder checking Diagnostics
    # shouldn't see a stale pre-launch checklist reading like nothing's
    # been done yet.
    def _render():
        import app as hw_app
        hw_app.hosted_database_prep_section()

    at = AppTest.from_function(_render, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "migration checklist" not in all_text.lower(), f"Expected the obsolete migration checklist removed, got: {all_text}"
    assert "V25.28" not in all_text, f"Expected the stale version reference removed, got: {all_text}"
    assert "before launch" not in all_text.lower(), f"Expected pre-launch framing removed, got: {all_text}"


def test_claim_existing_profile_section_drops_prototype_wording():
    # Founder: "I'm still seeing testing language on here." This screen is
    # real-user-facing (a signed-in seller/buyer with no linked store sees
    # it, not just admins), so "prototype" language here reaches real
    # customers, not just internal testers.
    def _render():
        import app as hw_app
        hw_app.claim_existing_profile_section()

    at = AppTest.from_function(_render, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    all_text = " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)
    assert "prototype" not in all_text.lower(), f"Expected no 'prototype' wording, got: {all_text}"


def test_image_unavailable_fallback_has_no_internal_deployment_language():
    # Same class of issue -- a broken image (local dev leftover, migration
    # artifact, whatever) could show this caption to any real buyer or
    # seller. It should just say the image isn't available, not talk about
    # "production launch" or "prototype image storage" -- both wrong now
    # that Supabase storage is actually connected, and neither is
    # something a customer should ever see regardless.
    import tempfile, os

    def _render():
        import app as hw_app
        # A path that doesn't exist on disk triggers the fallback branch.
        hw_app.safe_image("/tmp/does-not-exist-house-of-wax-test.jpg", width=100)

    at = AppTest.from_function(_render, default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    all_text = " ".join(c.value for c in at.caption)
    assert "prototype" not in all_text.lower(), f"Expected no 'prototype' wording, got: {all_text}"
    assert "production launch" not in all_text.lower(), f"Expected no internal deployment language, got: {all_text}"


def test_header_prototype_demo_banner_hidden_from_real_admins():
    # Same pattern as the Testing mode sidebar fix (V25.43.161) -- this
    # "Working prototype demo... available for walkthroughs" banner showed
    # to every admin session on every page load, real admin or not. A real,
    # signed-in admin doesn't need to be told the site is a demo for
    # walkthroughs.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        ("real-admin-uuid-2", "real-admin-test2@example.com", "Real Admin", "Admin", "Yes", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": "real-admin-uuid-2", "email": "real-admin-test2@example.com", "access_token": "fake"}
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    assert not at.exception, at.exception

    all_text = " ".join(i.value for i in at.info)
    assert "prototype demo" not in all_text.lower(), f"A real admin should not see the prototype-demo banner, got: {all_text}"


def test_real_admin_does_not_see_testing_build_password_language():
    # Same class of issue found while cleaning up the ones above: this
    # message conflates "no separate ADMIN_PASSWORD secret configured"
    # with "Testing build" -- misleading for a real admin who authenticated
    # via real sign-in, not a testing shortcut.
    import app as hw_app
    assert not hw_app.ADMIN_PASSWORD, "This test assumes no ADMIN_PASSWORD secret is configured locally"
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        ("real-admin-uuid-3", "real-admin-test3@example.com", "Real Admin", "Admin", "Yes", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": "real-admin-uuid-3", "email": "real-admin-test3@example.com", "access_token": "fake"}
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Admin Dashboard").run()
    assert not at.exception, at.exception

    all_text = " ".join(i.value for i in at.info)
    assert "testing build" not in all_text.lower(), f"A real admin should not see 'Testing build' language, got: {all_text}"


def test_seller_action_dropdown_reflects_newly_selected_listings_real_status():
    # Founder, live: "I just tried to load a record into my store and it
    # didn't work... it did all the work but it didn't move it to my
    # store." Root cause: the "Seller action" status dropdown shares one
    # key across every listing, so switching which item is selected didn't
    # reset it to that item's real current status -- it silently kept
    # whatever was left over from browsing a previous item, making
    # "Update listing status" a no-op that still claimed success.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Seller Action Dropdown Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    live_product_id = _new_isolated_product(hw_app, seller_id, "Already Live Item")
    draft_product_id = _new_isolated_product(hw_app, seller_id, "Still Draft Item")
    hw_app.run("UPDATE products SET listing_status='Draft' WHERE id=?", (draft_product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    assert not at.exception, at.exception

    listing_select = at.selectbox(key="primary_my_inventory_listing_id")
    listing_select.set_value(live_product_id).run()
    assert at.selectbox(key=f"primary_my_inventory_seller_action_{live_product_id}").value == "Live", (
        "Dropdown should default to the selected listing's real current status (Live)"
    )

    listing_select.set_value(draft_product_id).run()
    assert not at.exception, at.exception
    assert at.selectbox(key=f"primary_my_inventory_seller_action_{draft_product_id}").value == "Draft", (
        "Switching to a different listing should show a dropdown defaulted to THAT listing's real status"
    )


def test_my_inventory_shows_price_range_and_lets_seller_update_price():
    # Founder: "make sure it is giving range of price suggestions for the
    # music items" -- reviewing an already-imported listing in My Inventory
    # previously had no price guidance and no way to change the price at
    # all without leaving the page (upload_product() only supports creating
    # a NEW listing, not editing an existing one). This adds both: a real
    # low-high range (not a single number) using the same
    # suggest_seller_price_range() the listing-creation form already uses,
    # plus an editable price field that actually saves.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Price Range Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    # Two comparable priced items (same artist, real prices) so
    # suggest_price_range_from_how_history has something to compute a
    # range from -- it needs at least 2 matching-artist items with a
    # positive price.
    comp1 = _new_isolated_product(hw_app, seller_id, "Comparable Item One")
    comp2 = _new_isolated_product(hw_app, seller_id, "Comparable Item Two")
    hw_app.run("UPDATE products SET artist='Range Test Artist', price=20.00 WHERE id=?", (comp1,))
    hw_app.run("UPDATE products SET artist='Range Test Artist', price=30.00 WHERE id=?", (comp2,))
    target_id = _new_isolated_product(hw_app, seller_id, "Item Needing A Price")
    hw_app.run("UPDATE products SET artist='Range Test Artist', listing_status='Draft', price=0 WHERE id=?", (target_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(target_id).run()
    assert not at.exception, at.exception

    caption_text = " ".join(c.value for c in at.caption)
    assert "Suggested price range" in caption_text, f"Expected a price-range caption, got: {caption_text}"
    # Compute the expected range the same way the app does (quantiles of
    # [20, 30], adjusted for the target listing's own grade), rather than
    # hardcoding the grade-multiplier math here. round_price_range_up()
    # rounds both ends up to the nearest whole dollar (founder: "make sure
    # we are maximizing this part" -- clean numbers, never rounded down).
    expected = hw_app.suggest_seller_price_range("Range Test Artist", None, "VG+", "VG", "Item Needing A Price")
    assert expected["low"] % 1 == 0 and expected["high"] % 1 == 0, "Suggested range must be whole dollars"
    assert hw_app.money(expected["low"]) in caption_text and hw_app.money(expected["high"]) in caption_text, (
        f"Expected {hw_app.money(expected['low'])}-{hw_app.money(expected['high'])} in caption, got: {caption_text}"
    )

    at.number_input(key=f"primary_my_inventory_price_{target_id}").set_value(27.5).run()
    at.button(key=f"primary_my_inventory_price_update_{target_id}").click().run()
    assert not at.exception, at.exception
    assert hw_app.df("SELECT price FROM products WHERE id=?", (target_id,)).iloc[0]["price"] == 27.5, (
        "Price should actually persist after clicking Update price"
    )

    # Founder: "I only want price suggestion to show when the item is being
    # inputted into the system. At that point the seller chooses how much
    # they want to list the item for." Now that a real price has been set,
    # the suggestion must not keep reappearing on every future visit.
    caption_text_after = " ".join(c.value for c in at.caption)
    assert "Suggested price range" not in caption_text_after, (
        f"Suggestion should disappear once a real price is set, got: {caption_text_after}"
    )


def test_my_inventory_dataframe_shows_cover_photo_column():
    # Founder: "I don't see photo of the album covers or any other pics."
    # The inventory table had a text Yes/No indicator but never rendered
    # the actual image, which made reviewing a large imported batch a wall
    # of text with no visual to recognize items by.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Cover Photo Test Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Item With A Cover")
    hw_app.run("UPDATE products SET image_url='https://img.discogs.com/cover-test.jpg' WHERE id=?", (product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    assert not at.exception, at.exception

    table = at.dataframe[0].value
    assert "Cover" in table.columns, f"Expected a Cover column in My Inventory, got: {list(table.columns)}"
    assert "https://img.discogs.com/cover-test.jpg" in table["Cover"].values, (
        "Expected the item's real image_url to appear in the Cover column"
    )


def test_has_listing_photos_bulk_matches_per_item_lookup():
    # Correctness check for the batched version against the same fixtures
    # the single-item has_listing_photos() would be asked about: a real
    # seller-uploaded photo counts, a reference/auto image URL and no
    # gallery rows at all both don't.
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Bulk Photo Lookup Seller")
    with_real_photo = _new_isolated_product(hw_app, seller_id, "Has A Real Photo")
    with_reference_only = _new_isolated_product(hw_app, seller_id, "Reference Photo Only")
    with_no_gallery_rows = _new_isolated_product(hw_app, seller_id, "No Gallery Rows At All")

    hw_app.run(
        "INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)",
        (with_real_photo, "house_of_wax_uploads/real-photo.jpg", "Main listing photo", hw_app.now()),
    )
    hw_app.run(
        "INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)",
        (with_reference_only, "https://img.discogs.com/reference.jpg", "Reference art", hw_app.now()),
    )

    result = hw_app.has_listing_photos_bulk([with_real_photo, with_reference_only, with_no_gallery_rows])
    assert result == {with_real_photo}, f"Expected only the real-photo item to match, got: {result}"

    # Must agree with the original per-item function on the same fixtures.
    assert hw_app.has_listing_photos(with_real_photo) == True
    assert hw_app.has_listing_photos(with_reference_only) == False
    assert hw_app.has_listing_photos(with_no_gallery_rows) == False

    assert hw_app.has_listing_photos_bulk([]) == set()


def test_has_listing_photos_bulk_uses_one_query_per_chunk_not_per_item(monkeypatch):
    # Founder felt this live: My Inventory took 30-45+ seconds to load for
    # a large store because has_listing_photos() ran once per row (one
    # product_gallery network round-trip per listing). This proves the fix
    # actually batches -- a few hosted_select calls total, not one per id.
    import app as hw_app
    monkeypatch.setattr(hw_app, "hosted_enabled", lambda: True)
    calls = []

    def fake_hosted_select(table_name, filters=None, order=None, limit=None, in_filters=None, select=None):
        calls.append(in_filters)
        return pd.DataFrame(columns=["product_id", "image_url"])

    monkeypatch.setattr(hw_app, "hosted_select", fake_hosted_select)
    ids = list(range(1, 451))  # spans more than one 200-id chunk
    hw_app.has_listing_photos_bulk(ids)
    assert len(calls) == 3, f"Expected 3 chunked calls for 450 ids (200/200/50), got {len(calls)}: {calls}"
    assert sum(len(c["product_id"]) for c in calls) == 450


def test_bulk_get_sellers_uses_one_query_per_chunk_not_per_item():
    # Same class of bug as has_listing_photos_bulk above, on the seller
    # side: product_card() used to call get_seller() fresh for every single
    # card. Real incident: with 800+ live listings on Search Music, that's
    # 800+ Supabase round-trips just for seller lookups on one page load --
    # founder, live: "it's taken at least five minutes to get to the search
    # bar." This proves bulk_get_sellers() actually batches.
    import app as hw_app
    calls = []

    def fake_hosted_select(table_name, filters=None, order=None, limit=None, in_filters=None, select=None):
        calls.append(in_filters)
        return pd.DataFrame(columns=["id", "store_name"])

    orig_hosted_enabled = hw_app.hosted_enabled
    orig_hosted_select = hw_app.hosted_select
    hw_app.hosted_enabled = lambda: True
    hw_app.hosted_select = fake_hosted_select
    try:
        ids = list(range(1, 451))
        hw_app.bulk_get_sellers(ids)
    finally:
        hw_app.hosted_enabled = orig_hosted_enabled
        hw_app.hosted_select = orig_hosted_select
    assert len(calls) == 3, f"Expected 3 chunked calls for 450 seller ids, got {len(calls)}: {calls}"
    assert sum(len(c["id"]) for c in calls) == 450


def test_bulk_listing_galleries_uses_one_query_per_chunk_not_per_item():
    import app as hw_app
    calls = []

    def fake_hosted_select(table_name, filters=None, order=None, limit=None, in_filters=None, select=None):
        calls.append(in_filters)
        return pd.DataFrame(columns=["product_id", "image_url", "caption"])

    orig_hosted_enabled = hw_app.hosted_enabled
    orig_hosted_select = hw_app.hosted_select
    hw_app.hosted_enabled = lambda: True
    hw_app.hosted_select = fake_hosted_select
    try:
        ids = list(range(1, 451))
        result = hw_app.bulk_listing_galleries(ids)
    finally:
        hw_app.hosted_enabled = orig_hosted_enabled
        hw_app.hosted_select = orig_hosted_select
    assert len(calls) == 3, f"Expected 3 chunked calls for 450 product ids, got {len(calls)}: {calls}"
    assert len(result) == 450, "Every requested id should have an entry, even with no gallery rows"


def test_search_music_does_not_query_sellers_or_gallery_once_per_listing(monkeypatch):
    # End-to-end version of the fix, through the real Search Music page:
    # several live listings from the same seller used to mean one
    # get_seller() call AND one product_gallery fetch per listing (product_card
    # calling listing_primary_image() and has_listing_photos() separately,
    # each doing their own fetch). This drives the actual page and asserts
    # the seller/gallery query counts stay small and flat regardless of how
    # many listings are showing, not proportional to them.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id, seller_email = _setup_approved_seller_for_bulk_publish(hw_app, "N+1 Regression Test Seller")
    for i in range(6):
        pid = _new_isolated_product(hw_app, seller_id, f"N+1 Test Item {i}")
        hw_app.run("UPDATE products SET listing_status='Live' WHERE id=?", (pid,))

    seller_calls = []
    gallery_calls = []
    orig_get_seller = hw_app.get_seller
    orig_gallery = hw_app.listing_gallery_images

    def counting_get_seller(i):
        seller_calls.append(i)
        return orig_get_seller(i)

    def counting_gallery(pid):
        gallery_calls.append(pid)
        return orig_gallery(pid)

    monkeypatch.setattr(hw_app, "get_seller", counting_get_seller)
    monkeypatch.setattr(hw_app, "listing_gallery_images", counting_gallery)

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    goto(at, "Search Music")
    assert not at.exception, at.exception

    assert len(seller_calls) <= 1, (
        f"Expected at most one per-item get_seller() call (batched via bulk_get_sellers otherwise), "
        f"got {len(seller_calls)} for 6 listings from the same seller: {seller_calls}"
    )
    assert len(gallery_calls) <= 1, (
        f"Expected listing_gallery_images() to not run once per card (batched via bulk_listing_galleries "
        f"otherwise), got {len(gallery_calls)} for 6 listings: {gallery_calls}"
    )


# ---------- Real incident: a buyer with a null product_id on one row crashed every page that loaded their activity ----------

def test_int_or_handles_none_nan_and_real_values():
    # A NULL DB column comes back through pandas as a genuine float NaN, and
    # NaN is truthy in Python -- "int(x or default)" does not catch it and
    # crashes with "cannot convert float NaN to integer". int_or must.
    import app as hw_app
    assert hw_app.int_or(None) == 0
    assert hw_app.int_or(float("nan")) == 0
    assert hw_app.int_or(float("nan"), 7) == 7
    assert hw_app.int_or(42) == 42
    assert hw_app.int_or(42.0) == 42
    assert hw_app.int_or("not a number") == 0


def test_enrich_activity_rows_does_not_crash_on_a_null_product_id():
    # Real production incident: a buyer had a listing_inquiries row whose
    # product_id was null (an inquiry about a listing that no longer
    # exists). buyer_activity_tables() always computes inquiries internally
    # even when a caller only wants purchases (e.g. seller_ready_to_pay_groups),
    # so this crashed every page for that buyer -- Cart AND My Account both,
    # confirmed via the founder's screenshots: "ValueError: cannot convert
    # float NaN to integer".
    import app as hw_app
    records = pd.DataFrame([
        {"id": 3, "buyer_id": 125, "seller_id": 14, "product_id": float("nan"), "status": "New"},
        {"id": 9, "buyer_id": 125, "seller_id": 14, "product_id": 11, "status": "New"},
    ])
    result = hw_app.enrich_activity_rows(records)
    assert len(result) == 2


def test_enrich_cart_rows_does_not_crash_on_a_null_product_id():
    import app as hw_app
    records = pd.DataFrame([
        {"id": 1, "buyer_id": 125, "seller_id": 14, "product_id": float("nan")},
    ])
    result = hw_app.enrich_cart_rows(records)
    assert len(result) == 1
    assert result.iloc[0]["available"] == False


# ---------- Deleting inventory (founder: sellers need a way to delete listings that sold, including sold off-platform) ----------

def test_product_has_completed_platform_sale_true_when_real_sold_purchase_request_exists():
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Real Sale Test Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Item Sold Through House Of Wax")
    hw_app.run(
        "INSERT INTO purchase_requests(product_id,seller_id,buyer_name,buyer_contact,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (product_id, seller_id, "Real Buyer", "buyer@example.com", "Sold", hw_app.now(), hw_app.now()),
    )
    assert hw_app.product_has_completed_platform_sale(product_id) is True


def test_product_has_completed_platform_sale_false_with_no_purchase_request():
    # The common case for "sold another way" -- seller marks it Sold
    # themselves, no real purchase_requests row was ever created for it.
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Off Platform Sale Test Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Item Sold Somewhere Else")
    assert hw_app.product_has_completed_platform_sale(product_id) is False


def test_product_has_completed_platform_sale_false_when_only_an_unfulfilled_offer_exists():
    # A purchase_requests row that never actually completed (still New,
    # never reached status=Sold) must not count as real sale history.
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Pending Offer Test Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Item With Only An Open Offer")
    hw_app.run(
        "INSERT INTO purchase_requests(product_id,seller_id,buyer_name,buyer_contact,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (product_id, seller_id, "Interested Buyer", "buyer2@example.com", "New", hw_app.now(), hw_app.now()),
    )
    assert hw_app.product_has_completed_platform_sale(product_id) is False


def test_seller_can_delete_sold_listing_with_no_real_purchase_history():
    # Founder: "Some people may sell other ways and some items will sell
    # and they can't delete it from their inventory." Sold listings used
    # to never be deletable at all, no matter what.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Delete Sold No History Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Sold Elsewhere Item")
    hw_app.run("UPDATE products SET listing_status='Sold' WHERE id=?", (product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    at.checkbox(key="primary_my_inventory_show_sold").set_value(True).run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(product_id).run()
    assert not at.exception, at.exception

    confirm = next(c for c in at.checkbox if c.key == f"primary_my_inventory_delete_confirm_{product_id}")
    confirm.set_value(True).run()
    delete_button = next(b for b in at.button if b.key == f"primary_my_inventory_delete_{product_id}")
    delete_button.click().run()
    assert not at.exception, at.exception

    remaining = hw_app.df("SELECT * FROM products WHERE id=?", (product_id,))
    assert remaining.empty, "Sold listing with no real purchase history should be deletable"


def test_seller_cannot_delete_sold_listing_with_real_completed_sale():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Delete Sold Real History Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Genuinely Sold On House Of Wax")
    hw_app.run("UPDATE products SET listing_status='Sold' WHERE id=?", (product_id,))
    hw_app.run(
        "INSERT INTO purchase_requests(product_id,seller_id,buyer_name,buyer_contact,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (product_id, seller_id, "Real Buyer", "buyer3@example.com", "Sold", hw_app.now(), hw_app.now()),
    )
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    at.checkbox(key="primary_my_inventory_show_sold").set_value(True).run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(product_id).run()
    assert not at.exception, at.exception

    delete_buttons = [b for b in at.button if b.key == f"primary_my_inventory_delete_{product_id}"]
    assert not delete_buttons, "A listing with a real completed sale must not offer a delete button"
    all_text = " ".join(w.value for w in at.warning)
    assert "completed House Of Wax sale" in all_text

    remaining = hw_app.df("SELECT * FROM products WHERE id=?", (product_id,))
    assert not remaining.empty, "Listing with real sale history must not be deletable"


# ---------- Bulk publish (founder: "why are my listings not live?" -> reviewing ~800 imported drafts one at a time is too slow) ----------

def _setup_approved_seller_for_bulk_publish(hw_app, store_name):
    seller_id = _new_isolated_seller(hw_app, store_name)
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]
    return seller_id, seller_email


def _load_my_inventory(hw_app, seller_id, seller_email):
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    assert not at.exception, at.exception
    return at


def test_bulk_publish_only_offers_drafts_with_both_a_photo_and_a_price():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id, seller_email = _setup_approved_seller_for_bulk_publish(hw_app, "Bulk Publish Eligibility Seller")

    ready_id = _new_isolated_product(hw_app, seller_id, "Ready To Publish")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='https://img.discogs.com/ready.jpg' WHERE id=?", (ready_id,))

    no_price_id = _new_isolated_product(hw_app, seller_id, "Has Photo No Price")
    hw_app.run("UPDATE products SET listing_status='Draft', price=0, image_url='https://img.discogs.com/no-price.jpg' WHERE id=?", (no_price_id,))

    no_photo_id = _new_isolated_product(hw_app, seller_id, "Has Price No Photo")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='' WHERE id=?", (no_photo_id,))

    at = _load_my_inventory(hw_app, seller_id, seller_email)
    multiselects = [m for m in at.multiselect if m.key == "primary_my_inventory_bulk_publish_select"]
    assert multiselects, "Expected the bulk publish multiselect to render when at least one listing is ready"
    ms = multiselects[0]
    assert ms.value == [ready_id], f"Expected only the ready listing as default selection, got: {ms.value}"


def test_bulk_publish_hidden_when_no_listings_are_ready():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id, seller_email = _setup_approved_seller_for_bulk_publish(hw_app, "Bulk Publish None Ready Seller")
    no_price_id = _new_isolated_product(hw_app, seller_id, "Still Needs A Price")
    hw_app.run("UPDATE products SET listing_status='Draft', price=0, image_url='https://img.discogs.com/pending.jpg' WHERE id=?", (no_price_id,))

    at = _load_my_inventory(hw_app, seller_id, seller_email)
    multiselects = [m for m in at.multiselect if m.key == "primary_my_inventory_bulk_publish_select"]
    assert not multiselects, "Bulk publish section should not render when nothing is ready"


def test_bulk_publish_hidden_when_seller_rules_not_accepted():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Bulk Publish Rules Not Accepted Seller")
    # Deliberately skip accepting rules, unlike _setup_approved_seller_for_bulk_publish.
    seller_email = hw_app.get_seller(seller_id)["email"]
    ready_id = _new_isolated_product(hw_app, seller_id, "Ready But Rules Not Accepted")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='https://img.discogs.com/ready.jpg' WHERE id=?", (ready_id,))

    at = _load_my_inventory(hw_app, seller_id, seller_email)
    multiselects = [m for m in at.multiselect if m.key == "primary_my_inventory_bulk_publish_select"]
    assert not multiselects, "Bulk publish must not be offered before seller rules are accepted"


def test_bulk_publish_publishes_only_selected_listings_and_leaves_others_alone():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id, seller_email = _setup_approved_seller_for_bulk_publish(hw_app, "Bulk Publish Action Seller")

    ready_a = _new_isolated_product(hw_app, seller_id, "Ready Item A")
    hw_app.run("UPDATE products SET listing_status='Draft', price=5, image_url='https://img.discogs.com/a.jpg' WHERE id=?", (ready_a,))
    ready_b = _new_isolated_product(hw_app, seller_id, "Ready Item B")
    hw_app.run("UPDATE products SET listing_status='Draft', price=8, image_url='https://img.discogs.com/b.jpg' WHERE id=?", (ready_b,))
    not_ready = _new_isolated_product(hw_app, seller_id, "Not Ready Item")
    hw_app.run("UPDATE products SET listing_status='Draft', price=0, image_url='https://img.discogs.com/c.jpg' WHERE id=?", (not_ready,))

    at = _load_my_inventory(hw_app, seller_id, seller_email)
    ms = next(m for m in at.multiselect if m.key == "primary_my_inventory_bulk_publish_select")
    # Deselect item B, keep only A -- proves the selection actually controls
    # what gets published, not just "publish everything ready."
    ms.set_value([ready_a]).run()
    publish_buttons = [b for b in at.button if b.key == "primary_my_inventory_bulk_publish_button"]
    assert publish_buttons, "Expected the bulk publish button"
    publish_buttons[0].click().run()
    assert not at.exception, at.exception

    statuses = hw_app.df("SELECT id,listing_status FROM products WHERE id IN (?,?,?)", (ready_a, ready_b, not_ready))
    by_id = dict(zip(statuses["id"], statuses["listing_status"]))
    assert by_id[ready_a] == "Live", "Selected ready item should be published"
    assert by_id[ready_b] == "Draft", "Deselected ready item should stay Draft"
    assert by_id[not_ready] == "Draft", "Item missing a price must never be published, selected or not"


def test_round_price_range_up_rounds_to_whole_dollars_never_down():
    # Founder: "The price is not in whole numbers. I want to make sure we
    # are maximizing this part." Raw quantile/API prices come back in odd
    # cents -- round both ends up (never down) to a clean whole dollar.
    import app as hw_app
    result = hw_app.round_price_range_up({"low": 7.94, "high": 11.47, "source": "test"})
    assert result["low"] == 8.0
    assert result["high"] == 12.0

    # Already-whole values should stay put, not get bumped up an extra dollar.
    exact = hw_app.round_price_range_up({"low": 10.0, "high": 20.0, "source": "test"})
    assert exact["low"] == 10.0
    assert exact["high"] == 20.0

    # A tight range still rounds each end up independently -- $9.99-$10.01
    # becomes $10-$11, not squashed into a single number.
    tight = hw_app.round_price_range_up({"low": 9.99, "high": 10.01, "source": "test"})
    assert tight["low"] == 10.0
    assert tight["high"] == 11.0

    assert hw_app.round_price_range_up(None) is None


def test_publish_via_status_dropdown_blocked_without_a_photo():
    # Founder: "we should have it where all submissions for sale have
    # photos of lp and record" -- every live listing needs at least one
    # photo (the auto-filled reference image, or the seller's own), and
    # nothing previously enforced that on the My Inventory status-dropdown
    # path (as opposed to the listing-creation form, which is a separate
    # code path). A draft with no image_url should not be publishable.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "No Photo Publish Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    draft_product_id = _new_isolated_product(hw_app, seller_id, "No Photo Draft Item")
    hw_app.run("UPDATE products SET listing_status='Draft', image_url='' WHERE id=?", (draft_product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()

    at.selectbox(key="primary_my_inventory_listing_id").set_value(draft_product_id).run()
    at.selectbox(key=f"primary_my_inventory_seller_action_{draft_product_id}").set_value("Live").run()
    at.button(key=f"primary_my_inventory_update_{draft_product_id}").click().run()
    assert not at.exception, at.exception

    assert hw_app.df("SELECT listing_status FROM products WHERE id=?", (draft_product_id,)).iloc[0]["listing_status"] == "Draft", (
        "Listing should still be Draft -- publish must be blocked with no photo"
    )
    error_text = " ".join(e.value for e in at.error)
    assert "photo" in error_text.lower(), f"Expected a photo-required error, got: {error_text}"


def test_publish_via_status_dropdown_allowed_with_a_photo():
    # Positive control for the guard above -- a listing that DOES have a
    # photo should publish normally, same as before this fix.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Has Photo Publish Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    draft_product_id = _new_isolated_product(hw_app, seller_id, "Has Photo Draft Item")
    hw_app.run("UPDATE products SET listing_status='Draft', image_url='https://example.com/real-photo.jpg' WHERE id=?", (draft_product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()

    at.selectbox(key="primary_my_inventory_listing_id").set_value(draft_product_id).run()
    at.selectbox(key=f"primary_my_inventory_seller_action_{draft_product_id}").set_value("Live").run()
    at.button(key=f"primary_my_inventory_update_{draft_product_id}").click().run()
    assert not at.exception, at.exception

    assert hw_app.df("SELECT listing_status FROM products WHERE id=?", (draft_product_id,)).iloc[0]["listing_status"] == "Live", (
        "Listing with a real photo should publish normally"
    )


def test_publish_via_status_dropdown_blocked_without_media_grade():
    # Founder: "I notice the grading is incomplete. There need to be
    # grading for both the vinyl and the cover." A listing missing the
    # media (vinyl) grade should not be publishable.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "No Media Grade Publish Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    draft_product_id = _new_isolated_product(hw_app, seller_id, "No Media Grade Draft Item")
    hw_app.run("UPDATE products SET listing_status='Draft', image_url='https://example.com/real-photo.jpg', media_grade='', sleeve_grade='VG' WHERE id=?", (draft_product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()

    at.selectbox(key="primary_my_inventory_listing_id").set_value(draft_product_id).run()
    at.selectbox(key=f"primary_my_inventory_seller_action_{draft_product_id}").set_value("Live").run()
    at.button(key=f"primary_my_inventory_update_{draft_product_id}").click().run()
    assert not at.exception, at.exception

    assert hw_app.df("SELECT listing_status FROM products WHERE id=?", (draft_product_id,)).iloc[0]["listing_status"] == "Draft", (
        "Listing should still be Draft -- publish must be blocked with no media grade"
    )
    error_text = " ".join(e.value for e in at.error)
    assert "vinyl" in error_text.lower() or "media" in error_text.lower(), f"Expected a media-grade-required error, got: {error_text}"


def test_publish_via_status_dropdown_blocked_without_sleeve_grade():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "No Sleeve Grade Publish Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    draft_product_id = _new_isolated_product(hw_app, seller_id, "No Sleeve Grade Draft Item")
    hw_app.run("UPDATE products SET listing_status='Draft', image_url='https://example.com/real-photo.jpg', media_grade='VG+', sleeve_grade='' WHERE id=?", (draft_product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()

    at.selectbox(key="primary_my_inventory_listing_id").set_value(draft_product_id).run()
    at.selectbox(key=f"primary_my_inventory_seller_action_{draft_product_id}").set_value("Live").run()
    at.button(key=f"primary_my_inventory_update_{draft_product_id}").click().run()
    assert not at.exception, at.exception

    assert hw_app.df("SELECT listing_status FROM products WHERE id=?", (draft_product_id,)).iloc[0]["listing_status"] == "Draft", (
        "Listing should still be Draft -- publish must be blocked with no sleeve grade"
    )
    error_text = " ".join(e.value for e in at.error)
    assert "sleeve" in error_text.lower() or "cover" in error_text.lower(), f"Expected a sleeve-grade-required error, got: {error_text}"


def test_seller_can_edit_grading_in_my_inventory():
    # Founder: same grading-completeness request -- and there was
    # previously no way to add a missing grade to an already-imported
    # listing without leaving My Inventory and re-running the whole Add
    # Inventory wizard (which doesn't support editing an existing row).
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "Edit Grading Test Seller")
    product_id = _new_isolated_product(hw_app, seller_id, "Ungraded Item")
    hw_app.run("UPDATE products SET media_grade='', sleeve_grade='' WHERE id=?", (product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(product_id).run()
    assert not at.exception, at.exception

    at.selectbox(key=f"primary_my_inventory_media_grade_{product_id}").set_value("Near Mint").run()
    at.selectbox(key=f"primary_my_inventory_sleeve_grade_{product_id}").set_value("VG+").run()
    at.button(key=f"primary_my_inventory_grading_update_{product_id}").click().run()
    assert not at.exception, at.exception

    row = hw_app.df("SELECT media_grade, sleeve_grade FROM products WHERE id=?", (product_id,)).iloc[0]
    assert row["media_grade"] == "Near Mint"
    assert row["sleeve_grade"] == "VG+"


def test_seller_can_mark_no_sleeve_and_it_satisfies_the_publish_gate():
    # Founder: "I can understand the ones that don't have sleeves but for
    # the one[s] that do we should make that an option." A record with no
    # cover at all has a real, selectable answer now (not just blank), and
    # picking it should be enough to satisfy the sleeve-grading requirement
    # for publishing -- there's nothing left to grade.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = _new_isolated_seller(hw_app, "No Sleeve Option Test Seller")
    hw_app.run("UPDATE sellers SET rules_accepted='Yes' WHERE id=?", (seller_id,))
    product_id = _new_isolated_product(hw_app, seller_id, "No Cover Single")
    hw_app.run("UPDATE products SET listing_status='Draft', image_url='https://example.com/real-photo.jpg', media_grade='VG+', sleeve_grade='' WHERE id=?", (product_id,))
    seller_email = hw_app.get_seller(seller_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,seller_id,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (f"real-seller-uuid-{seller_id}", seller_email, "Real Seller", "Seller", seller_id, "No", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": f"real-seller-uuid-{seller_id}", "email": seller_email, "access_token": "fake"}
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section_auth").set_value("My Inventory").run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(product_id).run()

    at.selectbox(key=f"primary_my_inventory_sleeve_grade_{product_id}").set_value(hw_app.NO_SLEEVE_VALUE).run()
    at.button(key=f"primary_my_inventory_grading_update_{product_id}").click().run()
    at.run()
    assert not at.exception, at.exception
    assert hw_app.df("SELECT sleeve_grade FROM products WHERE id=?", (product_id,)).iloc[0]["sleeve_grade"] == hw_app.NO_SLEEVE_VALUE

    at.selectbox(key="primary_my_inventory_listing_id").set_value(product_id).run()
    at.selectbox(key=f"primary_my_inventory_seller_action_{product_id}").set_value("Live").run()
    at.button(key=f"primary_my_inventory_update_{product_id}").click().run()
    assert not at.exception, at.exception
    assert hw_app.df("SELECT listing_status FROM products WHERE id=?", (product_id,)).iloc[0]["listing_status"] == "Live", (
        "Marking 'No sleeve/cover' should count as a real answer and allow publishing"
    )


def test_bulk_publish_excludes_listings_missing_grading():
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id, seller_email = _setup_approved_seller_for_bulk_publish(hw_app, "Bulk Publish Grading Gate Seller")

    fully_ready = _new_isolated_product(hw_app, seller_id, "Fully Ready Item")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='https://img.discogs.com/ready.jpg', media_grade='VG+', sleeve_grade='VG' WHERE id=?", (fully_ready,))

    no_sleeve_grade = _new_isolated_product(hw_app, seller_id, "Missing Sleeve Grade Item")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='https://img.discogs.com/no-sleeve.jpg', media_grade='VG+', sleeve_grade='' WHERE id=?", (no_sleeve_grade,))

    no_media_grade = _new_isolated_product(hw_app, seller_id, "Missing Media Grade Item")
    hw_app.run("UPDATE products SET listing_status='Draft', price=9.99, image_url='https://img.discogs.com/no-media.jpg', media_grade='', sleeve_grade='VG' WHERE id=?", (no_media_grade,))

    at = _load_my_inventory(hw_app, seller_id, seller_email)
    multiselects = [m for m in at.multiselect if m.key == "primary_my_inventory_bulk_publish_select"]
    assert multiselects, "Expected the bulk publish multiselect to render"
    assert multiselects[0].value == [fully_ready], (
        f"Only the fully-graded item should be offered for bulk publish, got: {multiselects[0].value}"
    )


def test_real_admin_does_not_see_testing_mode_language():
    # Founder, live, signed in as a real admin (not via the Testing mode
    # toggle): "I'm still seeing testing language on here... that looks
    # tacky and unprofessional." The sidebar warning mentioned "Testing
    # mode" unconditionally to every admin regardless of how they actually
    # got in -- confusing/unprofessional-reading noise for someone who is
    # genuinely, deliberately signed in as themselves.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    hw_app.run(
        "INSERT INTO app_users(auth_user_id,email,display_name,account_type,admin_access,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
        ("real-admin-uuid-1", "real-admin-test@example.com", "Real Admin", "Admin", "Yes", "Active", hw_app.now(), hw_app.now()),
    )
    at.session_state["auth_session"] = {"user_id": "real-admin-uuid-1", "email": "real-admin-test@example.com", "access_token": "fake"}
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    assert not at.exception, at.exception

    sidebar_text = " ".join(w.value for w in at.sidebar.warning) + " ".join(i.value for i in at.sidebar.info)
    assert "Testing mode" not in sidebar_text, (
        f"A real, signed-in admin should not see 'Testing mode' language, got: {sidebar_text}"
    )


def test_testing_mode_only_access_still_explains_itself():
    # The flip side: someone who got into the admin area via the Testing
    # mode toggle (not real credentials) genuinely should be told that's
    # why -- this case still needs the explanation.
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    assert not at.exception, at.exception

    sidebar_text = " ".join(w.value for w in at.sidebar.warning) + " ".join(i.value for i in at.sidebar.info)
    assert "Testing mode" in sidebar_text, (
        f"Testing-mode-only access should still explain why Admin is visible, got: {sidebar_text}"
    )


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


def test_buyer_profile_has_one_photo_spot_not_two(monkeypatch):
    # Founder, live screenshot of My Account -> Buying -> My Profile: "There
    # are two place in the buyer section to put profile photos please delete
    # ons [one]." The page showed a standalone preview of the buyer's saved
    # avatar_url image sitting above the "Profile photo - optional" file
    # uploader -- two visually separate photo elements doing overlapping
    # jobs. Keep the single functional upload control, drop the passive
    # preview above it.
    #
    # st.image isn't a typed element AppTest exposes (no at.image / no
    # at.get("image") support), same gap as st.link_button -- so this
    # monkeypatches st.image directly to count real calls instead.
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    buyer_id = _new_isolated_buyer(hw_app, "photo_spot_buyer")
    hw_app.run(
        "UPDATE buyers SET avatar_url=? WHERE id=?",
        ("https://example.com/existing-avatar.png", buyer_id),
    )
    buyer_email = hw_app.get_buyer(buyer_id)["email"]

    image_calls = []
    real_image = hw_app.st.image
    monkeypatch.setattr(hw_app.st, "image", lambda *a, **k: image_calls.append((a, k)) or real_image(*a, **k))

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    _real_buyer_session(at, hw_app, buyer_id, buyer_email)
    goto(at, "My Account")
    at.run()
    assert not at.exception, at.exception

    uploaders = [u for u in at.get("file_uploader") if "Profile photo" in (u.label or "")]
    assert len(uploaders) == 1, f"Expected exactly one profile photo uploader, got {len(uploaders)}"
    assert len(image_calls) == 0, (
        f"Founder: only one photo spot in the buyer section -- expected no standalone avatar preview, got st.image() called {len(image_calls)} time(s)"
    )


def _new_isolated_seller(hw_app, store_name):
    # ensure_seller() reuses whatever seller row already exists in the
    # shared SQLite file (same reasoning as _new_isolated_product below).
    # Give each test needing its own seller/inventory a dedicated row.
    #
    # The email used to be generated deterministically from store_name alone
    # (e.g. "seller-action-dropdown-test-seller@example.com") -- fine within
    # a single suite run since test names differ, but sellers.email has a
    # real UNIQUE constraint, and the local house_of_wax.db file persists
    # across separate pytest invocations rather than resetting each time.
    # Re-running the suite (or even just this one test) against that same
    # file a second time collided with its own leftover row from the first
    # run, throwing "UNIQUE constraint failed: sellers.email" -- not a real
    # app bug, just this helper not being safe to call more than once ever
    # against a given database. A uuid suffix makes every call unique
    # regardless of how many times it's been run before.
    email = store_name.lower().replace(" ", "-") + f"-{uuid.uuid4().hex[:8]}@example.com"
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
    # uuid suffix for the same reason as _new_isolated_seller above -- safe
    # to call more than once against a database that persists across runs.
    email = f"{email_prefix}-{uuid.uuid4().hex[:8]}@example.com"
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
    assert any(k.startswith("ask_item_") for k in button_keys), "Expected the seeded listing card to actually render"
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


def test_listing_card_price_is_not_truncated_st_metric():
    # Founder, live screenshot: listing cards on Search Music showed "Price
    # $..." instead of the actual dollar amount, on every card. Root cause:
    # price_col.metric('Price', money(...)) -- st.metric renders its value in
    # a large fixed font with CSS text-overflow:ellipsis, and these cards are
    # narrow (price_col is half of one column in a multi-card grid), so the
    # price text gets visually clipped to "$..." even though the underlying
    # money() string is always a full, valid amount. Fix: plain text, same
    # pattern already used on the product detail page ('**Price:** $24.99'),
    # which doesn't truncate.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Price Truncation Test Album")
    hw_app.run("UPDATE products SET price=? WHERE id=?", (24.99, product_id))

    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception, at.exception

    price_metrics = [m for m in at.get("metric") if (m.label or "") == "Price"]
    assert not price_metrics, "Listing cards should not use st.metric for price -- it truncates in narrow columns"

    all_text = [m.value for m in at.markdown] + [c.value for c in at.caption]
    assert any("$24.99" in t for t in all_text), (
        "Expected the actual price ($24.99) to render as plain text on the listing card"
    )


# ---------- Listing view analytics (founder: give sellers a feedback loop -- "is this getting looked at") ----------

def test_record_listing_view_increments_dedups_and_skips_sellers_own_view(monkeypatch):
    import app as hw_app
    assert not hw_app.hosted_enabled(), "This test assumes local SQLite mode (no Supabase secrets)"
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "View Count Test Album")

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    def current_views():
        return int(hw_app.df("SELECT view_count FROM products WHERE id=?", (product_id,)).iloc[0]["view_count"] or 0)

    assert current_views() == 0

    # A buyer (not this listing's seller) views it -- counts.
    at.session_state["viewed_listings_this_session"] = set()
    hw_app.record_listing_view(product_id, seller_id)
    assert current_views() == 1, "First view from a non-owner should increment the count"

    # Same session viewing the same listing again -- deduped, no double count.
    hw_app.record_listing_view(product_id, seller_id)
    assert current_views() == 1, "Repeat view in the same session should not inflate the count"

    # The listing's own seller viewing it -- should never count as buyer interest.
    at.session_state["viewed_listings_this_session"] = set()
    monkeypatch.setattr(hw_app, "linked_seller_id", lambda: seller_id)
    monkeypatch.setattr(hw_app, "is_authenticated", lambda: True)
    hw_app.record_listing_view(product_id, seller_id)
    assert current_views() == 1, "The seller viewing their own listing should not count as a view"


def test_product_detail_page_records_a_view():
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Product Detail View Test Album")

    goto(at, "Search Music")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    views = int(hw_app.df("SELECT view_count FROM products WHERE id=?", (product_id,)).iloc[0]["view_count"] or 0)
    assert views == 1, f"Expected visiting the product detail page to record one view, got {views}"


def test_seller_inventory_shows_view_and_watching_counts():
    # Founder: sellers previously had no idea whether a listing was getting
    # looked at. Both signals -- raw views, and buyers actively watching for
    # this exact artist/title via their Want List -- should show up together
    # for the seller on their own inventory management screen.
    import app as hw_app
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Views And Watching Test Album")
    hw_app.run("UPDATE products SET view_count=? WHERE id=?", (7, product_id))
    product = hw_app.df("SELECT artist,title FROM products WHERE id=?", (product_id,)).iloc[0]

    watcher_id = hw_app.create_buyer("watcher_views_test@example.com", "Watcher Views Test")
    hw_app.add_want(watcher_id, product["artist"], product["title"])

    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.session_state["seller_tool_seller_id"] = seller_id
    at.run()
    goto(at, "Seller Dashboard")
    at.radio(key="seller_tools_primary_section").set_value("My Inventory").run()
    at.selectbox(key="primary_my_inventory_listing_id").set_value(int(product_id)).run()
    assert not at.exception, at.exception

    captions = [c.value for c in at.caption]
    assert any("7 views" in c and "1 buyer" in c and "watching" in c for c in captions), (
        f"Expected a '7 views · 1 buyer watching' style caption, got captions: {captions}"
    )


def test_clicking_listing_photo_navigates_away_from_sellers_public_inventory_page():
    # Founder, screen recording (original bug, back when this was a "View"
    # button): browsing a seller's store (Seller Stores -> a seller's
    # public profile -> "Public inventory" section), tapping View/Ask/Offer
    # on a listing card visibly triggers a rerun but lands back on the
    # exact same seller profile page every time. Root cause: seller_stores()
    # checks session_state['seller_id'] and dispatches to seller_profile()
    # unconditionally, with no check for 'product_id' at all. The View
    # button itself is gone now (founder: "the view button can go away
    # because it's not needed" -- the thumbnail is clickable instead), but
    # the same underlying navigation guarantee still has to hold for the
    # photo-click mechanism that replaced it (?open_product= query param,
    # consumed by apply_image_click_navigation()).
    import app as hw_app
    seller_id = _new_isolated_seller(hw_app, "Nav Bug Test Store")
    product_id = _new_isolated_product(hw_app, seller_id, "Nav Bug Test Album")
    hw_app.run("UPDATE products SET listing_status='Live' WHERE id=?", (product_id,))

    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Seller Stores")
    assert not at.exception, at.exception

    open_profile_buttons = [b for b in at.button if b.key == f"openseller{seller_id}"]
    assert open_profile_buttons, "Expected an 'Open public profile' button for the seeded seller"
    open_profile_buttons[0].click().run()
    assert not at.exception, at.exception
    assert any("Public inventory" in s.value for s in at.subheader), "Expected to land on the seller's public inventory"

    assert not [b for b in at.button if b.key == f"item_{product_id}"], (
        "The View button should be gone -- the listing photo is the click-through now"
    )

    # Simulates clicking the listing photo: a real <a href="?open_product=...">
    # (from st.image's link=), not a Streamlit rerun trigger, so exercise it
    # the same way a real browser navigation would -- set the query param
    # and load the page fresh.
    at.query_params["open_product"] = str(product_id)
    at.run()
    assert not at.exception, at.exception

    titles = [t.value for t in at.title]
    assert any("Nav Bug Test Album" in t for t in titles), (
        f"Expected the photo click to navigate to the product detail page (title should mention the album), got titles: {titles}"
    )
    subheaders = [s.value for s in at.subheader]
    assert not any("Public inventory" in s for s in subheaders), (
        "Should have navigated away from the seller's public inventory grid, not stayed on it"
    )
    assert "open_product" not in at.query_params, "The query param should be consumed, not left dangling"


def test_open_product_link_works_from_a_completely_fresh_session():
    # Regression guard for a real bug caught live (not by the test above):
    # st.image's link= renders a real <a href>, which is a full browser
    # navigation -- it drops the WebSocket and starts a BRAND NEW Streamlit
    # session, unlike st.button (an in-app rerun on the SAME session). A
    # fresh session's own default nav logic lands on Home, which never
    # checks product_id at all, so the very first click from any fresh
    # page load did nothing until apply_image_click_navigation() also
    # forced marketplace_navigation to Search Music (same fix
    # apply_share_deep_link() already needed for the same reason). This
    # test deliberately does NOT reuse an existing `at` session/goto() the
    # way the test above does, specifically because that reuse is what let
    # the bug slip past that test in the first place.
    import app as hw_app
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Fresh Session Photo Click Test Album")
    hw_app.run("UPDATE products SET listing_status='Live' WHERE id=?", (product_id,))

    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["open_product"] = str(product_id)
    at.run()
    assert not at.exception, at.exception

    titles = [t.value for t in at.title]
    assert any("Fresh Session Photo Click Test Album" in t for t in titles), (
        f"A fresh session landing on ?open_product= should go straight to that listing's detail page, got titles: {titles}"
    )


def test_seller_stores_directory_hides_non_approved_sellers():
    # Launch-readiness audit: the public "Seller Stores" directory had no
    # status filter at all -- Pending and Suspended sellers (and a leftover
    # "Demo Wax Seller" test row from ensure_seller(), found live in
    # production) all showed up next to real Approved sellers. A skeptical
    # prospective seller checking whether House Of Wax is a real, active
    # marketplace before joining is exactly the audience this undercuts.
    import app as hw_app
    approved_id = _new_isolated_seller(hw_app, "Approved Directory Test Store")
    pending_id = _new_isolated_seller(hw_app, "Pending Directory Test Store")
    hw_app.run("UPDATE sellers SET status='Pending Seller Approval' WHERE id=?", (pending_id,))
    suspended_id = _new_isolated_seller(hw_app, "Suspended Directory Test Store")
    hw_app.run("UPDATE sellers SET status='Suspended Seller' WHERE id=?", (suspended_id,))

    at = fresh_app()
    goto(at, "Seller Stores")
    assert not at.exception, at.exception

    subheaders = [s.value for s in at.subheader]
    assert any("Approved Directory Test Store" in s for s in subheaders), (
        "Approved seller should appear in the public directory"
    )
    assert not any("Pending Directory Test Store" in s for s in subheaders), (
        "Pending seller should not appear in the public directory"
    )
    assert not any("Suspended Directory Test Store" in s for s in subheaders), (
        "Suspended seller should not appear in the public directory"
    )


def test_inquiry_and_offer_forms_clear_on_submit():
    # Founder: "I want it to reset and be ready [to] ask another [question]
    # or be able to get another offer" -- after a successful send, the form
    # still held the just-sent text/amount with no visible change besides a
    # success banner, reading as "stuck" rather than ready for another.
    #
    # st.form's clear_on_submit=True is the correct fix, but Streamlit's
    # AppTest harness does not actually simulate the clearing behavior --
    # confirmed with a minimal isolated repro app outside this codebase,
    # where a submitted text_area's value stays populated post-submit even
    # with clear_on_submit=True set. What AppTest *does* expose reliably is
    # the form's own protobuf config, which is what this test checks instead
    # of the unsimulated runtime behavior.
    import app as hw_app
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Form Reset Test Album")
    hw_app.run("UPDATE products SET listing_status='Live' WHERE id=?", (product_id,))
    buyer_id = _new_isolated_buyer(hw_app, "form_reset_buyer")
    buyer_email = hw_app.get_buyer(buyer_id)["email"]

    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    _real_buyer_session(at, hw_app, buyer_id, buyer_email)
    goto(at, "Search Music")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    key_prefix = f"product_{product_id}"
    forms = {f.proto.form.form_id: f for f in at.get("form")}
    assert forms.get(f"inquiry_form_{key_prefix}") and forms[f"inquiry_form_{key_prefix}"].proto.form.clear_on_submit, (
        "Inquiry form should clear on submit so the buyer can ask another question right away"
    )
    assert forms.get(f"offer_form_{key_prefix}") and forms[f"offer_form_{key_prefix}"].proto.form.clear_on_submit, (
        "Offer form should clear on submit so the buyer can make another offer right away"
    )


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


def test_product_detail_has_no_duplicate_ask_offer_buttons():
    # Founder: "there are some redundancies. The buy button is very low on
    # the screen and is hard to find." The old page had Ask/Offer as quick
    # buttons right under the price that only pre-expanded the SAME two
    # forms rendered again, full-width, under a separate "Buyer actions"
    # header after Description/Video -- Add to Cart lived only down there.
    # Buyer actions now render exactly once, right under the price.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()

    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "No Duplicate Buttons Test Album")

    goto(at, "Search Music", area_key="marketplace_navigation")
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception

    button_keys = [b.key for b in at.button if b.key]
    assert not any(k.startswith("detail_ask_top_") for k in button_keys), (
        f"The old duplicate top Ask button should be gone, got: {button_keys}"
    )
    assert not any(k.startswith("detail_offer_top_") for k in button_keys), (
        f"The old duplicate top Offer button should be gone, got: {button_keys}"
    )
    subheaders = [s.value for s in at.subheader]
    assert "Buyer actions" not in subheaders, (
        f"The separate 'Buyer actions' section should be gone -- merged into one place near the price, got: {subheaders}"
    )
    # The real, single Ask/Offer/Cart entry points must still all be present.
    assert any(k == f"cart_add_detail_{product_id}" for k in button_keys), "Expected the Add to Cart button"
    expander_labels = [e.label for e in at.get("expander")]
    assert "Ask About This Item / Contact Seller" in expander_labels
    assert "Make an Offer" in expander_labels


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


def test_ai_research_queue_shows_fact_check_verdict():
    # Founder: "Can we make sure we double check these before I see it?"
    # The fact-check verdict must be the first thing shown on a draft --
    # PASS shown as a clear positive signal, NEEDS REVIEW as a warning that
    # can't be missed, and older drafts saved before this column existed
    # (fact_check_notes NULL/empty) fall back to the old "verify before
    # publishing" caption instead of silently looking checked.
    import app as hw_app
    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    ts = hw_app.now()
    hw_app.run(
        """INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,source_type,sources,fact_check_notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("Fact Check PASS Test Article", "Genre Education", "Collectors", "Beginner",
         "s", "b", "h", "Draft", "No", "AI Research", "", "PASS: confirmed via 3 sources.", ts, ts),
    )
    hw_app.run(
        """INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,source_type,sources,fact_check_notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("Fact Check NEEDS REVIEW Test Article", "Genre Education", "Collectors", "Beginner",
         "s", "b", "h", "Draft", "No", "AI Research", "", "NEEDS REVIEW: could not confirm the release date.", ts, ts),
    )
    hw_app.run(
        """INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,source_type,sources,fact_check_notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("Fact Check Missing Test Article (older draft)", "Genre Education", "Collectors", "Beginner",
         "s", "b", "h", "Draft", "No", "AI Research", "", None, ts, ts),
    )

    at.sidebar.radio(key="house_of_wax_area").set_value("House Of Wax Admin").run()
    at.sidebar.radio(key="admin_navigation").set_value("Content Admin").run()
    assert not at.exception, at.exception

    success_texts = [s.value for s in at.success]
    warning_texts = [w.value for w in at.warning]
    caption_texts = [c.value for c in at.caption]

    assert any("PASS: confirmed via 3 sources" in t for t in success_texts), (
        "A PASS verdict should render as a success banner"
    )
    assert any("NEEDS REVIEW: could not confirm the release date" in t for t in warning_texts), (
        "A NEEDS REVIEW verdict should render as a warning banner, impossible to miss"
    )
    assert any("No fact-check recorded" in t for t in caption_texts), (
        "A draft with no fact_check_notes (older draft) should fall back to the old verify-before-publishing caption"
    )


# ---------- Trending Now: Style & Sound (founder: steer the audience toward trending styles/artists) ----------

def _import_researcher_script():
    # scripts/knowledge_hub_researcher.py is a standalone script (run via
    # GitHub Actions, not imported by app.py) -- import it directly by file
    # path rather than needing an __init__.py under scripts/. Safe to import
    # with no env vars/secrets set: env() is only called inside main(), never
    # at module level.
    import importlib.util
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    spec = importlib.util.spec_from_file_location(
        "knowledge_hub_researcher", os.path.join(repo_root, "scripts", "knowledge_hub_researcher.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_knowledge_categories_stay_in_sync_with_researcher_script():
    # scripts/knowledge_hub_researcher.py duplicates KNOWLEDGE_CATEGORIES
    # (documented reason: app.py runs setup() -- Streamlit secrets, DB
    # connections -- at import time, so it isn't safely importable from a
    # bare script). Nothing previously enforced the two lists actually
    # match. Guards against silent drift: if only one list gets a new
    # category, either the daily research job can produce a category the
    # app doesn't recognize (falls back to a wrong default), or the app
    # offers a category the research job never knows to use.
    import app as hw_app
    researcher = _import_researcher_script()
    assert researcher.KNOWLEDGE_CATEGORIES == hw_app.KNOWLEDGE_CATEGORIES, (
        "scripts/knowledge_hub_researcher.py's KNOWLEDGE_CATEGORIES has drifted from app.py's -- keep them in sync"
    )


def test_trending_category_available_in_knowledge_hub_and_research_job():
    # Founder: wants a feature steering the audience toward trending styles,
    # new artists, and music/entertainment culture. New category, both
    # sides: the public Knowledge Hub category filter, and the research job
    # that can be pointed at it.
    import app as hw_app
    assert "Trending Now: Style & Sound" in hw_app.KNOWLEDGE_CATEGORIES

    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()
    goto(at, "Knowledge Hub")
    assert not at.exception, at.exception
    cat_selects = [s for s in at.selectbox if s.label == "Category"]
    assert cat_selects, "Expected a Category filter on the Knowledge Hub"
    assert "Trending Now: Style & Sound" in cat_selects[0].options

    researcher = _import_researcher_script()
    assert "Trending Now: Style & Sound" in researcher.KNOWLEDGE_CATEGORIES


def test_researcher_is_trending_day_cadence(monkeypatch):
    # Founder: wants trending content to actually show up, not just be one
    # option among 11 that the model might rarely pick on its own. Guarantee
    # a predictable cadence (every 3rd day) instead of leaving it to chance.
    researcher = _import_researcher_script()
    import datetime as dt_module

    class FrozenDay3(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 3, tzinfo=tz)  # day-of-year 3 -> 3 % 3 == 0

    class FrozenDay4(dt_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 4, tzinfo=tz)  # day-of-year 4 -> 4 % 3 != 0

    monkeypatch.setattr(researcher, "datetime", FrozenDay3)
    assert researcher.is_trending_day() is True

    monkeypatch.setattr(researcher, "datetime", FrozenDay4)
    assert researcher.is_trending_day() is False


def test_researcher_manual_trigger_always_forces_trending_day(monkeypatch):
    # Founder: "Trigger the job manually so I can see one now." A manual
    # workflow_dispatch run on a non-cadence day would otherwise fall back
    # to free category choice and might not produce a Trending Now article
    # at all -- defeating the point of triggering it manually to see one.
    # GITHUB_EVENT_NAME is a default GitHub Actions env var (no workflow
    # YAML changes needed, which matters: this repo's push credential lacks
    # the `workflow` scope needed to edit .github/workflows/*).
    researcher = _import_researcher_script()
    import datetime as dt_module

    class FrozenDay4(dt_module.datetime):  # 4 % 3 != 0 -- not a cadence day
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 1, 4, tzinfo=tz)

    monkeypatch.setattr(researcher, "datetime", FrozenDay4)

    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    assert researcher.is_trending_day() is False, "Scheduled/local runs on a non-cadence day should not force trending"

    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    assert researcher.is_trending_day() is True, "A manual trigger should always force a trending article"

    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    assert researcher.is_trending_day() is False, "The regular cron trigger should still respect the 3-day cadence"


def test_researcher_forces_trending_category_and_prompt_has_guidance():
    # Verifies the actual prompt sent to Claude, not just that a parameter
    # exists -- on a forced trending day, the system prompt must lock the
    # topic to the Trending Now category and include the "must be genuinely
    # current" guidance so the model doesn't just write another evergreen
    # article under a new label.
    researcher = _import_researcher_script()

    captured = {}

    class FakeTextBlock:
        type = "text"
        text = (
            '{"title":"t","category":"Trending Now: Style & Sound","audience":"Everyone",'
            '"level":"Beginner","summary":"s","body":"b","house_tip":"h"}'
        )
        citations = None

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    article, sources = researcher.research_article(
        FakeClient(), [], forced_category="Trending Now: Style & Sound"
    )
    assert article["category"] == "Trending Now: Style & Sound"
    assert sources == []
    system_prompt = captured["system"]
    assert "MUST be in this category: Trending Now: Style & Sound" in system_prompt
    assert "genuinely current" in system_prompt


def test_researcher_captures_sources_from_web_search_results_without_inline_citations():
    # Real bug found reviewing the first live Trending Now draft ("Boards of
    # Canada Are Back..."): it saved with 0 sources despite the job
    # presumably searching the web as instructed. Root cause: the system
    # prompt requires the FINAL message to be ONLY a raw JSON object, so
    # Claude's inline-citation markup (which attaches to cited spans of
    # prose) never has anywhere to attach on a JSON-only answer -- even when
    # real searches happened. Sources must also be pulled from the actual
    # web_search_tool_result blocks Claude received, not just from citations
    # on the final text block.
    researcher = _import_researcher_script()

    class FakeSearchResult:
        url = "https://example.com/boards-of-canada-inferno"
        title = "Boards of Canada announce Inferno"

    class FakeSearchResultBlock:
        type = "web_search_tool_result"
        content = [FakeSearchResult()]

    class FakeTextBlock:
        type = "text"
        text = (
            '{"title":"t","category":"Trending Now: Style & Sound","audience":"Everyone",'
            '"level":"Beginner","summary":"s","body":"b","house_tip":"h"}'
        )
        citations = None  # JSON-only final answer -- no inline citation markup possible

    class FakeResponse:
        content = [FakeSearchResultBlock(), FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    article, sources = researcher.research_article(FakeClient(), [], forced_category=None)
    assert sources, "Expected sources to be captured from the web_search_tool_result block"
    assert ("Boards of Canada announce Inferno", "https://example.com/boards-of-canada-inferno") in sources


def test_researcher_fact_check_article_passes_clean_draft():
    # Founder: "Can we make sure we double check these before I see it?"
    # A second Claude call, given the already-drafted article, verifies its
    # claims with fresh web search before the draft is ever saved.
    researcher = _import_researcher_script()

    captured = {}

    class FakeTextBlock:
        type = "text"
        text = '{"verdict":"PASS","notes":"Confirmed release date and label via 3 sources."}'
        citations = None

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    article = {"title": "t", "summary": "s", "body": "b", "house_tip": "h"}
    verdict, notes, sources = researcher.fact_check_article(FakeClient(), article)
    assert verdict == "PASS"
    assert "3 sources" in notes
    assert sources == []
    assert "fact-checker" in captured["system"].lower()
    assert article["body"] in captured["messages"][0]["content"]


def test_researcher_fact_check_article_flags_needs_review():
    researcher = _import_researcher_script()

    class FakeTextBlock:
        type = "text"
        text = '{"verdict":"NEEDS REVIEW","notes":"Could not confirm the claimed chart position."}'
        citations = None

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    article = {"title": "t", "summary": "s", "body": "b", "house_tip": "h"}
    verdict, notes, sources = researcher.fact_check_article(FakeClient(), article)
    assert verdict == "NEEDS REVIEW"
    assert "chart position" in notes


def test_researcher_save_draft_stores_fact_check_notes(monkeypatch):
    researcher = _import_researcher_script()

    captured = {}

    class FakeResponse:
        ok = True
        def json(self):
            return [{"id": 99}]

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(researcher.requests, "post", fake_post)

    article = {"title": "t", "category": "Trending Now: Style & Sound", "audience": "Everyone",
               "level": "Beginner", "summary": "s", "body": "b", "house_tip": "h"}
    researcher.save_draft("https://example.supabase.co", "fake-key", article, [], "PASS: confirmed via 3 sources.")
    assert captured["json"]["fact_check_notes"] == "PASS: confirmed via 3 sources."


def test_researcher_free_choice_mode_still_lists_trending_category():
    # Regression guard for the change above -- on a non-forced day, the
    # model should still see Trending Now as a normal option among the
    # others, and still get the "must be current" guidance for it.
    researcher = _import_researcher_script()

    captured = {}

    class FakeTextBlock:
        type = "text"
        text = (
            '{"title":"t","category":"Vinyl Grading School","audience":"Everyone",'
            '"level":"Beginner","summary":"s","body":"b","house_tip":"h"}'
        )
        citations = None

    class FakeResponse:
        content = [FakeTextBlock()]

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeClient:
        messages = FakeMessages()

    researcher.research_article(FakeClient(), [], forced_category=None)
    system_prompt = captured["system"]
    assert "- Trending Now: Style & Sound" in system_prompt
    assert "genuinely current" in system_prompt
    assert "MUST be in this category" not in system_prompt


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

def test_report_listing_button_is_gone_from_buyer_facing_pages():
    # Founder: "Please remove the report listing button. That can be done
    # in customer support." Report Seller (on a seller's public profile)
    # is a separate, intentionally-kept flow -- only the per-listing Report
    # Listing button/form goes away, replaced by the general Support page.
    import app as hw_app
    seller_id = hw_app.ensure_seller()
    product_id = _new_isolated_product(hw_app, seller_id, "Report Button Removal Test Album")
    hw_app.run("UPDATE products SET listing_status='Live' WHERE id=?", (product_id,))

    at = AppTest.from_file("app.py", default_timeout=30)
    at.session_state["testing_mode_enabled"] = True
    at.run()

    # Card view (Search Music grid).
    goto(at, "Search Music", area_key="marketplace_navigation")
    assert not at.exception, at.exception
    expander_labels = [e.label for e in at.get("expander")]
    assert "Report Listing" not in expander_labels, f"Report Listing should be gone from listing cards, got: {expander_labels}"

    # Full listing detail page.
    at.session_state["product_id"] = int(product_id)
    at.run()
    assert not at.exception, at.exception
    expander_labels = [e.label for e in at.get("expander")]
    assert "Report Listing" not in expander_labels, f"Report Listing should be gone from the listing detail page, got: {expander_labels}"
    all_text = " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)
    assert "Support" in all_text, "Expected the listing detail page to point buyers at Support instead"

    # Report Seller must still be intact -- this removal is listing-specific.
    if "product_id" in at.session_state:
        del at.session_state["product_id"]
    at.session_state["seller_id"] = int(seller_id)
    at.run()
    assert not at.exception, at.exception
    expander_labels = [e.label for e in at.get("expander")]
    assert "Report Seller" in expander_labels, f"Report Seller should still be available on the seller profile, got: {expander_labels}"


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


def test_notify_admins_new_support_request_emails_every_admin(monkeypatch):
    # Founder: a new support request only ever showed up if someone
    # remembered to open the admin panel and check -- no alert otherwise.
    import app as hw_app
    monkeypatch.setattr(hw_app, "admin_email_allowlist", lambda: ["admin1@example.com", "admin2@example.com"])
    sent = []
    monkeypatch.setattr(
        hw_app, "send_email",
        lambda to_email, subject, html_body: sent.append((to_email, subject, html_body)) or True,
    )

    hw_app.notify_admins_new_support_request("Jamie", "buyer@example.com", "Payment issue", "My order never showed up.")

    assert len(sent) == 2, f"Expected one email per configured admin, got: {sent}"
    assert [s[0] for s in sent] == ["admin1@example.com", "admin2@example.com"]
    for to_email, subject, body in sent:
        assert "Payment issue" in subject
        assert "buyer@example.com" in body
        assert "My order never showed up." in body


def test_notify_admins_new_support_request_noop_when_no_admins_configured(monkeypatch):
    import app as hw_app
    monkeypatch.setattr(hw_app, "admin_email_allowlist", lambda: [])
    calls = []
    monkeypatch.setattr(hw_app, "send_email", lambda *a, **k: calls.append(a) or True)
    hw_app.notify_admins_new_support_request("Jamie", "buyer@example.com", "General", "Hello")
    assert calls == [], "Should not attempt to send any email when no admins are configured"


def test_support_form_submission_actually_emails_the_admin(monkeypatch):
    # Integration-level proof of the fix, not just the helper function in
    # isolation: submitting the real support form must trigger a real
    # outbound email call to the configured admin address.
    import app as hw_app
    monkeypatch.setenv("ADMIN_EMAILS", "founder@example.com")
    # send_email() reads RESEND_API_KEY via st.secrets.get(), not
    # config_value() -- so unlike ADMIN_EMAILS above, an env var alone
    # doesn't reach it. st.secrets blocks plain attribute assignment
    # entirely (raises TypeError), so use its own public API for injecting
    # a secret programmatically; it persists across AppTest's reruns since
    # it's the same secrets singleton each time (only the script's own
    # top-level `def`s get rebound on rerun, not imported module state).
    hw_app.st.secrets.merge_programmatic_secrets({"RESEND_API_KEY": "fake-resend-key-for-tests"})
    calls = []

    class FakeResponse:
        status_code = 200

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append((url, json))
        return FakeResponse()

    monkeypatch.setattr(hw_app.requests, "post", fake_post)

    at = AppTest.from_file("app.py", default_timeout=30)
    at.query_params["support"] = "1"
    at.run()
    assert not at.exception, at.exception

    email_input = next(t for t in at.text_input if (t.label or "").startswith("Your email"))
    email_input.set_value("worried-buyer@example.com").run()
    message_input = next(t for t in at.text_area if (t.label or "").startswith("Tell us what is going on"))
    message_input.set_value("My package never arrived.").run()
    submit_buttons = [b for b in at.button if (b.label or "") == "Send to House Of Wax"]
    submit_buttons[0].click().run()
    assert not at.exception, at.exception

    assert calls, "Expected the support form submission to trigger a real send_email -> requests.post call"
    _, payload = calls[0]
    assert payload["to"] == ["founder@example.com"], f"Expected the admin address as recipient, got: {payload['to']}"
    assert "worried-buyer@example.com" in payload["html"]
    assert "My package never arrived." in payload["html"]


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

    for table in ["support_requests", "release_photo_library", "tester_feedback", "listing_reports", "newsletter_signups"]:
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


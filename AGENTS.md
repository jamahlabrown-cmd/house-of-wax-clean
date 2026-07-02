# AGENTS.md - House Of Wax Coding Instructions

## Project identity

This repo is the working prototype for House Of Wax, a Streamlit + SQLite marketplace/community platform for records, music culture, collectibles, merch, clothing, memorabilia, and seller storefronts.

House Of Wax is not just a record store. It is a marketplace, knowledge hub, trust layer, and culture platform.

## Current working version

Current target version:

V25.24 FULL LAUNCH AUDIT + BUG FIX SPRINT

The live Streamlit app must show this marker near the top of the app:

Running V25.24 FULL LAUNCH AUDIT + BUG FIX SPRINT

## Critical deployment rule

The live Streamlit app runs from the root-level file:

app.py

Do not create a nested app.py.
Do not rename app.py.
Do not put the real app inside a folder.
Do not create a second competing app file.

## Required root files

The repo should include:

* app.py
* requirements.txt
* runtime.txt
* AGENTS.md

Optional context files may include:

* HOUSE_OF_WAX_PROJECT_CONTEXT.md
* HOUSE_OF_WAX_VERSION_HISTORY.md
* HOUSE_OF_WAX_PREFLIGHT_CHECKLIST.md

## Tech stack

* Python
* Streamlit
* SQLite
* pandas
* requests

## Install / run commands

Use:

pip install -r requirements.txt

python -m py_compile app.py

streamlit run app.py

## Pre-flight checks before every commit or PR

Before finishing any task, check:

1. app.py compiles with python -m py_compile app.py
2. app.py exists at the repo root
3. requirements.txt exists
4. runtime.txt exists
5. The version marker is updated and visible
6. No duplicate Streamlit literal widget keys were introduced
7. No old broken variable named app_app_settings exists
8. No multi-window search code using window.open exists unless explicitly requested
9. No old version marker is left behind
10. Any new button/form/input has a unique key
11. Database/table changes are backwards compatible
12. Existing seller tools still load
13. Existing My House of Wax navigation still loads

## Streamlit duplicate key warning

This app has previously crashed because the same widget appeared in multiple areas.

When adding widgets inside reusable functions, use a key_prefix pattern:

def example_widget(key_prefix="main"):
st.button("Example", key=f"example_button_{key_prefix}")

Do not use static keys in reusable components.

Bad:

st.button("Run source health check", key="source_health_check_button")

Good:

st.button("Run source health check", key=f"source_health_check_button_{key_prefix}")

## Current search behavior

The current search flow should work like this:

1. Seller enters barcode and/or artist and title.
2. Smart Search runs inside House Of Wax.
3. Artist and title must be searched together first.
4. Results are ranked.
5. One recommended best match is shown.
6. Seller can click Use recommended match.
7. Backup source links are available only if smart search fails.

Do not revert to opening many browser tabs.
Do not make the user click many different search links as the main flow.

## Current search sources

The app may use:

* House Of Wax internal release database
* Barcode cache
* Discogs automatic search
* Apple/iTunes album search
* MusicBrainz search
* Backup manual links only when needed

## House Of Wax product rule

For music items:

* Records, CDs, and cassettes can use release cover art found by barcode/search.
* Seller should still be able to add condition photos.

For non-music items:

* Clothing, dolls, memorabilia, merch, accessories, and collectibles should use exact seller photos or official product images.

## Business rules

House Of Wax is a platform/marketplace.

House Of Wax can also have an official seller account.

Seller content is not the main content strategy.

The Knowledge Hub is House Of Wax-owned education, culture, history, discovery, trust, and marketplace guidance.

## Current known login/test accounts

Seller test:

* Demo Seller: [seller@test.com](mailto:seller@test.com) / test123
* House Of Wax Official: [official@houseofwax.com](mailto:official@houseofwax.com) / official123

Buyer test:

* [buyer@test.com](mailto:buyer@test.com)

## Team rule

Work carefully. This is an active founder-led project.

Do not make unnecessary broad rewrites. Patch the smallest safe area unless a larger refactor is clearly needed.

Explain what changed, what was tested, and what risks remain.

The founder leads the vision. The coding assistant protects the build.

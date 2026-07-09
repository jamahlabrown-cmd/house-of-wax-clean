# House Of Wax Preflight Checklist

Before every patch, Codex must check the following.

## File structure

- app.py exists at the repo root.
- requirements.txt exists at the repo root.
- runtime.txt exists at the repo root.
- No nested replacement app.py was created.
- app.py was not renamed.

## Version

- APP_VERSION is updated.
- The displayed version marker matches APP_VERSION.
- Old version marker is removed.

## Python check

Run:

python -m py_compile app.py

The patch is not complete unless app.py compiles.

## Imports

Check needed imports exist:

- streamlit
- pandas
- sqlite3
- requests
- re

If a new library is added, it must also be added to requirements.txt.

## Streamlit widget keys

Check:

- No duplicate literal Streamlit keys.
- Reusable components use key_prefix.
- New buttons, forms, inputs, and selectboxes have unique keys.

Bad example:

st.button("Run source health check", key="source_health_check_button")

Good example:

st.button("Run source health check", key=f"source_health_check_button_{key_prefix}")

## Database

Check:

- Existing tables are not broken.
- New table changes use CREATE TABLE IF NOT EXISTS.
- Insert statements match the number of columns and placeholders.
- Existing test/demo data still works.

## Search behavior

Check:

- Smart Search does not open many windows.
- Smart Search searches inside the app.
- Artist and title are combined first.
- Search falls back only after combined search.
- Best match card appears.
- Use recommended match works.
- Backup source links are backup only.

## Known bad code to avoid

Do not introduce:

- app_app_settings
- window.open for main search
- static duplicate button keys
- nested app.py
- renamed app file
- old V25.10 multi-window behavior

## Current search standard

The current search standard is:

1. Seller enters barcode and/or artist and title.
2. Smart Search runs inside House Of Wax.
3. Artist and title are searched together first.
4. Results are ranked.
5. One recommended best match is shown.
6. Seller can click Use recommended match.
7. Backup source links are available only if smart search fails.

## Communication

When reporting back, Codex should state:

- What changed
- What was tested
- What was not live-tested
- What risks remain
- What the next step should be

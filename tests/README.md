# House Of Wax — smoke tests

Run with:

```bash
pip install -r requirements-dev.txt
pytest tests/test_smoke.py -v
```

No Supabase secrets needed. These run against the local SQLite fallback
(`hosted_enabled()` is False with no `SUPABASE_URL`/`SUPABASE_ANON_KEY`
configured), using Streamlit's built-in `AppTest` -- no browser, no server.

## What's covered

- Every marketplace page renders without raising an exception
- Create Account form validation (short password, mismatched confirmation,
  invalid email, missing fields)
- Add Inventory's Step 1 structure: the Artist/Title fields live outside
  `st.form` (regression guard for the V25.43.84 fix -- if a future edit
  moves them back inside the form, this fails loudly instead of silently
  breaking the price box again)
- The price/market-data box shows an explicit reason when no Discogs
  token is configured, instead of silently showing nothing

Each test in `test_smoke.py` was verified to actually fail against the
pre-fix code before being added -- they're regression guards for bugs
that were real, not tests written to match whatever the code already does.

## What's NOT covered yet

Anything that only happens against real Supabase Auth -- specifically the
sign-up/sign-in email-confirmation messaging fixed in V25.43.86. With no
secrets configured, `hosted_enabled()` is False and the app uses local
SQLite auth instead, so that code path never runs here.

Covering it properly needs a **staging Supabase project** (separate from
production, so test signups don't land in real user data) with its
credentials available to the test run as environment variables or a local
`.streamlit/secrets.toml` (gitignored, never committed). Once that exists,
add a second test module (e.g. `test_hosted_auth.py`) that skips itself
automatically when those secrets aren't present, so the free/local suite
here keeps working for everyone without needing them.

## Adding new tests

When you fix a bug, add a test for it here first -- confirm the test
fails against the old behavior (check out the commit before your fix and
run just that test), then confirm it passes against your fix. A test that
was never seen to fail hasn't proven anything.

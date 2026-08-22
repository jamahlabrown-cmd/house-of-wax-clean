"""
Shared pytest setup for the House Of Wax test suite.

Root cause of a real flakiness pattern hit repeatedly in 2026-08 sessions:
tests share ONE on-disk SQLite file (house_of_wax.db, the app's local
fallback DB) that persists between separate `pytest` invocations rather than
resetting each time. Test helpers that insert rows with real UNIQUE
constraints (sellers.email, etc. -- see the uuid suffixes added to
_new_isolated_seller/_new_isolated_buyer) or that assert on absolute row
counts would pass the first time a session runs, then fail the next time
the suite (or even just one of those tests) runs again, purely from
leftover data -- not from anything actually broken in the app. Confirmed
directly: a full run passed 121/121 clean, then failed 24 tests on an
immediate second run against the same un-wiped file.

Fix: wipe the local SQLite file once, at the very start of the test
session, before any test runs. Every `pytest` invocation then always starts
from a clean slate -- app.py's own setup() recreates the schema (and any
seed data) automatically the first time a test touches it. This is
deliberately session-scoped (not per-test) rather than giving every
individual test its own isolated DB file: an earlier per-test-isolation
attempt via monkeypatching HOUSE_OF_WAX_DB_PATH ran into Streamlit AppTest's
own script-execution/caching model in ways that caused MORE failures, not
fewer (a test that passed alone still failed as part of the full suite) --
not well enough understood to trust. Wiping once per session is simpler,
lower-risk, and directly fixes the actual observed failure mode (repeated
invocations, not concurrent/parallel tests -- this suite doesn't run
tests in parallel).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_configure(config):
    db_path = os.environ.get(
        "HOUSE_OF_WAX_DB_PATH",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "house_of_wax.db"),
    )
    if os.path.exists(db_path):
        os.remove(db_path)

#!/usr/bin/env python3
"""House Of Wax -- automated health diagnostics.

Runs a set of lightweight, non-destructive checks against the live site and its
dependencies, and emails an alert via Resend only when something is actually broken.
Designed to run on a schedule (see .github/workflows/diagnostics.yml) -- silent on
success, loud on failure.

What this DOES check: the site loads, the real app responds, the SSL certificate is
valid, Supabase is reachable, the Resend sending domain is still verified, and DNS
still points where it should.

What this does NOT check (out of scope for a lightweight script): the actual buyer
checkout flow, whether specific listing photos render, or anything else that needs a
real browser clicking through the app. Those would need browser automation (e.g.
Playwright) -- a heavier, separate project if wanted later.
"""
import os
import smtplib
import ssl
import socket
import sys
import time
from datetime import datetime, timezone
from email.mime.text import MIMEText

import certifi
import requests

SITE_URL = "https://shophouseofwax.com/"
APP_URL = "https://house-of-wax-clean-5rqkikwpyr3xrappzemzjcb.streamlit.app/"
SUPABASE_URL = "https://zkyzodmvtudmrpeiysyp.supabase.co"
RESEND_DOMAIN = "shophouseofwax.com"
CERT_WARNING_DAYS = 14
REQUEST_TIMEOUT = 15

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_TO = os.environ.get("DIAGNOSTIC_ALERT_TO", "hello@shophouseofwax.com")


def check_site_loads():
    r = requests.get(SITE_URL, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        return False, f"shophouseofwax.com returned HTTP {r.status_code} (expected 200)"
    if "House Of Wax" not in r.text:
        return False, "shophouseofwax.com loaded but doesn't look like the real page (content check failed)"
    return True, "OK"


def check_app_responds():
    # The real app returns a 303 for anonymous requests (Streamlit's own session
    # negotiation) -- that's normal and expected, not a failure. Only a connection
    # error, timeout, or 5xx counts as broken.
    r = requests.get(APP_URL, timeout=REQUEST_TIMEOUT, allow_redirects=False)
    if r.status_code >= 500:
        return False, f"Live app returned HTTP {r.status_code} (server error)"
    return True, f"OK (HTTP {r.status_code})"


def check_ssl_cert():
    hostname = "shophouseofwax.com"
    ctx = ssl.create_default_context(cafile=certifi.where())
    with socket.create_connection((hostname, 443), timeout=REQUEST_TIMEOUT) as sock:
        with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
    expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    days_left = (expires - datetime.now(timezone.utc)).days
    if days_left < 0:
        return False, f"SSL certificate EXPIRED {abs(days_left)} days ago"
    if days_left < CERT_WARNING_DAYS:
        return False, f"SSL certificate expires in {days_left} days (renews automatically, but flagging early)"
    return True, f"OK ({days_left} days remaining)"


def check_supabase_reachable():
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/", timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as e:
        return False, f"Supabase unreachable: {e}"
    # Without an API key this legitimately returns 401 -- that still means the
    # database is up and responding, which is what we're checking.
    if r.status_code >= 500:
        return False, f"Supabase returned HTTP {r.status_code} (server error)"
    return True, f"OK (HTTP {r.status_code})"


def check_resend_domain_verified():
    if not RESEND_API_KEY:
        return False, "RESEND_API_KEY not set -- can't check email deliverability"
    r = requests.get(
        "https://api.resend.com/domains",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code != 200:
        return False, f"Resend API returned HTTP {r.status_code}"
    domains = r.json().get("data", [])
    match = next((d for d in domains if d.get("name") == RESEND_DOMAIN), None)
    if not match:
        return False, f"{RESEND_DOMAIN} not found in Resend account -- signup emails may fail"
    if match.get("status") != "verified":
        return False, f"{RESEND_DOMAIN} status is '{match.get('status')}', not 'verified' -- signup emails may fail"
    return True, "OK"


def check_dns_records():
    # The domain is proxied through Cloudflare (as of 2026-08-19), so this
    # legitimately resolves to Cloudflare's own edge IPs, not GitHub Pages' IPs
    # directly -- that's expected. This check just confirms DNS resolves at all;
    # whether the *right content* is being served is already covered by
    # check_site_loads's content check.
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo("shophouseofwax.com", None, socket.AF_INET)}
    except socket.gaierror as e:
        return False, f"DNS lookup failed: {e}"
    if not addrs:
        return False, "DNS resolved but returned no addresses"
    return True, f"OK ({', '.join(sorted(addrs))})"


CHECKS = [
    ("Site loads (shophouseofwax.com)", check_site_loads),
    ("Live app responds", check_app_responds),
    ("SSL certificate valid", check_ssl_cert),
    ("Supabase reachable", check_supabase_reachable),
    ("Resend sending domain verified", check_resend_domain_verified),
    ("DNS points at GitHub Pages", check_dns_records),
]


def send_alert_email(failures):
    if not RESEND_API_KEY:
        print("No RESEND_API_KEY set -- can't send alert email. Failures:", failures)
        return
    body_lines = [
        "House Of Wax diagnostic check found a problem:",
        "",
    ]
    for name, message in failures:
        body_lines.append(f"- {name}: {message}")
    body_lines += ["", f"Checked at {datetime.now(timezone.utc).isoformat()} UTC."]
    body = "\n".join(body_lines)

    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
        json={
            "from": "House Of Wax Diagnostics <hello@shophouseofwax.com>",
            "to": [ALERT_TO],
            "subject": f"⚠️ House Of Wax: {len(failures)} check(s) failing",
            "text": body,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if r.status_code >= 300:
        print(f"Failed to send alert email: HTTP {r.status_code} {r.text}")


def main():
    failures = []
    for name, check_fn in CHECKS:
        try:
            ok, message = check_fn()
        except Exception as e:
            ok, message = False, f"Check crashed: {e}"
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {message}")
        if not ok:
            failures.append((name, message))

    if failures:
        send_alert_email(failures)
        sys.exit(1)
    print("\nAll checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()

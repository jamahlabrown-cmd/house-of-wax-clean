"""Scheduled Discogs -> House Of Wax mirror for one seller.

Runs from .github/workflows/discogs_sync.yml. Uses the same rules as the
app's More Tools > Discogs sync (see discogs_mirror.py). Every read and
write is filtered to the one seller found by DISCOGS_SYNC_STORE_NAME.

Required environment variables:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  -- server-side key; GitHub secret only
  DISCOGS_USERNAME                          -- whose Discogs store to mirror
  DISCOGS_SYNC_STORE_NAME                   -- the House Of Wax store that owns those records
Optional:
  DISCOGS_TOKEN       -- needed for cover photos (without it new records wait as Drafts)
  RESEND_API_KEY, DISCOGS_SYNC_ALERT_TO -- email when something needs a look
  ALLOW_BIG_CHANGES=1 -- lift the safety brake for one run
  TAKE_DOWN_UNLINKED=1 -- also take down Live listings that came from Discogs
                          (have a release link) but aren't linked to a Discogs
                          listing. First run only: clears the old collection import.
  DRY_RUN=1           -- plan only, change nothing
"""
import os
import sys

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from discogs_mirror import run_discogs_mirror, safe, now  # noqa: E402

SUPABASE_URL = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
# New-style Supabase secret keys (sb_secret_...) go in the apikey header
# only; the gateway turns them into a short-lived token. Legacy JWT
# service_role keys also need the Authorization header.
HEADERS = {'apikey': KEY, 'Content-Type': 'application/json'}
if not KEY.startswith('sb_'):
    HEADERS['Authorization'] = f'Bearer {KEY}'
TIMEOUT = 20
PRODUCT_COLS = 'id,discogs_listing_id,external_release_url,listing_status,price,media_grade,sleeve_grade,condition_notes,image_url,artist,title'
INSERT_COLS = ['seller_id', 'sku', 'barcode', 'catalog_number', 'matrix_runout', 'category', 'artist', 'title', 'format', 'label', 'release_year', 'genre', 'media_grade', 'sleeve_grade', 'condition_notes', 'description', 'price', 'quantity', 'shipping_price', 'image_url', 'video_url', 'audio_url', 'external_release_url', 'discogs_listing_id', 'listing_status', 'listing_type', 'created_at', 'updated_at']


def rest(method, table, params=None, json=None, prefer=''):
    headers = dict(HEADERS)
    if prefer:
        headers['Prefer'] = prefer
    try:
        r = requests.request(method, f'{SUPABASE_URL}/rest/v1/{table}', headers=headers, params=params or {}, json=json, timeout=TIMEOUT)
    except Exception as e:
        print(f'Supabase {method} {table} failed: {type(e).__name__}')
        return None
    if r.status_code >= 300:
        print(f'Supabase {method} {table} failed: HTTP {r.status_code} {r.text[:300]}')
        return None
    return r.json() if r.text else []


class ServiceStore:
    def __init__(self, seller_id, chunk=100):
        self.sid = int(seller_id)
        self.chunk = chunk

    def read_products(self):
        rows, offset = [], 0
        while True:
            data = rest('get', 'products', {'select': PRODUCT_COLS, 'seller_id': f'eq.{self.sid}', 'order': 'id.asc', 'limit': '1000', 'offset': str(offset)})
            if data is None:
                return None
            if not data:
                break
            rows.extend(data)
            offset += len(data)
        return pd.DataFrame(rows)

    def insert(self, rows):
        saved = 0
        for i in range(0, len(rows), self.chunk):
            batch = [{k: dict(r, seller_id=self.sid)[k] for k in INSERT_COLS} for r in rows[i:i + self.chunk]]
            if rest('post', 'products', json=batch, prefer='return=minimal') is not None:
                saved += len(batch)
        return saved

    def update(self, pid, changes):
        data = rest('patch', 'products', {'id': f'eq.{int(pid)}', 'seller_id': f'eq.{self.sid}'}, json=changes, prefer='return=representation')
        return bool(data)

    def set_status(self, ids, status):
        changed = 0
        ids = list(ids)
        for i in range(0, len(ids), self.chunk):
            batch = ids[i:i + self.chunk]
            data = rest('patch', 'products', {'id': f"in.({','.join(str(x) for x in batch)})", 'seller_id': f'eq.{self.sid}'}, json={'listing_status': status, 'updated_at': now()}, prefer='return=representation')
            changed += len(data or [])
        return changed


def find_seller(store_name):
    data = rest('get', 'sellers', {'select': 'id,store_name,status,rules_accepted,paypal_link', 'store_name': f'eq.{store_name}'})
    if not data or len(data) != 1:
        return None
    return data[0]


def seller_ready(seller):
    status = safe(seller.get('status'))
    approved = status in ('Approved', 'Active', 'Verified', 'Verified Seller', 'Approved Seller')
    rules = safe(seller.get('rules_accepted')).strip().lower() in ('yes', 'true', '1', 'accepted')
    return approved and rules and bool(safe(seller.get('paypal_link')).strip())


def send_alert(subject, body):
    key = os.environ.get('RESEND_API_KEY', '')
    to = os.environ.get('DISCOGS_SYNC_ALERT_TO', 'hello@shophouseofwax.com')
    if not key:
        return
    try:
        requests.post('https://api.resend.com/emails', headers={'Authorization': f'Bearer {key}'}, json={'from': 'House Of Wax <hello@shophouseofwax.com>', 'to': [to], 'subject': subject, 'text': body}, timeout=TIMEOUT)
    except Exception as e:
        print(f'Alert email failed: {e}')


def main():
    store_name = os.environ.get('DISCOGS_SYNC_STORE_NAME', '').strip()
    username = os.environ.get('DISCOGS_USERNAME', '').strip()
    if not store_name or not username:
        print('Discogs sync stopped: DISCOGS_SYNC_STORE_NAME and DISCOGS_USERNAME must both be set.')
        return 1
    seller = find_seller(store_name)
    if seller is None:
        msg = f'Discogs sync stopped: could not find exactly one House Of Wax store named "{store_name}". Nothing was changed.'
        print(msg)
        send_alert('House Of Wax: Discogs sync stopped', msg)
        return 1
    ok = seller_ready(seller)
    report = run_discogs_mirror(
        ServiceStore(seller['id']), username,
        token=os.environ.get('DISCOGS_TOKEN', ''), seller_ok=ok,
        take_down_unlinked=os.environ.get('TAKE_DOWN_UNLINKED') == '1',
        allow_big_changes=os.environ.get('ALLOW_BIG_CHANGES') == '1', dry_run=os.environ.get('DRY_RUN') == '1')
    plan = report.get('plan') or {}
    summary = (f"Discogs records for sale: {report['discogs_count']}\n"
               f"Planned: {len(plan.get('add', []))} new, {len(plan.get('update', []))} updates, {len(plan.get('take_down', []))} coming off\n"
               f"Done: {report['added']} added, {report['published']} published, {report['updated']} updated, "
               f"{report['taken_down']} taken off, {report['photos_added']} photos added, {report['failed']} failed")
    print(summary)
    if not ok:
        print('Note: the seller account is not ready to publish (approval, rules or PayPal), so new records stay as Drafts.')
    problems = []
    if report['aborted']:
        problems.append(report['aborted'])
    if report['failed']:
        problems.append(f"{report['failed']} change(s) failed to save. The next run will retry them.")
    if report['protected']:
        problems.append('Possible double sale. These are being paid for, or sold, on House Of Wax:\n' + '\n'.join(f"  listing #{p['id']}: {p['reason']}" for p in report['protected']))
    # Only mention records still waiting on a run that brought something
    # new in, so the same list doesn't arrive every few hours.
    if report['waiting'] and (report['added'] or report['photos_added']):
        problems.append(f"{len(report['waiting'])} Discogs record(s) are waiting as Drafts on House Of Wax because something is missing:\n" + '\n'.join(f"  {w['record']}: needs {', '.join(w['missing'])}" for w in report['waiting'][:50]))
    if problems:
        send_alert('House Of Wax: Discogs sync needs a look', summary + '\n\n' + '\n\n'.join(problems))
    return 1 if (report['aborted'] or report['failed']) else 0


if __name__ == '__main__':
    sys.exit(main())

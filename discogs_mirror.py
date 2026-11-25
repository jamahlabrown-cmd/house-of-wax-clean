"""Discogs mirror: Discogs is the master copy of a seller's stock.

Shared by the app (More Tools > Discogs sync) and the scheduled job
(scripts/discogs_sync.py), so both follow exactly the same rules.

Founder's rules (2026-11-25): records are only ever entered on Discogs.
Whatever is for sale there shows on House Of Wax with the same price,
grades and notes. New Discogs records go live here automatically when they
have a price, both grades and a cover photo; otherwise they wait as Drafts.
Anything sold or removed on Discogs comes off House Of Wax (moved to Draft,
never deleted). Listings a buyer is paying for, or has bought, here are
never changed.
"""
import re
import time
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd
import requests


def safe(v, d=''):
    if v is None:
        return d
    try:
        if pd.isna(v):
            return d
    except Exception:
        pass
    s = str(v)
    return d if s.lower() in ['nan', 'none'] else s


def now():
    return datetime.now().isoformat(timespec='seconds')


DISCOGS_CONDITION_MAP = {'mint (m)': 'Mint', 'near mint (nm or m-)': 'Near Mint', 'very good plus (vg+)': 'VG+', 'very good (vg)': 'VG', 'good plus (g+)': 'Good+', 'good (g)': 'Good', 'fair (f)': 'Fair', 'poor (p)': 'Poor'}


def map_discogs_condition(value):
    # 'Generic'/'No Cover'/blank aren't real condition grades -- never guess
    # one that isn't there.
    return DISCOGS_CONDITION_MAP.get(safe(value).strip().lower(), '')


# Sleeve-only special states -- distinct from both a real condition grade
# and from "not graded yet". A record sold without any cover (a lot of 7"
# singles and promos) has nothing to grade; a generic/unbranded sleeve is a
# real physical object the seller can still grade later, but "Generic" on
# Discogs describes the sleeve TYPE, not a condition, so it's never treated
# as if it were one. Both count as a real answer for the publish-gate check
# (there's a real answer on file), unlike blank/"Not graded yet".
NO_SLEEVE_VALUE = 'No sleeve/cover'
GENERIC_SLEEVE_VALUE = 'Generic sleeve (ungraded)'


def map_discogs_sleeve_condition(value):
    real_grade = map_discogs_condition(value)
    if real_grade:
        return real_grade
    v = safe(value).strip().lower()
    if v == 'no cover':
        return NO_SLEEVE_VALUE
    if v == 'generic':
        return GENERIC_SLEEVE_VALUE
    return ''


def discogs_release_id_from_url(url):
    m = re.search(r'discogs\.com/release/(\d+)', safe(url))
    return m.group(1) if m else ''


def existing_discogs_release_counts(listings):
    # How many copies of each Discogs release this seller already has on
    # House Of Wax, so re-importing the same inventory file never doubles up.
    counts = {}
    if listings is None or listings.empty or 'external_release_url' not in listings.columns:
        return counts
    for url in listings['external_release_url'].tolist():
        if not isinstance(url, str):
            continue
        rid = discogs_release_id_from_url(url)
        if rid:
            counts[rid] = counts.get(rid, 0) + 1
    return counts


DISCOGS_SYNC_PROTECTED_STATUSES = {'Pending Pickup/Payment', 'Pending', 'Sold'}
# Only listings that are up for sale come down. Moderation states (Hidden,
# Reported, Under Review...) are House Of Wax's call and are never reset.
DISCOGS_SYNC_TAKE_DOWN_STATUSES = {'Live', 'Active', 'Approved', 'Public'}
USER_AGENT = 'HouseOfWaxPrototype/1.0'


def _fetch_discogs_inventory_pass(username, sort, token=''):
    out = []
    total = None
    page = 1
    while True:
        params = {'per_page': 100, 'page': page, 'sort': sort, 'sort_order': 'asc'}
        if token:
            params['token'] = token
        try:
            r = requests.get(f'https://api.discogs.com/users/{quote_plus(username)}/inventory', params=params, headers={'User-Agent': USER_AGENT}, timeout=15)
        except Exception:
            return None, None
        if r.status_code != 200:
            return None, None
        data = r.json()
        pagination = data.get('pagination') or {}
        if total is None:
            total = int(pagination.get('items') or 0)
        for l in data.get('listings') or []:
            rel = l.get('release') or {}
            year = rel.get('year')
            out.append({
                'listing_id': safe(l.get('id')),
                'release_id': safe(rel.get('id')),
                'artist': safe(rel.get('artist')),
                'title': safe(rel.get('title')),
                'label': safe(rel.get('label')),
                'catno': safe(rel.get('catalog_number')),
                'format': safe(rel.get('format')),
                'year': safe(year) if year not in (None, 0, '0') else '',
                'price': float((l.get('price') or {}).get('value') or 0),
                'media_condition': safe(l.get('condition')),
                'sleeve_condition': safe(l.get('sleeve_condition')),
                'comments': safe(l.get('comments')),
                'status': safe(l.get('status')),
            })
        if page >= int(pagination.get('pages') or 1):
            break
        page += 1
        # Discogs allows 25 requests a minute without a token, 60 with one.
        time.sleep(1.1 if token else 2.5)
    return out, total


def fetch_discogs_inventory(username, token=''):
    # All-or-nothing: returns None unless every listing came back exactly
    # once. Found 2026-11-25: Discogs' default order is unstable when many
    # listings share a listed time (a bulk upload), so pages repeat some
    # listings and skip others -- 37 of 1,437 went missing that way, and a
    # missing listing looks exactly like a sale. sort=item pages cleanly;
    # price is the fallback. Anything short of complete returns None so a
    # sync never takes listings down on a partial read.
    username = safe(username).strip()
    if not username:
        return None
    for sort in ('item', 'price'):
        rows, total = _fetch_discogs_inventory_pass(username, sort, token)
        if rows is None:
            return None
        unique = {}
        for row in rows:
            unique.setdefault(row['listing_id'], row)
        if total is not None and len(unique) == total and len(rows) == total:
            # Only records actually for sale are mirrored (never Draft,
            # Expired or Sold listings, should Discogs ever include them).
            return [r for r in unique.values() if r['status'].strip().lower() in ('', 'for sale')]
    return None


def fetch_discogs_release_image(release_id, token=''):
    # Cover photo for a release (works without a token, just a lower
    # Discogs rate limit: 25 requests a minute instead of 60).
    if not safe(release_id):
        return ''
    try:
        r = requests.get(f'https://api.discogs.com/releases/{safe(release_id)}', params={'token': token} if token else {}, headers={'User-Agent': USER_AGENT}, timeout=10)
    except Exception:
        return ''
    if r.status_code != 200:
        return ''
    data = r.json()
    images = data.get('images') or []
    primary = [i for i in images if safe(i.get('type')) == 'primary']
    pick = (primary or images or [{}])[0]
    return safe(pick.get('uri')) or safe(data.get('thumb'))


def discogs_row_for_house_of_wax(d):
    fmt = safe(d.get('format'))
    category = 'Cassettes' if 'Cass' in fmt else ('CDs' if re.search(r'\bCD\b', fmt) else 'Vinyl Records')
    rid = safe(d.get('release_id'))
    return {
        'sku': '', 'barcode': '', 'catalog_number': safe(d.get('catno')), 'matrix_runout': '',
        'category': category, 'artist': safe(d.get('artist')), 'title': safe(d.get('title')), 'format': fmt,
        'label': safe(d.get('label')), 'release_year': safe(d.get('year')), 'genre': '',
        'media_grade': map_discogs_condition(d.get('media_condition')),
        'sleeve_grade': map_discogs_sleeve_condition(d.get('sleeve_condition')),
        'condition_notes': safe(d.get('comments')), 'description': '', 'price': float(d.get('price') or 0),
        'quantity': 1, 'shipping_price': 0, 'image_url': '', 'video_url': '', 'audio_url': '',
        'external_release_url': f'https://www.discogs.com/release/{rid}' if rid else '',
        'discogs_listing_id': safe(d.get('listing_id')),
        'listing_status': 'Draft', 'listing_type': 'Fixed Price', 'created_at': now(), 'updated_at': now(),
    }


def discogs_changes_for(product, d):
    changes = {}
    price = round(float(d.get('price') or 0), 2)
    try:
        current_price = round(float(product.get('price')), 2)
    except Exception:
        current_price = None
    if price > 0 and current_price != price:
        # A missing or $0 Discogs price is never copied over a real one.
        changes['price'] = price
    media = map_discogs_condition(d.get('media_condition'))
    if media and safe(product.get('media_grade')) != media:
        changes['media_grade'] = media
    sleeve = map_discogs_sleeve_condition(d.get('sleeve_condition'))
    if sleeve and safe(product.get('sleeve_grade')) != sleeve:
        changes['sleeve_grade'] = sleeve
    comments = safe(d.get('comments')).strip()
    if comments and safe(product.get('condition_notes')).strip() != comments:
        changes['condition_notes'] = comments
    return changes


def plan_discogs_mirror(discogs_listings, products, take_down_unlinked=False):
    if not discogs_listings:
        raise ValueError('Discogs returned no listings -- refusing to plan a sync that would take everything down.')
    by_listing = {safe(d['listing_id']): d for d in discogs_listings if safe(d.get('listing_id'))}
    claimed = set()
    plan = {'add': [], 'update': [], 'take_down': [], 'protected': [], 'unlinked_left': []}
    rows = [] if products is None or products.empty else products.to_dict('records')
    linked = [p for p in rows if safe(p.get('discogs_listing_id')).strip()]
    unlinked = [p for p in rows if not safe(p.get('discogs_listing_id')).strip()]
    for p in linked:
        lid = safe(p.get('discogs_listing_id')).strip()
        status = safe(p.get('listing_status'))
        if lid in by_listing and lid not in claimed:
            claimed.add(lid)
            if status in DISCOGS_SYNC_PROTECTED_STATUSES:
                # Never change a listing a buyer is paying for or has bought.
                plan['protected'].append({'id': int(p['id']), 'reason': f'{status} on House Of Wax but still for sale on Discogs'})
                continue
            changes = discogs_changes_for(p, by_listing[lid])
            if changes:
                plan['update'].append({'id': int(p['id']), 'changes': changes})
        elif status in DISCOGS_SYNC_PROTECTED_STATUSES:
            plan['protected'].append({'id': int(p['id']), 'reason': f'{status} on House Of Wax'})
        elif status in DISCOGS_SYNC_TAKE_DOWN_STATUSES:
            plan['take_down'].append(int(p['id']))
    # Unlinked listings that came from Discogs (collection import): link
    # them to an unclaimed Discogs listing of the same pressing, one copy each.
    open_by_release = {}
    for d in discogs_listings:
        lid = safe(d.get('listing_id'))
        if lid and lid not in claimed:
            open_by_release.setdefault(safe(d.get('release_id')), []).append(d)
    # Live listings link before Drafts, so a matched copy stays on the site.
    unlinked.sort(key=lambda p: (safe(p.get('listing_status')) != 'Live', int(p['id'])))
    for p in unlinked:
        rid = discogs_release_id_from_url(p.get('external_release_url'))
        if not rid:
            continue  # manual listing, never touched
        status = safe(p.get('listing_status'))
        candidates = open_by_release.get(rid) or []
        if status in DISCOGS_SYNC_PROTECTED_STATUSES:
            # Mid-purchase or sold here: never changed or linked. Flag it if
            # Discogs still has a copy for sale, since that may be a double sale.
            if candidates:
                plan['protected'].append({'id': int(p['id']), 'reason': f'{status} on House Of Wax but a copy is still for sale on Discogs'})
            continue
        if candidates:
            d = candidates.pop(0)
            claimed.add(safe(d['listing_id']))
            changes = {'discogs_listing_id': safe(d['listing_id'])}
            changes.update(discogs_changes_for(p, d))
            plan['update'].append({'id': int(p['id']), 'changes': changes})
            continue
        if status not in DISCOGS_SYNC_TAKE_DOWN_STATUSES:
            continue
        if take_down_unlinked:
            plan['take_down'].append(int(p['id']))
        else:
            plan['unlinked_left'].append(int(p['id']))
    for d in discogs_listings:
        lid = safe(d.get('listing_id'))
        if lid and lid not in claimed:
            claimed.add(lid)
            plan['add'].append(discogs_row_for_house_of_wax(d))
    plan['take_down'] = sorted(plan['take_down'])
    return plan


def publish_blockers(row, seller_ok=True):
    # Same bar as Bulk Publish in My Inventory: a real price, a photo, and
    # both grades, from a seller who is approved, accepted the rules and
    # has PayPal on file.
    missing = []
    try:
        price = float(row.get('price') or 0)
    except Exception:
        price = 0
    if price <= 0:
        missing.append('price')
    if not safe(row.get('image_url')).strip():
        missing.append('cover photo')
    if not safe(row.get('media_grade')).strip():
        missing.append('vinyl grade')
    if not safe(row.get('sleeve_grade')).strip():
        missing.append('cover grade')
    if not seller_ok:
        missing.append('seller account not ready to publish (approval, rules or PayPal)')
    return missing


def run_discogs_mirror(store, username, token='', seller_ok=True, take_down_unlinked=False,
                       allow_big_changes=False, max_take_down=25, max_take_down_share=0.2,
                       max_image_lookups=600, dry_run=False):
    """Full sync. `store` is the House Of Wax side:
    read_products() -> DataFrame or None, insert(rows) -> int saved,
    update(id, changes) -> bool, set_status(ids, status) -> int changed.
    Returns a report dict; report['aborted'] explains why nothing was done."""
    report = {'aborted': '', 'discogs_count': 0, 'added': 0, 'updated': 0, 'taken_down': 0,
              'published': 0, 'photos_added': 0, 'failed': 0, 'protected': [], 'waiting': [], 'plan': None}
    listings = fetch_discogs_inventory(username, token)
    if listings is None:
        report['aborted'] = "Couldn't read the full Discogs store, so nothing was changed."
        return report
    report['discogs_count'] = len(listings)
    products = store.read_products()
    if products is None:
        report['aborted'] = "Couldn't read the House Of Wax listings, so nothing was changed."
        return report
    try:
        plan = plan_discogs_mirror(listings, products, take_down_unlinked)
    except ValueError as e:
        report['aborted'] = str(e)
        return report
    report['plan'] = plan
    report['protected'] = plan['protected']
    live_now = 0 if products.empty else int((products['listing_status'].fillna('') == 'Live').sum())
    limit = max(max_take_down, int(live_now * max_take_down_share))
    if not allow_big_changes and len(plan['take_down']) > limit:
        report['aborted'] = (f"Safety brake: this run would take {len(plan['take_down'])} listings off House Of Wax "
                             f"(the limit per run is {limit}). Nothing was changed. If that's expected, run it once with big changes allowed.")
        return report
    if dry_run:
        return report
    # Cover photos for new records, so complete ones can go live right away.
    lookups = 0
    for row in plan['add']:
        if lookups >= max_image_lookups:
            break
        rid = discogs_release_id_from_url(row['external_release_url'])
        if rid:
            row['image_url'] = fetch_discogs_release_image(rid, token)
            lookups += 1
            time.sleep(1.05 if token else 2.5)
    for row in plan['add']:
        if not publish_blockers(row, seller_ok):
            row['listing_status'] = 'Live'
    saved = store.insert(plan['add']) if plan['add'] else 0
    report['added'] = saved
    report['failed'] += len(plan['add']) - saved
    report['published'] += sum(1 for r in plan['add'] if r['listing_status'] == 'Live') if saved == len(plan['add']) else 0
    for u in plan['update']:
        if store.update(u['id'], dict(u['changes'], updated_at=now())):
            report['updated'] += 1
        else:
            report['failed'] += 1
    if plan['take_down']:
        changed = store.set_status(plan['take_down'], 'Draft')
        report['taken_down'] = changed
        report['failed'] += len(plan['take_down']) - changed
    # Drafts that are still for sale on Discogs: add a missing photo, then
    # publish the complete ones. Hidden (moderation) listings are never touched.
    current = store.read_products()
    on_discogs = {safe(d['listing_id']) for d in listings}
    taken_down = set(plan['take_down'])
    seen_listing = set()
    if current is not None and not current.empty:
        rows = sorted(current.to_dict('records'), key=lambda p: int(p['id']))
        # A Discogs listing that already has a live copy here never gets a second one published.
        seen_listing.update(safe(p.get('discogs_listing_id')) for p in rows if safe(p.get('listing_status')) != 'Draft')
        for p in rows:
            lid = safe(p.get('discogs_listing_id'))
            if safe(p.get('listing_status')) != 'Draft' or lid not in on_discogs or int(p['id']) in taken_down or lid in seen_listing:
                continue
            seen_listing.add(lid)
            if not safe(p.get('image_url')).strip() and lookups < max_image_lookups:
                image = fetch_discogs_release_image(discogs_release_id_from_url(p.get('external_release_url')), token)
                lookups += 1
                time.sleep(1.05 if token else 2.5)
                if image and store.update(int(p['id']), {'image_url': image, 'updated_at': now()}):
                    p['image_url'] = image
                    report['photos_added'] += 1
            missing = publish_blockers(p, seller_ok)
            if missing:
                report['waiting'].append({'id': int(p['id']), 'record': f"{safe(p.get('artist'))} - {safe(p.get('title'))}", 'missing': missing})
            elif store.update(int(p['id']), {'listing_status': 'Live', 'updated_at': now()}):
                report['published'] += 1
    return report

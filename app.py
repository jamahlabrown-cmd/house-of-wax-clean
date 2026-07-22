
# ROOT APP DEPLOY FIX — upload THIS app.py to the repository root, replacing the old root app.py.
import sqlite3
import re
import os
import html
import hashlib
import secrets
from uuid import uuid4
from urllib.parse import quote_plus
from pathlib import Path
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='House Of Wax', page_icon='🎧', layout='wide')
APP_VERSION='V25.43.58 FIX: PUBLIC PRODUCTS VISIBILITY (ANON SELECT PERMISSION)'
APP_DIR=Path(__file__).resolve().parent
DB=Path(os.environ.get('HOUSE_OF_WAX_DB_PATH', APP_DIR/'house_of_wax.db')).expanduser()
UPLOAD=Path(os.environ.get('HOUSE_OF_WAX_UPLOAD_DIR', APP_DIR/'house_of_wax_uploads')).expanduser(); UPLOAD.mkdir(exist_ok=True)
try:
    ADMIN_PASSWORD=st.secrets.get('ADMIN_PASSWORD','')
except Exception:
    ADMIN_PASSWORD=''

def now(): return datetime.now().isoformat(timespec='seconds')
def safe(v,d=''):
    if v is None: return d
    try:
        if pd.isna(v): return d
    except Exception: pass
    s=str(v)
    return d if s.lower() in ['nan','none'] else s
def money(v):
    try: return f'${float(v):,.2f}'
    except Exception: return '$0.00'
def parse_money_input(value, field_label='Price'):
    raw=safe(value).strip().replace('$','').replace(',','')
    if not raw:
        return 0.0, ''
    try:
        parsed=float(raw)
    except Exception:
        return 0.0, f'{field_label} must be a number like 10, 10.00, or $10.00.'
    if parsed<0:
        return 0.0, f'{field_label} cannot be negative.'
    return parsed, ''
def parse_quantity_input(value):
    raw=safe(value,'1').strip()
    try:
        parsed=int(raw)
    except Exception:
        return 1, 'Quantity must be a whole number.'
    if parsed<1:
        return 1, 'Quantity must be at least 1.'
    return parsed, ''
def mask_secret(v):
    s=safe(v)
    if not s:
        return 'Missing'
    if len(s)<=8:
        return 'Detected, hidden'
    return f'Detected ({s[:4]}...{s[-4:]})'
def config_value(key):
    if os.environ.get(key):
        return os.environ.get(key,'')
    try:
        return st.secrets.get(key,'')
    except Exception:
        return ''
def supabase_config():
    url=safe(config_value('SUPABASE_URL')).rstrip('/')
    if url.endswith('/rest/v1'):
        url=url[:-8].rstrip('/')
    anon=safe(config_value('SUPABASE_ANON_KEY'))
    return url,anon
CORE_HOSTED_TABLES=['app_users','buyers','sellers','products','product_gallery','listing_inquiries','purchase_requests','tester_feedback','listing_reports','knowledge_posts','glossary_terms','homepage_blocks','quick_tips','did_you_know','newsletter_signups','seller_followers','seller_badges','store_announcements','seller_events','seller_policies','want_list','seller_reviews']
GRADE_SCALE=['Mint','Near Mint','VG+','VG','Good+','Good','Fair','Poor']
GRADE_INDEX={g:i for i,g in enumerate(GRADE_SCALE)}
GRADE_PRICE_MULTIPLIERS={'Mint':1.35,'Near Mint':1.20,'VG+':1.00,'VG':0.80,'Good+':0.65,'Good':0.50,'Fair':0.35,'Poor':0.20}
DISCOGS_GRADE_ALIASES={'Mint':'Mint (M)','Near Mint':'Near Mint (NM or M-)','VG+':'Very Good Plus (VG+)','VG':'Very Good (VG)','Good+':'Good Plus (G+)','Good':'Good (G)','Fair':'Fair (F)','Poor':'Poor (P)'}
def grade_price_multiplier(media_grade, sleeve_grade=None):
    # Media condition drives resale value more than sleeve condition, so
    # sleeve only pulls the estimate down a little when it's worse.
    mg_mult=GRADE_PRICE_MULTIPLIERS.get(safe(media_grade),1.0)
    if not safe(sleeve_grade):
        return mg_mult
    sg_mult=GRADE_PRICE_MULTIPLIERS.get(safe(sleeve_grade),mg_mult)
    return round(mg_mult*0.7+sg_mult*0.3,4)
def worse_grade(media_grade, sleeve_grade=None):
    if not safe(sleeve_grade):
        return media_grade
    mg_idx=GRADE_INDEX.get(safe(media_grade),0)
    sg_idx=GRADE_INDEX.get(safe(sleeve_grade),mg_idx)
    return GRADE_SCALE[max(mg_idx,sg_idx)]
SUPABASE_STATUS={'last_read':'Not run','last_write':'Not run','last_error':''}
AUTH_STATUS={'last_error':'','last_buyer_save_error':'','last_seller_save_error':'','last_link_error':''}
def supabase_key_type():
    _,key=supabase_config()
    if key.startswith('sb_publishable_'):
        return 'publishable'
    if key.startswith('eyJ'):
        return 'anon JWT'
    return 'unknown' if key else 'missing'
def hosted_database_config_status():
    keys=['SUPABASE_URL','SUPABASE_ANON_KEY','DATABASE_URL']
    rows=[]
    for key in keys:
        value=config_value(key)
        rows.append({'Setting':key,'Status':'Detected' if value else 'Missing','Value':mask_secret(value)})
    detected={row['Setting']: row['Status']=='Detected' for row in rows}
    has_supabase=detected.get('SUPABASE_URL') and detected.get('SUPABASE_ANON_KEY')
    has_database_url=detected.get('DATABASE_URL')
    return {'rows':rows,'has_supabase':has_supabase,'has_database_url':has_database_url,'hosted_config_detected':bool(has_supabase or has_database_url)}
def auth_config_status():
    keys=['AUTH_PROVIDER','SUPABASE_URL','SUPABASE_ANON_KEY','ADMIN_EMAILS']
    rows=[]
    for key in keys:
        value=config_value(key)
        rows.append({'Setting':key,'Status':'Configured' if value else 'Missing','Value':mask_secret(value)})
    configured=any(row['Status']=='Configured' for row in rows)
    return {'rows':rows,'auth_configured':configured}
def database_mode():
    hosted=hosted_database_config_status()
    active=bool(hosted['has_supabase'])
    storage_mode='Supabase Hosted' if active else 'Local SQLite'
    engine='Supabase/PostgREST core data' if active else 'SQLite local prototype'
    return {'engine':engine,'storage_mode':storage_mode,'path':str(DB.resolve()),'hosted_config_detected':hosted['hosted_config_detected'],'active_hosted_database':active,'hosted_config':hosted}
def hosted_enabled():
    url,anon=supabase_config()
    return bool(url and anon)
def hosted_headers(prefer='return=representation'):
    _,anon=supabase_config()
    user_token=auth_access_token()
    token=user_token or anon
    SUPABASE_STATUS['last_auth_mode']='Signed-in user token' if user_token else 'Anon key (no user session token in memory)'
    headers={'apikey':anon,'Authorization':f'Bearer {token}','Content-Type':'application/json'}
    if prefer:
        headers['Prefer']=prefer
    return headers
def hosted_url(table_name):
    url,_=supabase_config()
    return f"{url}/rest/v1/{table_name}"
def supabase_auth_url(path):
    url,_=supabase_config()
    return f"{url}/auth/v1/{path.lstrip('/')}"
def hosted_result_summary(resp):
    text=safe(getattr(resp,'text',''))
    return {'status_code':getattr(resp,'status_code',0),'ok':bool(getattr(resp,'ok',False)),'message':text[:800]}
def show_hosted_error(action, table_name, detail):
    if not hosted_enabled() or detail.get('ok'):
        return
    message=f"Supabase {action} failed for {table_name}: HTTP {detail.get('status_code')} {safe(detail.get('message'))}"
    try:
        st.error(message)
    except Exception:
        pass
def hosted_request(method, table_name, params=None, data=None, prefer='return=representation'):
    if not hosted_enabled():
        detail={'status_code':0,'ok':False,'message':'Supabase settings are missing.'}
        SUPABASE_STATUS['last_error']=detail['message']
        return None,detail
    try:
        r=requests.request(method,hosted_url(table_name),headers=hosted_headers(prefer),params=params or {},json=data,timeout=12)
        detail=hosted_result_summary(r)
        # A signed-in user's Supabase access token expires (~1hr) long before
        # their browser session ends, and nothing else in the app proactively
        # refreshes it mid-session -- without this, every request silently
        # fails with "JWT expired" until the user reloads the page. One
        # transparent refresh-and-retry keeps the session usable instead.
        if detail['status_code']==401 and 'jwt expired' in safe(detail['message']).lower():
            refresh_token=safe(auth_session().get('refresh_token'))
            if refresh_token and supabase_refresh_session(refresh_token):
                r=requests.request(method,hosted_url(table_name),headers=hosted_headers(prefer),params=params or {},json=data,timeout=12)
                detail=hosted_result_summary(r)
        if method.lower()=='get':
            SUPABASE_STATUS['last_read']=f"{table_name}: HTTP {detail['status_code']}"
        else:
            SUPABASE_STATUS['last_write']=f"{table_name}: HTTP {detail['status_code']}"
        if not detail['ok']:
            SUPABASE_STATUS['last_error']=f"{table_name}: HTTP {detail['status_code']} {detail['message']}"
            return None,detail
        return (r.json() if r.text else []),detail
    except Exception as e:
        detail={'status_code':0,'ok':False,'message':str(e)}
        SUPABASE_STATUS['last_error']=f"{table_name}: {e}"
        if method.lower()=='get':
            SUPABASE_STATUS['last_read']=f"{table_name}: error"
        else:
            SUPABASE_STATUS['last_write']=f"{table_name}: error"
        return None,detail
# Supabase only grants anon SELECT on these products columns (reviewer_notes,
# internal moderation commentary, is deliberately excluded) -- see
# supabase_core_policies.sql. Postgres requires privilege on every column for
# select=*, so any anon/testing-mode request for products defaulted to '*'
# gets rejected outright with "permission denied for table products". Callers
# that genuinely need reviewer_notes (a signed-in seller viewing their own
# listings) pass select='*' explicitly to opt back into the full column set.
PRODUCTS_ANON_SAFE_SELECT=('id,seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,'
    'format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,'
    'shipping_price,image_url,reference_image_url,video_url,audio_url,external_release_url,listing_status,'
    'listing_type,created_at,updated_at')
def hosted_select(table_name, filters=None, order=None, limit=None, in_filters=None, select='*'):
    if not hosted_enabled():
        return pd.DataFrame()
    if table_name=='products' and select=='*':
        select=PRODUCTS_ANON_SAFE_SELECT
    params={'select':select}
    for key,value in (filters or {}).items():
        params[key]=f'eq.{value}'
    for key,values in (in_filters or {}).items():
        clean=','.join([safe(v).replace(',', '') for v in values])
        params[key]=f'in.({clean})'
    if order:
        params['order']=order
    if limit:
        params['limit']=str(limit)
    data,detail=hosted_request('get',table_name,params=params,prefer='')
    show_hosted_error('read',table_name,detail)
    return pd.DataFrame(data or [])
def hosted_insert(table_name, data):
    if not hosted_enabled():
        return 0
    clean={k:v for k,v in data.items() if k!='id' and v is not None}
    payload,detail=hosted_request('post',table_name,data=clean)
    show_hosted_error('insert',table_name,detail)
    return int(payload[0].get('id',0)) if payload and payload[0].get('id') else 0
def hosted_update(table_name, data, filters):
    if not hosted_enabled():
        return False
    params={k:f'eq.{v}' for k,v in filters.items()}
    clean={k:v for k,v in data.items() if v is not None}
    payload,detail=hosted_request('patch',table_name,params=params,data=clean)
    show_hosted_error('update',table_name,detail)
    return bool(detail.get('ok'))
def hosted_delete(table_name, filters):
    if not hosted_enabled():
        return False
    params={k:f'eq.{v}' for k,v in filters.items()}
    payload,detail=hosted_request('delete',table_name,params=params,prefer='')
    show_hosted_error('delete',table_name,detail)
    return bool(detail.get('ok'))
def core_table(table_name, order=None):
    if hosted_enabled() and table_name in CORE_HOSTED_TABLES:
        return hosted_select(table_name,order=order)
    return pd.DataFrame()
def core_insert(table_name, data, sql='', params=()):
    if hosted_enabled() and table_name in CORE_HOSTED_TABLES:
        return hosted_insert(table_name,data)
    return insert(sql,params) if sql else 0
def core_update(table_name, data, filters, sql='', params=()):
    if hosted_enabled() and table_name in CORE_HOSTED_TABLES:
        return hosted_update(table_name,data,filters)
    if sql:
        run(sql,params)
    return True
def active_storage_label():
    return 'Supabase Hosted' if hosted_enabled() else 'Local SQLite'
def warn_if_local_only(feature_label):
    # These features have no Supabase-hosted table yet and always write to
    # local SQLite, which is ephemeral on Streamlit Cloud. Surface that
    # plainly instead of letting a live tester believe it persisted.
    if hosted_enabled():
        st.warning(f"{feature_label} is saved locally to this session only and will not survive a Streamlit Cloud restart. It is not yet stored in Supabase.")
def mask_identifier(value):
    s=safe(value)
    if not s:
        return 'None'
    if len(s)<=10:
        return s[:2]+'...'
    return s[:6]+'...'+s[-4:]
def admin_email_allowlist():
    raw=safe(config_value('ADMIN_EMAILS') or os.environ.get('ADMIN_EMAILS',''))
    return [x.strip().lower() for x in re.split(r'[,;\\s]+',raw) if x.strip()]
def hash_password(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.sha256((salt+safe(password)).encode('utf-8')).hexdigest()
    return salt+'$'+digest
def verify_password(password, stored):
    stored=safe(stored)
    if '$' not in stored:
        return False
    salt,digest=stored.split('$',1)
    return hash_password(password,salt)==stored
def auth_session():
    return st.session_state.get('auth_session') or {}
def auth_user_id():
    return safe(auth_session().get('user_id'))
def auth_user_email():
    return safe(auth_session().get('email')).lower()
def auth_access_token():
    return safe(auth_session().get('access_token'))
def is_authenticated():
    return bool(auth_user_id() and auth_user_email())
def auth_user_row():
    uid=auth_user_id()
    email=auth_user_email()
    if uid:
        row=hosted_select('app_users',{'auth_user_id':uid},limit=1) if hosted_enabled() else df('SELECT * FROM app_users WHERE auth_user_id=? LIMIT 1',(uid,))
        if not row.empty:
            return row.iloc[0]
    if email:
        row=hosted_select('app_users',{'email':email},limit=1) if hosted_enabled() else df('SELECT * FROM app_users WHERE lower(email)=lower(?) LIMIT 1',(email,))
        if not row.empty:
            return row.iloc[0]
    return None
def current_app_user():
    row=auth_user_row()
    return row.to_dict() if row is not None else {}
def effective_account_type():
    user=current_app_user()
    if is_admin_user(user):
        return 'Admin'
    if user and int(user.get('seller_id') or 0):
        return 'Seller'
    if user:
        return 'Buyer'
    return 'Public'
def account_status(user=None):
    if user is None:
        user=current_app_user()
    if user is None:
        return 'Public'
    try:
        if hasattr(user,'empty') and user.empty:
            return 'Public'
    except Exception:
        pass
    return safe(user.get('account_status') or user.get('status'),'Active')
def seller_application_status(user=None):
    if user is None:
        user=current_app_user()
    if user is None:
        return 'Not Applied'
    try:
        if hasattr(user,'empty') and user.empty:
            return 'Not Applied'
    except Exception:
        pass
    raw=safe(user.get('seller_application_status'))
    if raw:
        return normalize_seller_status(raw) if raw!='Not Applied' else raw
    sid=int(user.get('seller_id') or 0)
    seller=get_seller(sid) if sid else None
    if seller is not None:
        return normalize_seller_status(seller.get('status'))
    return 'Not Applied'
def has_buyer_capability():
    return is_authenticated()
def has_seller_capability():
    return is_authenticated() and linked_seller_id()>0
def seller_is_approved_for_current_user():
    sid=linked_seller_id()
    seller=get_seller(sid) if sid else None
    return seller_can_publish(seller) if seller is not None else False
def linked_buyer_id():
    user=current_app_user()
    try:
        return int(user.get('buyer_id') or 0)
    except Exception:
        return 0
def linked_seller_id():
    user=current_app_user()
    try:
        return int(user.get('seller_id') or 0)
    except Exception:
        return 0
def pending_action():
    action=st.session_state.get('pending_action') or {}
    return action if isinstance(action,dict) else {}
def request_marketplace_navigation(target, clear_product=False, clear_seller=False):
    st.session_state['pending_marketplace_navigation']=safe(target,'Home')
    if clear_product:
        st.session_state['pending_clear_product_id']=True
    if clear_seller:
        st.session_state['pending_clear_seller_id']=True
def apply_pending_marketplace_navigation(marketplace_menu):
    if st.session_state.pop('pending_clear_product_id',False):
        st.session_state.pop('product_id',None)
    if st.session_state.pop('pending_clear_seller_id',False):
        st.session_state.pop('seller_id',None)
    pending=st.session_state.pop('pending_marketplace_navigation',None)
    if pending in marketplace_menu:
        st.session_state['marketplace_navigation']=pending
def app_public_url():
    try:
        return safe(st.secrets.get('APP_PUBLIC_URL','')).rstrip('/')
    except Exception:
        return ''
def share_block(item_kind, item_id, item_label):
    base=app_public_url()
    if not base:
        return
    param='view_product' if item_kind=='product' else 'view_article'
    link=f'{base}/?{param}={int(item_id)}'
    share_text=f'Check this out on House Of Wax: {safe(item_label)}'
    with st.expander('Share'):
        st.text_input('Link to this page',value=link,key=f'share_link_{item_kind}_{item_id}')
        sc1,sc2,sc3,sc4=st.columns(4)
        sc1.link_button('WhatsApp',f'https://wa.me/?text={quote_plus(share_text+" "+link)}')
        sc2.link_button('Email',f'mailto:?subject={quote_plus(safe(item_label,"House Of Wax"))}&body={quote_plus(share_text+chr(10)+link)}')
        sc3.link_button('X',f'https://twitter.com/intent/tweet?text={quote_plus(share_text)}&url={quote_plus(link)}')
        sc4.link_button('Facebook',f'https://www.facebook.com/sharer/sharer.php?u={quote_plus(link)}')
def apply_share_deep_link():
    if st.session_state.get('share_deep_link_applied'):
        return
    shared_product=safe(st.query_params.get('view_product')).strip()
    shared_article=safe(st.query_params.get('view_article')).strip()
    if not (shared_product or shared_article):
        return
    st.session_state['share_deep_link_applied']=True
    st.session_state['house_of_wax_area']='House Of Wax Marketplace'
    if shared_product.isdigit():
        st.session_state['product_id']=int(shared_product)
        request_marketplace_navigation('Search Music')
    elif shared_article.isdigit():
        st.session_state['selected_knowledge_id']=int(shared_article)
        request_marketplace_navigation('Knowledge Hub')
def set_pending_action(action_type, product=None):
    product_id=int(product.get('id') or 0) if product is not None else int(st.session_state.get('product_id') or 0)
    seller_id=int(product.get('seller_id') or 0) if product is not None else 0
    st.session_state['pending_action']={'action_type':safe(action_type),'product_id':product_id,'seller_id':seller_id,'return_page':'Search Music'}
    if product_id:
        st.session_state['product_id']=product_id
def restore_pending_action():
    action=pending_action()
    pid=int(action.get('product_id') or 0)
    if not pid:
        return False
    st.session_state['product_id']=pid
    request_marketplace_navigation('Search Music')
    if action.get('action_type')=='Ask Seller':
        st.session_state[f'open_inquiry_{pid}']=True
    elif action.get('action_type')=='Request to Buy':
        st.session_state[f'open_purchase_{pid}']=True
    elif action.get('action_type')=='Make Offer':
        st.session_state[f'open_offer_{pid}']=True
    return True
def clear_pending_action():
    st.session_state.pop('pending_action',None)
def ensure_linked_buyer_profile(name=''):
    if not is_authenticated():
        return 0
    bid=linked_buyer_id()
    if bid and get_buyer(bid) is not None:
        return bid
    email=auth_user_email()
    display=safe(name) or safe(current_app_user().get('display_name')) or email.split('@')[0]
    try:
        bid=create_or_get_buyer_for_auth(email,display)
        user=current_app_user()
        if bid:
            upsert_app_user(auth_user_id(),email,display,'Buyer',bid,int(user.get('seller_id') or 0),'',safe(user.get('admin_access'),'No'),seller_application_status(user),account_status(user))
            return int(bid)
    except Exception as e:
        AUTH_STATUS['last_buyer_save_error']=safe(e)
        AUTH_STATUS['last_link_error']=safe(e)
    return 0
def ensure_linked_seller_profile(name=''):
    if not is_authenticated():
        return 0
    sid=linked_seller_id()
    if sid and get_seller(sid) is not None:
        return sid
    email=auth_user_email()
    display=safe(name) or safe(current_app_user().get('display_name')) or email.split('@')[0]
    try:
        sid=create_or_get_seller_for_auth(email,display)
        user=current_app_user()
        if sid:
            bid=int(user.get('buyer_id') or 0) or ensure_linked_buyer_profile(display)
            upsert_app_user(auth_user_id(),email,display,'Buyer/Seller',bid,sid,'',safe(user.get('admin_access'),'No'),normalize_seller_status('Pending Seller Approval'),account_status(user))
            return int(sid)
    except Exception as e:
        AUTH_STATUS['last_seller_save_error']=safe(e)
        AUTH_STATUS['last_link_error']=safe(e)
    return 0
def is_admin_user(user=None):
    user=user or current_app_user()
    email=safe(user.get('email') if user else auth_user_email()).lower()
    admin_field=safe(user.get('admin_access') if user else '').lower() in ['yes','true','1','admin']
    return bool(admin_field or (email and email in admin_email_allowlist()))
def admin_access_source():
    user=current_app_user()
    email=auth_user_email()
    if safe(user.get('admin_access')).lower() in ['yes','true','1','admin']:
        return 'app_users.admin_access'
    if email and email in admin_email_allowlist():
        return 'ADMIN_EMAILS allowlist'
    if bool(st.session_state.get('testing_mode_enabled',False)) and not is_authenticated():
        return 'Unauthenticated Testing mode'
    return 'None'
def auth_headers():
    _,anon=supabase_config()
    token=auth_access_token() or anon
    return {'apikey':anon,'Authorization':f'Bearer {token}','Content-Type':'application/json'}
def supabase_auth_request(path, payload):
    if not hosted_enabled():
        return None, {'ok':False,'message':'Supabase Auth is not configured.'}
    try:
        r=requests.post(supabase_auth_url(path),headers=auth_headers(),json=payload,timeout=12)
        if r.status_code>=400:
            # Some Supabase error responses (rate limiting, edge/WAF blocks) come
            # back with an empty body, which used to show as a blank diagnostics
            # row with no way to tell what happened. Always include the status
            # code so there is something actionable even when the body is empty.
            return None, {'ok':False,'message':f'HTTP {r.status_code}: '+(safe(r.text) or '(empty response body)')}
        return r.json() if r.text else {}, {'ok':True,'message':'OK'}
    except Exception as e:
        return None, {'ok':False,'message':f'{type(e).__name__}: '+(safe(e) or '(no exception detail)')}
def create_or_get_buyer_for_auth(email, name):
    clean=safe(email).strip().lower()
    existing=hosted_select('buyers',{'email':clean},limit=1) if hosted_enabled() else df('SELECT * FROM buyers WHERE lower(email)=lower(?) LIMIT 1',(clean,))
    if not existing.empty:
        return int(existing.iloc[0]['id'])
    return create_buyer(clean,name)
def create_or_get_seller_for_auth(email, name):
    clean=safe(email).strip().lower()
    existing=hosted_select('sellers',{'email':clean},limit=1) if hosted_enabled() else df('SELECT * FROM sellers WHERE lower(email)=lower(?) LIMIT 1',(clean,))
    if not existing.empty:
        return int(existing.iloc[0]['id'])
    store=safe(name) or clean.split('@')[0]
    data={'store_name':store,'owner_name':safe(name),'email':clean,'phone':'','city':'','state':'','website':'','instagram':'','store_bio':'','seller_story':'','specialties':'','logo_url':'','banner_url':'','status':'Pending Seller Approval','seller_level':'Verified Seller','rating':100,'completed_sales':0,'disputes':0,'strikes':0,'auction_override':'Yes','access_code':'','rules_accepted':'No','rules_accepted_at':'','created_at':now()}
    keys=['store_name','owner_name','email','phone','city','state','website','instagram','store_bio','seller_story','specialties','logo_url','banner_url','status','seller_level','rating','completed_sales','disputes','strikes','auction_override','access_code','rules_accepted','rules_accepted_at','created_at']
    return core_insert('sellers',data,'''INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,rules_accepted,rules_accepted_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in keys))
def upsert_app_user(auth_uid,email,display_name,account_type='Buyer',buyer_id=0,seller_id=0,password_hash='',admin_access='No',seller_status='Not Applied',account_status_value='Active'):
    clean=safe(email).strip().lower()
    now_value=now()
    existing=hosted_select('app_users',{'auth_user_id':auth_uid},limit=1) if hosted_enabled() else df('SELECT * FROM app_users WHERE auth_user_id=? LIMIT 1',(auth_uid,))
    if existing.empty:
        existing=hosted_select('app_users',{'email':clean},limit=1) if hosted_enabled() else df('SELECT * FROM app_users WHERE lower(email)=lower(?) LIMIT 1',(clean,))
    existing_row=existing.iloc[0].to_dict() if not existing.empty else {}
    if not seller_status or seller_status=='Not Applied':
        seller_status=safe(existing_row.get('seller_application_status'),'Not Applied')
    if not account_status_value:
        account_status_value=safe(existing_row.get('account_status') or existing_row.get('status'),'Active')
    data={'auth_user_id':auth_uid,'email':clean,'display_name':display_name,'account_type':account_type,'buyer_id':int(buyer_id or 0),'seller_id':int(seller_id or 0),'admin_access':admin_access,'seller_application_status':seller_status,'account_status':account_status_value,'status':account_status_value,'local_password_hash':password_hash,'updated_at':now_value}
    if existing.empty:
        data['created_at']=now_value
        keys=['auth_user_id','email','display_name','account_type','buyer_id','seller_id','admin_access','seller_application_status','account_status','status','local_password_hash','created_at','updated_at']
        return core_insert('app_users',data,'INSERT INTO app_users(auth_user_id,email,display_name,account_type,buyer_id,seller_id,admin_access,seller_application_status,account_status,status,local_password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',tuple(data[k] for k in keys))
    user_id=int(existing.iloc[0]['id'])
    if not password_hash:
        data.pop('local_password_hash',None)
        core_update('app_users',data,{'id':user_id},'UPDATE app_users SET auth_user_id=?,email=?,display_name=?,account_type=?,buyer_id=?,seller_id=?,admin_access=?,seller_application_status=?,account_status=?,status=?,updated_at=? WHERE id=?',(auth_uid,clean,display_name,account_type,int(buyer_id or 0),int(seller_id or 0),admin_access,seller_status,account_status_value,account_status_value,now_value,user_id))
    else:
        core_update('app_users',data,{'id':user_id},'UPDATE app_users SET auth_user_id=?,email=?,display_name=?,account_type=?,buyer_id=?,seller_id=?,admin_access=?,seller_application_status=?,account_status=?,status=?,local_password_hash=?,updated_at=? WHERE id=?',(auth_uid,clean,display_name,account_type,int(buyer_id or 0),int(seller_id or 0),admin_access,seller_status,account_status_value,account_status_value,password_hash,now_value,user_id))
    return user_id
def sign_in_session(auth_uid,email,access_token='',refresh_token=''):
    st.session_state['auth_session']={'user_id':safe(auth_uid),'email':safe(email).lower(),'access_token':safe(access_token),'refresh_token':safe(refresh_token)}
    if refresh_token:
        try:
            st.query_params['rt']=safe(refresh_token)
        except Exception:
            pass
def supabase_refresh_session(refresh_token):
    refresh_token=safe(refresh_token)
    if not refresh_token or not hosted_enabled():
        return False
    payload,detail=supabase_auth_request('token?grant_type=refresh_token',{'refresh_token':refresh_token})
    if not detail.get('ok'):
        AUTH_STATUS['last_error']=detail.get('message')
        return False
    user=(payload or {}).get('user') or {}
    uid=safe(user.get('id'))
    email=safe(user.get('email')).lower()
    if not uid or not email:
        return False
    new_access=safe((payload or {}).get('access_token'))
    new_refresh=safe((payload or {}).get('refresh_token')) or refresh_token
    sign_in_session(uid,email,new_access,new_refresh)
    return True
def restore_session_from_query_params():
    # Streamlit has no server-side session store, so a mobile page reload
    # otherwise drops auth_session and signs the user out. The Supabase
    # refresh token is round-tripped through the URL query string instead,
    # and rotated on every restore (see sign_in_session) to limit the value
    # of a leaked/logged URL. Good enough for a controlled tester launch;
    # move to a server-side session table before a public launch.
    if is_authenticated():
        return
    rt=safe(st.query_params.get('rt'))
    if not rt:
        return
    if supabase_refresh_session(rt):
        reconcile_authenticated_profile()
    else:
        try:
            del st.query_params['rt']
        except Exception:
            pass
def reconcile_authenticated_profile():
    if not is_authenticated():
        return
    user=current_app_user()
    if not user:
        display=auth_user_email().split('@')[0]
        bid=create_or_get_buyer_for_auth(auth_user_email(),display)
        upsert_app_user(auth_user_id(),auth_user_email(),display,'Buyer',bid,0,'','No','Not Applied','Active')
        user=current_app_user()
    bid=ensure_linked_buyer_profile()
    if bid:
        st.session_state['buyer_id']=bid
    sid=int((user or {}).get('seller_id') or 0)
    if sid and get_seller(sid) is not None:
        st.session_state['seller_tool_seller_id']=sid
def auth_sign_out():
    for key in ['auth_session','buyer_id','seller_tool_seller_id']:
        st.session_state.pop(key,None)
    try:
        del st.query_params['rt']
    except Exception:
        pass
def is_valid_email(value):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', safe(value).strip()))
def auth_create_account(name,email,password,confirm,account_type='Buyer'):
    if not safe(name) or not safe(email):
        return False,'Name and email are required.'
    if not is_valid_email(email):
        return False,'Enter a valid email address (example: name@example.com).'
    if len(safe(password))<8:
        return False,'Password must be at least 8 characters.'
    if password!=confirm:
        return False,'Password confirmation does not match.'
    clean=safe(email).strip().lower()
    auth_uid='local-'+hashlib.sha256(clean.encode('utf-8')).hexdigest()[:24]
    access_token=''
    refresh_token=''
    if hosted_enabled():
        payload,detail=supabase_auth_request('signup',{'email':clean,'password':password,'data':{'display_name':name,'account_type':'Universal'}})
        if not detail.get('ok'):
            AUTH_STATUS['last_error']=detail.get('message')
            return False,'Supabase sign-up failed. Check Auth Diagnostics for the masked error.'
        user=(payload or {}).get('user') or {}
        auth_uid=safe(user.get('id'))
        if not auth_uid:
            # Supabase returns a 200 with no user id when the email is already
            # registered (an anti-enumeration response). Falling back to a
            # synthetic non-UUID id here used to sign the browser in anyway,
            # which then broke every later Supabase query filtering
            # app_users.auth_user_id (a real uuid column) by that fake string.
            AUTH_STATUS['last_error']='Supabase sign-up returned no user id, which usually means this email is already registered.'
            return False,'This email may already have a House Of Wax account. Try Sign In instead.'
        access_token=safe((payload or {}).get('access_token'))
        refresh_token=safe((payload or {}).get('refresh_token'))
    password_hash='' if hosted_enabled() else hash_password(password)
    buyer_id=create_or_get_buyer_for_auth(clean,name)
    upsert_app_user(auth_uid,clean,name,'Buyer',buyer_id,0,password_hash,'No','Not Applied','Active')
    sign_in_session(auth_uid,clean,access_token,refresh_token)
    reconcile_authenticated_profile()
    return True,'House Of Wax account created and signed in. You can buy now and apply to sell from My Account.'
def auth_sign_in(email,password):
    clean=safe(email).strip().lower()
    if not is_valid_email(clean):
        AUTH_STATUS['last_error']=f'Sign-in blocked before contacting Supabase: "{clean}" does not look like a valid email address.'
        return False,'Sign-in failed. Check your email/password.'
    if hosted_enabled():
        payload,detail=supabase_auth_request('token?grant_type=password',{'email':clean,'password':password})
        if not detail.get('ok'):
            AUTH_STATUS['last_error']=detail.get('message')
            if 'email not confirmed' in safe(detail.get('message')).lower():
                return False,'This account exists but the email has not been confirmed yet. Check the inbox for a confirmation link, or ask an admin to confirm it in Supabase.'
            return False,'Sign-in failed. Check your email/password or Auth Diagnostics.'
        user=(payload or {}).get('user') or {}
        sign_in_session(safe(user.get('id')),clean,safe((payload or {}).get('access_token')),safe((payload or {}).get('refresh_token')))
        reconcile_authenticated_profile()
        return True,'Signed in.'
    row=df('SELECT * FROM app_users WHERE lower(email)=lower(?) LIMIT 1',(clean,))
    if row.empty or not verify_password(password,safe(row.iloc[0].get('local_password_hash'))):
        AUTH_STATUS['last_error']='Local fallback sign-in failed.'
        return False,'Sign-in failed. Check your email/password.'
    sign_in_session(safe(row.iloc[0].get('auth_user_id')),clean)
    reconcile_authenticated_profile()
    return True,'Signed in.'
def request_password_reset_email(email):
    clean=safe(email).strip().lower()
    if not is_valid_email(clean):
        return False,'Enter a valid email address.'
    if not hosted_enabled():
        return False,'Password reset requires Supabase Hosted to be configured.'
    payload,detail=supabase_auth_request('recover',{'email':clean})
    if not detail.get('ok'):
        AUTH_STATUS['last_error']=detail.get('message')
        return False,'Could not send the reset email right now. Check Auth Diagnostics or try again shortly.'
    # Supabase returns success here regardless of whether the email has an
    # account, by design, to avoid letting this form be used to check which
    # emails are registered. Keep the message generic to match that.
    return True,'If that email has a House Of Wax account, a password reset link has been sent.'
def complete_password_reset(recovery_token, new_password):
    if len(safe(new_password))<8:
        return False,'Password must be at least 8 characters.'
    if not hosted_enabled():
        return False,'Password reset requires Supabase Hosted to be configured.'
    _,anon=supabase_config()
    try:
        r=requests.put(
            supabase_auth_url('user'),
            headers={'apikey':anon,'Authorization':f'Bearer {safe(recovery_token)}','Content-Type':'application/json'},
            json={'password':new_password},
            timeout=12,
        )
        if r.status_code>=400:
            AUTH_STATUS['last_error']=f'HTTP {r.status_code}: '+(safe(r.text) or '(empty response body)')
            return False,'Could not set the new password. The reset link may have expired -- request a new one.'
        return True,'Password updated. You can sign in with your new password now.'
    except Exception as e:
        AUTH_STATUS['last_error']=f'{type(e).__name__}: '+(safe(e) or '(no exception detail)')
        return False,'Could not set the new password. Try again.'
def recovery_token_bridge():
    # Supabase's password-reset email links carry the access token in the URL
    # fragment (after #), which browsers never send to the server -- Streamlit's
    # Python side has no way to read it directly. This runs a tiny bit of JS in
    # every page load that, only when it detects a recovery link, moves the
    # token into a normal query param and reloads, which Python *can* read via
    # st.query_params. No-ops on every other page load.
    if safe(st.query_params.get('recovery_token')):
        return
    st.iframe("""
    <script>
    (function() {
      try {
        var hash = window.top.location.hash;
        if (hash && hash.indexOf('type=recovery') !== -1) {
          var params = new URLSearchParams(hash.substring(1));
          var token = params.get('access_token');
          if (token) {
            var url = new URL(window.top.location.href);
            url.hash = '';
            url.searchParams.set('recovery_token', token);
            window.top.location.replace(url.toString());
          }
        }
      } catch (e) {}
    })();
    </script>
    """, height=1)
def password_reset_completion_screen():
    header()
    st.header('Set a new password')
    token=safe(st.query_params.get('recovery_token'))
    if not token:
        st.error('This password reset link is invalid or has already been used.')
        return
    st.caption('This link was opened from a House Of Wax password reset email.')
    with st.form('recovery_form'):
        new_password=st.text_input('New password',type='password')
        confirm_password=st.text_input('Confirm new password',type='password')
        submitted=st.form_submit_button('Set new password')
    if submitted:
        if new_password!=confirm_password:
            st.error('Passwords do not match.')
        else:
            ok,msg=complete_password_reset(token,new_password)
            if ok:
                try:
                    del st.query_params['recovery_token']
                except Exception:
                    pass
                st.success(msg+' Reloading to sign in...')
                st.rerun()
            else:
                st.error(msg)
def public_privacy_policy():
    header()
    st.header('House Of Wax Privacy Policy')
    st.caption('Last updated: July 2026')
    st.write('This policy explains what information House Of Wax collects, how it is used, and who it is shared with.')
    st.markdown('### Information we collect')
    st.write('When you create an account, we collect your name, email address, and optionally your phone number, city, and state. Sellers additionally provide a store name, bio, and any listing details, photos, and pricing they choose to publish. If you contact a seller, submit an offer, or sign up for our newsletter, we collect the information included in that message or signup.')
    st.markdown('### How we use it')
    st.write('We use this information to operate the marketplace: creating your account, displaying your listings or purchase activity, connecting buyers and sellers, sending account-related and newsletter emails, and improving the platform. We do not sell your personal information to third parties.')
    st.markdown('### Payments')
    st.write('House Of Wax does not process payments directly. Buy and Make an Offer actions send a request to the seller; no card or financial account information is collected or stored by House Of Wax.')
    st.markdown('### Third-party services we use')
    st.write('We use Supabase for database and file storage, Resend for sending account and newsletter emails, and public music databases (Discogs, MusicBrainz, iTunes, Cover Art Archive) to help identify records and albums -- these lookups do not send your personal information to those services. House Of Wax administrators may use the Meta Graph API and YouTube Data API to publish House Of Wax content to Instagram and YouTube; these connections are used for publishing content, not for collecting visitor data.')
    st.markdown('### Cookies and sessions')
    st.write('We use browser session storage to keep you signed in while you use House Of Wax. We do not use third-party advertising or tracking cookies.')
    st.markdown('### Your choices')
    st.write('You can update your account information at any time from My Account. To request a copy of your data or ask us to delete your account, contact us at the email below.')
    st.markdown('### Children\'s privacy')
    st.write('House Of Wax is not directed at children under 13, and we do not knowingly collect personal information from children under 13.')
    st.markdown('### Changes to this policy')
    st.write('We may update this policy as House Of Wax changes. The date above reflects the most recent update.')
    st.markdown('### Contact us')
    st.write('Questions about this policy or your data can be sent to hello@shophouseofwax.com.')
def public_terms_of_service():
    header()
    st.header('House Of Wax Terms of Service')
    st.caption('Last updated: July 2026')
    st.write('These terms govern your use of House Of Wax. By creating an account or using the site, you agree to them.')
    st.markdown('### What House Of Wax is')
    st.write('House Of Wax is a marketplace and education platform for vinyl records, music collectibles, and culture goods, connecting independent sellers with buyers.')
    st.markdown('### Accounts')
    st.write('You agree to provide accurate account information and are responsible for activity under your account. Sellers are responsible for the accuracy, legality, condition, pricing, images, and descriptions of the items they list.')
    st.markdown('### Buying and selling')
    st.write('Buy and Make an Offer send a request to the seller, not a completed payment -- House Of Wax does not process payments directly. Sellers and buyers are expected to communicate honestly and follow through on agreed transactions.')
    st.markdown('### Prohibited listings')
    st.write('Counterfeit, stolen, unsafe, illegal, misleading, or hateful items are not allowed. This list is general and non-exhaustive. House Of Wax may investigate reports and may hide, restrict, or remove listings or accounts that violate these terms.')
    st.markdown('### Content you post')
    st.write('You keep ownership of photos, descriptions, and other content you post, and you grant House Of Wax permission to display it on the platform and in House Of Wax marketing, including social media. You are responsible for making sure you have the right to post what you upload.')
    st.markdown('### No warranty')
    st.write('House Of Wax is provided as-is. We do not guarantee the accuracy of listings, the conduct of buyers or sellers, or that the service will be uninterrupted or error-free.')
    st.markdown('### Changes to these terms')
    st.write('We may update these terms as House Of Wax changes. The date above reflects the most recent update.')
    st.markdown('### Contact us')
    st.write('Questions about these terms can be sent to hello@shophouseofwax.com.')
def conn(): return sqlite3.connect(DB)
def run(sql,p=()):
    c=conn(); c.execute(sql,p); c.commit(); c.close()
def insert(sql,p=()):
    c=conn(); cur=c.execute(sql,p); c.commit(); last_id=cur.lastrowid; c.close(); return last_id
def df(sql,p=()):
    c=conn(); out=pd.read_sql_query(sql,c,params=p); c.close(); return out
def table(t):
    hosted=core_table(t)
    if not hosted.empty or (hosted_enabled() and t in CORE_HOSTED_TABLES):
        return hosted
    try: return df(f'SELECT * FROM {t}')
    except Exception: return pd.DataFrame()
def addcol(t,c,typ):
    try:
        info=df(f'PRAGMA table_info({t})')
        if c not in info['name'].tolist(): run(f'ALTER TABLE {t} ADD COLUMN {c} {typ}')
    except Exception: pass
SUPABASE_STORAGE_BUCKET='house-of-wax-uploads'
def upload_to_supabase_storage(file_bytes, folder, filename, content_type='application/octet-stream'):
    url,anon=supabase_config()
    if not (url and anon):
        return ''
    token=auth_access_token() or anon
    object_path=f'{folder}/{filename}'
    try:
        r=requests.post(
            f'{url}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{object_path}',
            headers={'apikey':anon,'Authorization':f'Bearer {token}','Content-Type':content_type},
            data=file_bytes,
            timeout=20,
        )
        if r.status_code>=400:
            SUPABASE_STATUS['last_error']=f'Storage upload failed: HTTP {r.status_code} {safe(r.text)[:300]}'
            return ''
        return f'{url}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{object_path}'
    except Exception as e:
        SUPABASE_STATUS['last_error']=f'Storage upload error: {type(e).__name__}: {e}'
        return ''
def save_file(up,folder):
    if up is None: return ''
    clean=re.sub(r'[^A-Za-z0-9._-]+','_',Path(up.name).name).strip('._') or 'upload'
    filename=datetime.now().strftime('%Y%m%d%H%M%S%f')+'_'+uuid4().hex[:8]+'_'+clean
    if hosted_enabled():
        # Upload to persistent Supabase Storage so photos survive a redeploy.
        # Falls through to local disk (the old behavior) if the bucket isn't
        # set up yet, rather than losing the seller's upload entirely.
        hosted_url=upload_to_supabase_storage(up.getvalue(),folder,filename,safe(up.type) or 'application/octet-stream')
        if hosted_url:
            return hosted_url
    f=UPLOAD/folder; f.mkdir(parents=True,exist_ok=True)
    p=f/filename
    p.write_bytes(up.getbuffer()); return str(p)
def save_files(uploads,folder):
    if not uploads: return []
    if not isinstance(uploads,list): uploads=[uploads]
    return [p for p in [save_file(up,folder) for up in uploads] if p]
def safe_image(image_value, caption=None, width='stretch', fallback_text=None):
    value=safe(image_value)
    if image_value is None or (isinstance(image_value,str) and not value):
        if fallback_text:
            st.caption(fallback_text)
        return False
    image_to_render=image_value
    if isinstance(image_value,(str,Path)):
        raw=safe(image_value).strip()
        if raw.startswith(('http://','https://')):
            image_to_render=raw
        else:
            try:
                local_path=Path(raw).expanduser()
                if not local_path.exists() or not local_path.is_file():
                    st.caption(fallback_text or 'Image unavailable. Prototype image storage may not persist after redeploy. Production launch needs cloud image storage.')
                    return False
                image_to_render=str(local_path)
            except Exception:
                st.caption(fallback_text or 'Image unavailable. Prototype image storage may not persist after redeploy. Production launch needs cloud image storage.')
                return False
    try:
        st.image(image_to_render,caption=caption,width=width)
        return True
    except Exception:
        st.caption(fallback_text or 'Image unavailable. Prototype image storage may not persist after redeploy. Production launch needs cloud image storage.')
        return False
def setting(k,d=''):
    try:
        run('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT)')
        r=df('SELECT value FROM app_settings WHERE key=?',(k,))
        return d if r.empty else safe(r.iloc[0]['value'],d)
    except Exception:
        return d
def set_setting(k,v):
    run('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT)')
    run('INSERT OR REPLACE INTO app_settings(key,value) VALUES(?,?)',(k,str(v)))
def email_exists(t,email):
    if not email:
        return False
    if hosted_enabled() and t in ['buyers','sellers']:
        return not hosted_select(t,{'email':email.strip().lower()},limit=1).empty
    return not df(f'SELECT id FROM {t} WHERE lower(email)=lower(?)',(email.strip(),)).empty

SELLER_STATUSES=['Pending Seller Approval','Approved Seller','Suspended Seller']
LISTING_STATUSES=['Draft','Live','Hidden','Sold','Reported','Under Review','Removed by House Of Wax']
PUBLIC_LISTING_STATUSES=['Live','Active','Approved','Public']
INQUIRY_STATUSES=['New','Seller Responded','Closed']
PURCHASE_REQUEST_STATUSES=['New','Offer Pending','Seller Countered','Seller Accepted','Seller Declined','Pending Pickup/Payment','Sold','Closed']
UNAVAILABLE_LISTING_STATUSES=['Pending Pickup/Payment','Pending','Sold']
ACCOUNT_ROLES=['Buyer','Seller','Admin']
KEY_DATA_TABLES=['app_users','products','sellers','listing_inquiries','purchase_requests','product_gallery','tester_feedback','listing_reports']

def listing_status_help():
    st.info('Listing status guide: Draft = only you can see it. Live = buyers can see it. Hidden = not public. Sold = no longer available. Reported/Under Review = House Of Wax may investigate after a complaint. Removed by House Of Wax = removed for a platform rule issue.')

def normalize_seller_status(status):
    raw=safe(status,'Pending Seller Approval')
    mapping={'Approved':'Approved Seller','Active':'Approved Seller','Verified':'Approved Seller','Verified Seller':'Approved Seller','Pending':'Pending Seller Approval','Suspended':'Suspended Seller'}
    return mapping.get(raw,raw if raw in SELLER_STATUSES else 'Pending Seller Approval')

def pending_seller_application_count():
    sellers=table('sellers')
    if sellers.empty or 'status' not in sellers.columns:
        return 0
    return int((sellers['status'].apply(normalize_seller_status)=='Pending Seller Approval').sum())

def seller_can_publish(seller):
    return seller is not None and normalize_seller_status(seller.get('status'))=='Approved Seller'

def seller_rules_accepted(seller):
    return safe(seller.get('rules_accepted') if seller is not None else '').strip().lower() in ['yes','true','1','accepted']

def seller_can_publish_live(seller):
    return seller_can_publish(seller) and seller_rules_accepted(seller)

def accept_seller_rules(sid):
    accepted_at=now()
    core_update(
        'sellers',
        {'rules_accepted':'Yes','rules_accepted_at':accepted_at},
        {'id':int(sid)},
        'UPDATE sellers SET rules_accepted=?,rules_accepted_at=? WHERE id=?',
        ('Yes',accepted_at,int(sid))
    )
    return accepted_at

def seller_responsibility_policy_text():
    st.write('House Of Wax allows approved sellers to manage and publish listings in their own stores. Sellers are responsible for the accuracy, legality, condition, pricing, images, and descriptions of the items they post. House Of Wax does not pre-approve every listing. Listings and sellers may be reported by buyers, sellers, rights owners, or community members. House Of Wax may investigate reports and may hide, remove, or restrict listings or sellers that violate platform rules.')
    st.write('Prohibited seller behavior:')
    for item in ['No knowingly stolen goods','No counterfeit items represented as official','No misleading condition, pricing, or item details','No hateful, violent, illegal, or prohibited content','No harassment or abusive seller behavior','No knowingly false claims about rarity, pressing, autograph, or authenticity']:
        st.write(f'- {item}')

def render_seller_rules_acceptance(sid, seller, key_prefix='seller_rules'):
    st.markdown('#### Seller rules and responsibility')
    seller_responsibility_policy_text()
    if seller_rules_accepted(seller):
        status_badge('Rules accepted','success')
        st.caption('Accepted: '+safe(seller.get('rules_accepted_at'),'date not recorded'))
        return True
    st.warning('Accept seller rules before publishing. You can still save drafts without accepting rules.')
    agreed=st.checkbox('I understand that I am responsible for the accuracy, legality, condition, pricing, images, and descriptions of the items I post. I agree to follow House Of Wax marketplace rules.',key=f'{key_prefix}_rules_agreement_{int(sid)}')
    if st.button('Accept seller rules',key=f'{key_prefix}_accept_rules_{int(sid)}'):
        if not agreed:
            st.error('Check the responsibility agreement before accepting seller rules.')
            return False
        accepted_at=accept_seller_rules(int(sid))
        st.success('Seller rules accepted. Publishing is now available for approved sellers.')
        st.caption('Accepted: '+accepted_at)
        st.rerun()
    return False

def seller_onboarding_checklist(sid, seller):
    listings=hosted_select('products',{'seller_id':int(sid)},order='created_at.desc') if hosted_enabled() else df('SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC',(sid,))
    has_profile=bool(seller is not None and safe(seller.get('store_name')) and safe(seller.get('email')))
    has_contact=bool(seller is not None and (safe(seller.get('city')) or safe(seller.get('state')) or safe(seller.get('phone')) or safe(seller.get('contact_preference'))))
    has_draft=not listings.empty and listings['listing_status'].fillna('').isin(['Draft']).any()
    has_live=not listings.empty and listings['listing_status'].fillna('').isin(PUBLIC_LISTING_STATUSES).any()
    checklist=[
        ('Create seller store profile',has_profile),
        ('Add contact/location information',has_contact),
        ('Read seller rules',True),
        ('Accept seller responsibility agreement',seller_rules_accepted(seller)),
        ('Add first draft listing',has_draft or has_live),
        ('Publish first live listing',has_live),
    ]
    st.markdown('### Seller Onboarding')
    st.caption('Complete these basics so sellers understand their responsibility before publishing.')
    with st.container(border=True):
        for label,done in checklist:
            c1,c2=st.columns([0.7,0.3])
            c1.write(label)
            if done:
                c2.success('Complete')
            else:
                c2.warning('Not complete')
    render_seller_rules_acceptance(sid,seller,'seller_onboarding')
    return checklist

def seller_public_trust_label(seller):
    if seller is None:
        return 'House Of Wax Seller'
    status=normalize_seller_status(seller.get('status'))
    level=safe(seller.get('seller_level'))
    if safe(seller.get('store_name')).lower()=='house of wax official' or 'official' in level.lower():
        return 'House Of Wax Seller'
    if status=='Approved Seller':
        return 'Verified Seller'
    if status=='Suspended Seller':
        return 'Not Enabled'
    return 'New Seller'

def status_badge(label, kind='neutral'):
    classes={'success':'how-status-success','live':'how-status-success','danger':'how-status-danger','disabled':'how-status-danger','warning':'how-status-warning','pending':'how-status-warning','admin':'how-status-admin','neutral':'how-status-neutral'}
    css_class=classes.get(kind,'how-status-neutral')
    st.markdown(f'<span class="how-status {css_class}">{html.escape(safe(label))}</span>',unsafe_allow_html=True)

def listing_status_badge(status):
    label=safe(status,'Draft')
    kind='neutral'
    if label in ['Live','Active','Approved','Public','Available']:
        kind='success'
    elif label in ['Hidden','Removed by House Of Wax','Suspended Seller','Not Enabled']:
        kind='danger'
    elif label in ['Draft','Pending','Pending Pickup/Payment','Reported','Under Review','Pending Seller Approval']:
        kind='warning'
    elif label=='Sold':
        kind='danger'
    status_badge(label,kind)

def public_seller_trust_badge(seller):
    label=seller_public_trust_label(seller)
    kind='success' if label in ['Verified Seller','Active Seller','Trusted Seller','House Of Wax Seller'] else ('danger' if label=='Not Enabled' else 'neutral')
    status_badge(label,kind)

def seller_status_notice(seller):
    status=normalize_seller_status(seller.get('status') if seller is not None else '')
    if status=='Approved Seller':
        status_badge('Enabled','success')
        if seller_rules_accepted(seller):
            st.success("You're approved to publish listings straight to your store.")
        else:
            st.warning("You're approved to sell — accept House Of Wax's seller rules to start publishing live listings.")
    elif status=='Suspended Seller':
        status_badge('Not Enabled','danger')
        st.error('Your seller account is suspended. Reach out to House Of Wax if you think this needs a second look.')
    else:
        status_badge('Pending','warning')
        st.warning("You're all set to save drafts while House Of Wax reviews your seller account.")
    return status

def public_listing_query_statuses():
    return PUBLIC_LISTING_STATUSES+UNAVAILABLE_LISTING_STATUSES

def live_marketplace_statuses():
    return PUBLIC_LISTING_STATUSES

def seller_is_public_marketplace_seller(seller):
    return seller is not None and normalize_seller_status(seller.get('status'))=='Approved Seller'

def current_account_role():
    return effective_account_type()

def is_admin_unlocked():
    return is_admin_user() or (bool(st.session_state.get('testing_mode_enabled',False)) and not is_authenticated())

def prototype_role_notice():
    if is_authenticated():
        st.info("You're signed in as "+auth_user_email()+". You'll see the buyer and seller info tied to this account.")
    else:
        st.info("Browsing is open to everyone. Sign in when you're ready to list something, message a seller, or make an offer.")

def admin_access_warning():
    st.warning('House Of Wax Admin is visible because Testing mode/Admin mode is enabled.')

def mobile_navigation_bar():
    st.markdown('### Go to')
    buttons=['Search Music','My Account']
    if has_seller_capability():
        buttons.append('My Store')
    if is_authenticated():
        buttons.append('Sign Out')
    cols=st.columns(len(buttons))
    for i,label in enumerate(buttons):
        with cols[i]:
            if label=='Search Music' and st.button('Search Music',key='mobile_nav_search_music',width='stretch'):
                request_marketplace_navigation('Search Music',clear_product=True,clear_seller=True)
                st.rerun()
            elif label=='My Account' and st.button('My Account',key='mobile_nav_my_account',width='stretch'):
                request_marketplace_navigation('My Account')
                st.rerun()
            elif label=='My Store' and st.button('My Store',key='mobile_nav_my_store',width='stretch'):
                request_marketplace_navigation('Seller Dashboard')
                st.rerun()
            elif label=='Sign Out' and st.button('Sign Out',key='mobile_nav_sign_out',width='stretch'):
                auth_sign_out()
                request_marketplace_navigation('Home')
                st.rerun()

# ---------- Database ----------
def setup():
    c=conn(); cur=c.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT)')
    cur.execute('''CREATE TABLE IF NOT EXISTS app_users(id INTEGER PRIMARY KEY AUTOINCREMENT,auth_user_id TEXT UNIQUE,email TEXT UNIQUE,display_name TEXT,account_type TEXT,buyer_id INTEGER DEFAULT 0,seller_id INTEGER DEFAULT 0,seller_application_status TEXT DEFAULT 'Not Applied',admin_access TEXT DEFAULT 'No',account_status TEXT DEFAULT 'Active',status TEXT DEFAULT 'Active',local_password_hash TEXT,created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS buyers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,phone TEXT,city TEXT,state TEXT,bio TEXT,status TEXT DEFAULT 'Trusted Buyer',rating REAL DEFAULT 100,completed_purchases INTEGER DEFAULT 0,unpaid_orders INTEGER DEFAULT 0,disputes INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS sellers(id INTEGER PRIMARY KEY AUTOINCREMENT,store_name TEXT,owner_name TEXT,email TEXT UNIQUE,phone TEXT,city TEXT,state TEXT,website TEXT,instagram TEXT,store_bio TEXT,seller_story TEXT,specialties TEXT,logo_url TEXT,banner_url TEXT,status TEXT DEFAULT 'Pending Seller Approval',seller_level TEXT DEFAULT 'Verified Seller',rating REAL DEFAULT 100,completed_sales INTEGER DEFAULT 0,disputes INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,auction_override TEXT DEFAULT 'Yes',access_code TEXT,rules_accepted TEXT DEFAULT 'No',rules_accepted_at TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,sku TEXT,barcode TEXT,catalog_number TEXT,matrix_runout TEXT,category TEXT,artist TEXT,title TEXT,format TEXT,label TEXT,release_year TEXT,genre TEXT,media_grade TEXT,sleeve_grade TEXT,condition_notes TEXT,description TEXT,price REAL DEFAULT 0,quantity INTEGER DEFAULT 1,shipping_price REAL DEFAULT 0,image_url TEXT,video_url TEXT,audio_url TEXT,external_release_url TEXT,listing_status TEXT DEFAULT 'Draft',listing_type TEXT DEFAULT 'Fixed Price',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS product_gallery(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,image_url TEXT,caption TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,order_type TEXT,status TEXT DEFAULT 'New',item_price REAL DEFAULT 0,shipping_price REAL DEFAULT 0,platform_fee REAL DEFAULT 0,seller_payout REAL DEFAULT 0,buyer_message TEXT,created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,reviewer_type TEXT,reviewer_id INTEGER,reviewee_type TEXT,reviewee_id INTEGER,rating INTEGER,comment TEXT,public TEXT DEFAULT 'Yes',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,sender_type TEXT,subject TEXT,message TEXT,status TEXT DEFAULT 'New',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS listing_inquiries(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,buyer_name TEXT,buyer_contact TEXT,preferred_contact_method TEXT,message TEXT,status TEXT DEFAULT 'New',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS purchase_requests(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,buyer_name TEXT,buyer_contact TEXT,preferred_contact_method TEXT,fulfillment_preference TEXT,offer_price REAL DEFAULT 0,buyer_message TEXT,status TEXT DEFAULT 'New',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS want_list(id INTEGER PRIMARY KEY AUTOINCREMENT,buyer_id INTEGER,artist TEXT,title TEXT,status TEXT DEFAULT 'Active',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,buyer_id INTEGER,purchase_request_id INTEGER,product_id INTEGER,rating INTEGER,review_text TEXT,buyer_display_name TEXT,created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS tester_feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,tester_name TEXT,tester_type TEXT,page_flow TEXT,worked_well TEXT,confusing TEXT,felt_broken TEXT,missing TEXT,ease_rating INTEGER,would_use_again TEXT,open_notes TEXT,status TEXT DEFAULT 'New',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS listing_reports(id INTEGER PRIMARY KEY AUTOINCREMENT,listing_id INTEGER,seller_id INTEGER,reporter_name TEXT,reporter_contact TEXT,reason TEXT,details TEXT,status TEXT DEFAULT 'Open',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_followers(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,buyer_id INTEGER,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_badges(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,badge_name TEXT,badge_type TEXT,active TEXT DEFAULT 'Yes',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS store_announcements(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,title TEXT,body TEXT,status TEXT DEFAULT 'Active',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_events(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,event_title TEXT,event_type TEXT,event_date TEXT,description TEXT,status TEXT DEFAULT 'Active',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_policies(seller_id INTEGER PRIMARY KEY,shipping_policy TEXT,return_policy TEXT,grading_policy TEXT,customer_service_policy TEXT,buyer_requirements TEXT,local_pickup_policy TEXT,processing_time TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS auctions(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,auction_title TEXT,starting_bid REAL,reserve_price REAL,buy_now_price REAL,bid_increment REAL DEFAULT 1,start_time TEXT,end_time TEXT,status TEXT DEFAULT 'Live',notes TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS bids(id INTEGER PRIMARY KEY AUTOINCREMENT,auction_id INTEGER,buyer_id INTEGER,bid_amount REAL,bid_time TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS listing_flags(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,reason TEXT,details TEXT,status TEXT DEFAULT 'Open',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS culture_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,category TEXT,author TEXT,body TEXT,image_url TEXT,status TEXT DEFAULT 'Published',created_at TEXT)''')
    cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,category TEXT,audience TEXT,level TEXT,summary TEXT,body TEXT,house_tip TEXT,image_url TEXT,video_url TEXT,status TEXT DEFAULT 'Draft',featured TEXT DEFAULT 'No',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS glossary_terms(id INTEGER PRIMARY KEY AUTOINCREMENT,term TEXT UNIQUE,category TEXT,plain_definition TEXT,why_it_matters TEXT,example TEXT,status TEXT DEFAULT 'Published',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_drafts(id INTEGER PRIMARY KEY AUTOINCREMENT,source_type TEXT,source_id INTEGER,title TEXT,platform TEXT,caption TEXT,script TEXT,hashtags TEXT,cta TEXT,status TEXT DEFAULT 'Draft',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_calendar(id INTEGER PRIMARY KEY AUTOINCREMENT,content_type TEXT,topic TEXT,platform TEXT,planned_date TEXT,status TEXT DEFAULT 'Planned',notes TEXT,created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS homepage_blocks(id INTEGER PRIMARY KEY AUTOINCREMENT,block_name TEXT,title TEXT,subtitle TEXT,body TEXT,button_text TEXT,button_target TEXT,image_url TEXT,video_url TEXT,status TEXT DEFAULT 'Active',sort_order INTEGER DEFAULT 0,created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS quick_tips(id INTEGER PRIMARY KEY AUTOINCREMENT,tip_text TEXT,category TEXT,status TEXT DEFAULT 'Active',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS did_you_know(id INTEGER PRIMARY KEY AUTOINCREMENT,fact_text TEXT,category TEXT,status TEXT DEFAULT 'Active',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS newsletter_signups(id INTEGER PRIMARY KEY AUTOINCREMENT,email TEXT,name TEXT,source TEXT,created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_series(id INTEGER PRIMARY KEY AUTOINCREMENT,series_name TEXT,description TEXT,audience TEXT,tone TEXT,default_format TEXT,active TEXT DEFAULT 'Yes',created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_campaigns(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_name TEXT,theme TEXT,goal TEXT,start_date TEXT,end_date TEXT,target_audience TEXT,status TEXT DEFAULT 'Planning',notes TEXT,created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_repurposing(id INTEGER PRIMARY KEY AUTOINCREMENT,post_id INTEGER,series_name TEXT,short_caption TEXT,reel_script TEXT,newsletter_blurb TEXT,marketplace_callout TEXT,created_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS barcode_lookup_cache(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT,
        source TEXT,
        external_id TEXT,
        artist TEXT,
        title TEXT,
        format TEXT,
        label TEXT,
        release_year TEXT,
        country TEXT,
        genre TEXT,
        style TEXT,
        catalog_number TEXT,
        image_url TEXT,
        external_url TEXT,
        raw_summary TEXT,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listing_media_policy(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        default_image_source TEXT,
        seller_photo_recommended TEXT,
        notes TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS how_releases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        barcode TEXT,
        artist TEXT,
        title TEXT,
        format TEXT,
        label TEXT,
        release_year TEXT,
        country TEXT,
        genre TEXT,
        style TEXT,
        catalog_number TEXT,
        image_url TEXT,
        external_release_url TEXT,
        discogs_id TEXT,
        musicbrainz_id TEXT,
        gs1_status TEXT,
        source_confidence INTEGER DEFAULT 50,
        verification_status TEXT DEFAULT 'Unverified',
        admin_notes TEXT,
        seller_correction_notes TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS how_release_sources(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        release_id INTEGER,
        source_name TEXT,
        source_external_id TEXT,
        source_url TEXT,
        source_confidence INTEGER DEFAULT 50,
        raw_summary TEXT,
        created_at TEXT
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS how_release_corrections(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        release_id INTEGER,
        seller_id INTEGER,
        field_name TEXT,
        old_value TEXT,
        suggested_value TEXT,
        correction_note TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TEXT
    )""")
    c.commit(); c.close()
    mig={'app_users':{'auth_user_id':'TEXT','email':'TEXT','display_name':'TEXT','account_type':'TEXT','buyer_id':'INTEGER','seller_id':'INTEGER','seller_application_status':'TEXT','admin_access':'TEXT','account_status':'TEXT','status':'TEXT','local_password_hash':'TEXT','created_at':'TEXT','updated_at':'TEXT'},'buyers':{'state':'TEXT','bio':'TEXT','status':'TEXT','rating':'REAL','completed_purchases':'INTEGER','unpaid_orders':'INTEGER'},'sellers':{'state':'TEXT','website':'TEXT','instagram':'TEXT','seller_story':'TEXT','specialties':'TEXT','logo_url':'TEXT','banner_url':'TEXT','status':'TEXT','seller_level':'TEXT','rating':'REAL','completed_sales':'INTEGER','auction_override':'TEXT','access_code':'TEXT','contact_preference':'TEXT','rules_accepted':'TEXT','rules_accepted_at':'TEXT'},'products':{'sku':'TEXT','barcode':'TEXT','catalog_number':'TEXT','matrix_runout':'TEXT','label':'TEXT','release_year':'TEXT','video_url':'TEXT','audio_url':'TEXT','external_release_url':'TEXT','listing_status':'TEXT','listing_type':'TEXT','reviewer_notes':'TEXT','reference_image_url':'TEXT'},'feedback':{'public':'TEXT'},'listing_reports':{'listing_id':'INTEGER','seller_id':'INTEGER','reporter_name':'TEXT','reporter_contact':'TEXT','reason':'TEXT','details':'TEXT','status':'TEXT','created_at':'TEXT','updated_at':'TEXT'},'knowledge_posts':{'video_url':'TEXT'},'homepage_blocks':{'video_url':'TEXT'},'purchase_requests':{'counter_price':'REAL','counter_message':'TEXT'},'newsletter_signups':{'interest':'TEXT','updated_at':'TEXT'}}
    for t,cols in mig.items():
        for col,typ in cols.items(): addcol(t,col,typ)
    try:
        run("UPDATE app_users SET account_status=COALESCE(NULLIF(account_status,''),COALESCE(NULLIF(status,''),'Active'))")
        run("UPDATE app_users SET seller_application_status='Not Applied' WHERE COALESCE(seller_id,0)=0 AND (seller_application_status IS NULL OR seller_application_status='')")
        run("UPDATE app_users SET seller_application_status='Pending Seller Approval' WHERE COALESCE(seller_id,0)>0 AND (seller_application_status IS NULL OR seller_application_status='' OR seller_application_status='Not Applied')")
    except Exception:
        pass
    for k,v in {'site_tagline':'A seller-powered marketplace for records, music culture, clothing, and collectors.','announcement':'V25.43.42 verified domain sender active','platform_commission_percent':'9','auction_commission_percent':'10'}.items():
        if setting(k, None) is None: set_setting(k,v)
    old_announcement='V16'+' testing build: all core options are active.'
    old_v25_18_announcement='V25.18.1'+' testing tools active'
    old_v25_23_announcement='V25.23'+' testing tools active'
    old_v25_24_announcement='V25.24'+' launch audit tools active'
    old_v25_25_announcement='V25.25'+' demo readiness tools active'
    old_v25_26_announcement='V25.26'+' pitch and demo package active'
    old_v25_27_announcement='V25.27'+' production readiness roadmap and auth plan active'
    old_v25_28_announcement='V25.28'+' Supabase and hosted database prep active'
    old_v25_29_announcement='V25.29'+' auth and login prep active'
    old_v25_30_announcement='V25.30'+' legal and policy pages prep active'
    old_v25_31_announcement='V25.31'+' payment and checkout decision prep active'
    old_v25_32_announcement='V25.32'+' seller onboarding and marketplace launch checklist active'
    old_v25_33_announcement='V25.33'+' final demo testing and business plan foundation active'
    old_v25_34_announcement='V25.34'+' business plan and funding package active'
    old_v25_34_wedge_announcement='V25.34'+' wedge strategy, testing script, and funding package active'
    old_v25_35_announcement='V25.35'+' knowledge center and education hub active'
    old_v25_36_announcement='V25.36'+' live tester feedback system active'
    old_v25_36_1_announcement='V25.36.1'+' inventory and store visibility clarity active'
    old_v25_36_2_announcement='V25.36.2'+' tester onboarding and inventory clarity fix active'
    old_v25_36_3_announcement='V25.36.3'+' core inventory and profile persistence fix active'
    old_v25_37_1_announcement='V25.37.1'+' Supabase diagnostics and RLS repair active'
    old_v25_37_2_announcement='V25.37.2'+' real profile flow repair active'
    old_v25_37_3_announcement='V25.37.3'+' safe image rendering fix active'
    old_v25_38_announcement='V25.38'+' seller simplicity and fast listing flow active'
    old_v25_39_announcement='V25.39'+' seller publishing and trust policy fix active'
    old_v25_39_1_announcement='V25.39.1'+' direct live publish and button contrast fix active'
    old_v25_39_2_announcement='V25.39.2'+' marketplace and admin separation fix active'
    old_v25_40_announcement='V25.40'+' marketplace search across all sellers active'
    old_v25_40_1_announcement='V25.40.1'+' marketplace polish and status visibility fix active'
    old_v25_41_announcement='V25.41'+' seller onboarding and rules acceptance active'
    old_v25_42_announcement='V25.42'+' music data source strategy and lookup reliability active'
    old_v25_43_announcement='V25.43'+' real login and role access foundation active'
    old_v25_43_1_announcement='V25.43.1'+' simple buyer search and navigation cleanup active'
    old_v25_43_2_announcement='V25.43.2'+' mobile account flow and profile persistence repair active'
    old_v25_43_3_announcement='V25.43.3'+' one account, user directory, and mobile navigation repair active'
    old_v25_43_4_announcement='V25.43.4'+' session persistence and local-only data warnings active'
    old_v25_43_5_announcement='V25.43.5'+' signup uuid fix active'
    old_v25_43_6_announcement='V25.43.6'+' auth error visibility fix active'
    old_v25_43_7_announcement='V25.43.7'+' email format validation active'
    old_v25_43_8_announcement='V25.43.8'+' signin email validation active'
    old_v25_43_9_announcement='V25.43.9'+' diagnostic recording fix active'
    old_v25_43_10_announcement='V25.43.10'+' unconfirmed email message active'
    old_v25_43_11_announcement='V25.43.11'+' auth mode diagnostic active'
    old_v25_43_12_announcement='V25.43.12'+' security hardening pass active'
    old_v25_43_13_announcement='V25.43.13'+' content admin and video embeds active'
    old_v25_43_14_announcement='V25.43.14'+' legacy access code login removed'
    old_v25_43_15_announcement='V25.43.15'+' dead content admin tabs removed'
    old_v25_43_16_announcement='V25.43.16'+' password reset active'
    old_v25_43_17_announcement='V25.43.17'+' persistent upload storage active'
    old_v25_43_18_announcement='V25.43.18'+' session restore crash fixed'
    old_v25_43_19_announcement='V25.43.19'+' purchase request status fix active'
    old_v25_43_20_announcement='V25.43.20'+' knowledge hub persistence fix active'
    old_v25_43_21_announcement='V25.43.21'+' knowledge hub auto-seed fix active'
    old_v25_43_22_announcement='V25.43.22'+' reference image labeling active'
    old_v25_43_23_announcement='V25.43.23'+' visual identity refresh active'
    old_v25_43_24_announcement='V25.43.24'+' groove dividers and card polish active'
    old_v25_43_25_announcement='V25.43.25'+' tab accent and image framing active'
    old_v25_43_26_announcement='V25.43.26'+' grading scale and make an offer active'
    old_v25_43_27_announcement='V25.43.27'+' admin screens consolidated active'
    old_v25_43_28_announcement='V25.43.28'+' homepage and seller tools consolidated active'
    old_v25_43_29_announcement='V25.43.29'+' shipping guidance active'
    old_v25_43_30_announcement='V25.43.30'+' admin permissions hardened active'
    old_v25_43_31_announcement='V25.43.31'+' homepage and newsletter data now persisted active'
    old_v25_43_32_announcement='V25.43.32'+' seller engagement data now persisted active'
    old_v25_43_33_announcement='V25.43.33'+' pending seller application alert active'
    old_v25_43_34_announcement='V25.43.34'+' remaining local-only bugs fixed active'
    old_v25_43_35_announcement='V25.43.35'+' admin jump-to-review crash fixed active'
    old_v25_43_36_announcement='V25.43.36'+' save failures now show errors active'
    old_v25_43_37_announcement='V25.43.37'+' cleanup pass 1 active'
    old_v25_43_38_announcement='V25.43.38'+' cleanup pass 2 active'
    old_v25_43_39_announcement='V25.43.39'+' cleanup pass 3 active'
    old_v25_43_40_announcement='V25.43.40'+' barcode tip and price suggestions active'
    old_v25_43_41_announcement='V25.43.41'+' email notifications active'
    old_v25_43_42_announcement='V25.43.42'+' verified domain sender active'
    old_v25_43_43_announcement='V25.43.43'+' Instagram auto-posting active'
    old_v25_43_44_announcement='V25.43.44'+' YouTube upload connection active'
    old_v25_43_45_announcement='V25.43.45'+' Share buttons and graded pricing active'
    old_v25_43_46_announcement='V25.43.46'+' Seller website link fix active'
    old_v25_43_47_announcement='V25.43.47'+' Public privacy policy page active'
    old_v25_43_48_announcement='V25.43.48'+' Public terms of service page active'
    old_v25_43_49_announcement='V25.43.49'+' Facebook Page posting active'
    old_v25_43_50_announcement='V25.43.50'+' Session token auto-refresh fix active'
    old_v25_43_51_announcement='V25.43.51'+' Want List with match notifications active'
    old_v25_43_52_announcement='V25.43.52'+' Seller written reviews active'
    old_v25_43_53_announcement='V25.43.53'+' Buyer-facing sold price history active'
    old_v25_43_54_announcement='V25.43.54'+' Dead orders/feedback system removed active'
    old_v25_43_55_announcement='V25.43.55'+' Buyer account reachability fix active'
    old_v25_43_56_announcement='V25.43.56'+' 6 more dead menu pages removed active'
    old_v25_43_57_announcement='V25.43.57'+' AI avatar assistant scaffolding added (off by default) active'
    if setting('announcement') in [old_announcement,old_v25_18_announcement,old_v25_23_announcement,old_v25_24_announcement,old_v25_25_announcement,old_v25_26_announcement,old_v25_27_announcement,old_v25_28_announcement,old_v25_29_announcement,old_v25_30_announcement,old_v25_31_announcement,old_v25_32_announcement,old_v25_33_announcement,old_v25_34_announcement,old_v25_34_wedge_announcement,old_v25_35_announcement,old_v25_36_announcement,old_v25_36_1_announcement,old_v25_36_2_announcement,old_v25_36_3_announcement,old_v25_37_1_announcement,old_v25_37_2_announcement,old_v25_37_3_announcement,old_v25_38_announcement,old_v25_39_announcement,old_v25_39_1_announcement,old_v25_39_2_announcement,old_v25_40_announcement,old_v25_40_1_announcement,old_v25_41_announcement,old_v25_42_announcement,old_v25_43_announcement,old_v25_43_1_announcement,old_v25_43_2_announcement,old_v25_43_3_announcement,old_v25_43_4_announcement,old_v25_43_5_announcement,old_v25_43_6_announcement,old_v25_43_7_announcement,old_v25_43_8_announcement,old_v25_43_9_announcement,old_v25_43_10_announcement,old_v25_43_11_announcement,old_v25_43_12_announcement,old_v25_43_13_announcement,old_v25_43_14_announcement,old_v25_43_15_announcement,old_v25_43_16_announcement,old_v25_43_17_announcement,old_v25_43_18_announcement,old_v25_43_19_announcement,old_v25_43_20_announcement,old_v25_43_21_announcement,old_v25_43_22_announcement,old_v25_43_23_announcement,old_v25_43_24_announcement,old_v25_43_25_announcement,old_v25_43_26_announcement,old_v25_43_27_announcement,old_v25_43_28_announcement,old_v25_43_29_announcement,old_v25_43_30_announcement,old_v25_43_31_announcement,old_v25_43_32_announcement,old_v25_43_33_announcement,old_v25_43_34_announcement,old_v25_43_35_announcement,old_v25_43_36_announcement,old_v25_43_37_announcement,old_v25_43_38_announcement,old_v25_43_39_announcement,old_v25_43_40_announcement,old_v25_43_41_announcement,old_v25_43_42_announcement,old_v25_43_43_announcement,old_v25_43_44_announcement,old_v25_43_45_announcement,old_v25_43_46_announcement,old_v25_43_47_announcement,old_v25_43_48_announcement,old_v25_43_49_announcement,old_v25_43_50_announcement,old_v25_43_51_announcement,old_v25_43_52_announcement,old_v25_43_53_announcement,old_v25_43_54_announcement,old_v25_43_55_announcement,old_v25_43_56_announcement,old_v25_43_57_announcement]:
        set_setting('announcement','V25.43.58 Fix: public products visibility (anon select permission) active')
setup()
recovery_token_bridge()


# ---------- V21 Visual Identity ----------
def apply_brand_style():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap');
    :root {
        --how-black: #0b0b0b;
        --how-charcoal: #171717;
        --how-ink: #222222;
        --how-cream: #f6efe3;
        --how-bone: #fbf7ef;
        --how-gold: #c9a45c;
        --how-oxblood: #6f1d1b;
        --how-oxblood-bright: #a8342f;
        --how-muted: #9b8f80;
        --how-card: #151515;
        --how-line: rgba(201,164,92,.35);
        --how-display: 'Fraunces', Georgia, 'Iowan Old Style', serif;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(201,164,92,.14), transparent 28%),
            radial-gradient(circle at top right, rgba(111,29,27,.18), transparent 24%),
            linear-gradient(180deg, #0b0b0b 0%, #151515 45%, #0b0b0b 100%);
        color: var(--how-cream);
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #090909 0%, #171717 100%);
        border-right: 1px solid rgba(201,164,92,.25);
    }

    section[data-testid="stSidebar"] * {
        color: var(--how-cream) !important;
    }

    h1, h2, h3 {
        letter-spacing: 0;
        color: var(--how-cream) !important;
        font-family: var(--how-display) !important;
        font-weight: 600 !important;
    }

    p, li, label, span {
        color: rgba(246,239,227,.92);
    }

    .block-container {
        padding-top: 1.8rem;
        padding-left: min(5vw, 2.5rem);
        padding-right: min(5vw, 2.5rem);
        max-width: 1180px;
    }

    [data-testid="stImage"] img {
        border-radius: 12px;
        object-fit: cover;
        border: 1px solid rgba(201,164,92,.28);
        box-shadow: 0 8px 22px rgba(0,0,0,.28);
    }

    div[data-testid="stMetric"] {
        background: rgba(251,247,239,.06);
        border: 1px solid rgba(201,164,92,.24);
        border-radius: 18px;
        padding: 14px 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,.18);
    }

    div[data-testid="stMetric"] label {
        color: rgba(246,239,227,.72) !important;
    }

    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--how-gold) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(251,247,239,.055);
        border: 1px solid rgba(201,164,92,.22);
        border-radius: 20px;
        box-shadow: 0 18px 44px rgba(0,0,0,.18);
    }

    .stButton > button,
    .stFormSubmitButton > button,
    .stDownloadButton > button,
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stDownloadButton"] > button,
    a[data-testid="stLinkButton"] {
        border-radius: 999px;
        border: 2px solid #c9a45c !important;
        background: linear-gradient(135deg, #d8b56b 0%, #c9a45c 48%, #9d732d 100%) !important;
        color: #0b0b0b !important;
        font-weight: 800;
        letter-spacing: .01em;
        padding: .55rem 1rem;
        box-shadow: 0 10px 30px rgba(0,0,0,.3);
        white-space: normal;
        opacity: 1 !important;
        text-decoration: none !important;
    }

    .stButton > button *,
    .stButton > button p,
    .stButton > button span,
    .stFormSubmitButton > button *,
    .stFormSubmitButton > button p,
    .stFormSubmitButton > button span,
    .stDownloadButton > button *,
    .stDownloadButton > button p,
    .stDownloadButton > button span,
    a[data-testid="stLinkButton"] *,
    a[data-testid="stLinkButton"] p,
    a[data-testid="stLinkButton"] span {
        color: #0b0b0b !important;
        font-weight: 850 !important;
    }

    .stButton > button:hover,
    .stFormSubmitButton > button:hover,
    .stDownloadButton > button:hover,
    div[data-testid="stButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    div[data-testid="stDownloadButton"] > button:hover,
    a[data-testid="stLinkButton"]:hover {
        border-color: #f6efe3 !important;
        background: linear-gradient(135deg, #f0cf85 0%, #d8b56b 52%, #b88937 100%) !important;
        color: #0b0b0b !important;
        transform: translateY(-1px);
        filter: brightness(1.06);
    }

    .stButton > button:hover *,
    .stFormSubmitButton > button:hover *,
    .stDownloadButton > button:hover *,
    a[data-testid="stLinkButton"]:hover * {
        color: #0b0b0b !important;
    }

    .stButton > button:active,
    .stFormSubmitButton > button:active,
    .stDownloadButton > button:active,
    div[data-testid="stButton"] > button:active,
    div[data-testid="stFormSubmitButton"] > button:active,
    div[data-testid="stDownloadButton"] > button:active,
    a[data-testid="stLinkButton"]:active {
        background: #a7792f !important;
        color: #0b0b0b !important;
        border-color: #f6efe3 !important;
        transform: translateY(0);
    }

    .stButton > button:focus,
    .stFormSubmitButton > button:focus,
    .stDownloadButton > button:focus,
    div[data-testid="stButton"] > button:focus,
    div[data-testid="stFormSubmitButton"] > button:focus,
    div[data-testid="stDownloadButton"] > button:focus,
    a[data-testid="stLinkButton"]:focus {
        outline: 3px solid rgba(246,239,227,.9) !important;
        outline-offset: 2px !important;
        color: #0b0b0b !important;
    }

    .stButton > button:disabled,
    .stFormSubmitButton > button:disabled,
    .stDownloadButton > button:disabled,
    div[data-testid="stButton"] > button:disabled,
    div[data-testid="stFormSubmitButton"] > button:disabled,
    div[data-testid="stDownloadButton"] > button:disabled {
        background: #4a4237 !important;
        color: #f6efe3 !important;
        border-color: rgba(201,164,92,.45) !important;
        opacity: .75 !important;
        box-shadow: none !important;
    }

    .stButton > button:disabled *,
    .stFormSubmitButton > button:disabled *,
    .stDownloadButton > button:disabled * {
        color: #f6efe3 !important;
    }

    section[data-testid="stSidebar"] .stButton > button,
    section[data-testid="stSidebar"] .stFormSubmitButton > button,
    section[data-testid="stSidebar"] .stDownloadButton > button {
        background: linear-gradient(135deg, #f6efe3 0%, #d8b56b 100%) !important;
        color: #0b0b0b !important;
        border-color: #c9a45c !important;
    }

    section[data-testid="stSidebar"] .stButton > button *,
    section[data-testid="stSidebar"] .stFormSubmitButton > button *,
    section[data-testid="stSidebar"] .stDownloadButton > button * {
        color: #0b0b0b !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: .35rem;
        border-bottom: 1px solid rgba(201,164,92,.25);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px 999px 0 0;
        color: rgba(246,239,227,.72);
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--how-cream) !important;
        font-weight: 700;
    }

    .stTabs [data-baseweb="tab-highlight"] {
        background-color: var(--how-oxblood-bright) !important;
        height: 2px !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        color: var(--how-gold) !important;
    }

    .stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
        background: rgba(251,247,239,.98) !important;
        border-color: rgba(201,164,92,.55) !important;
        color: #111111 !important;
        caret-color: #111111 !important;
        border-radius: 12px !important;
        padding-left: 0.85rem !important;
        text-indent: 0 !important;
    }

    .how-hero {
        position: relative;
        border: 1px solid rgba(201,164,92,.35);
        border-radius: 28px;
        padding: 34px;
        background:
            radial-gradient(circle at 50% 0%, rgba(201,164,92,.16), transparent 55%),
            linear-gradient(135deg, rgba(11,11,11,.92), rgba(34,20,16,.86)),
            radial-gradient(circle at bottom right, rgba(111,29,27,.22), transparent 34%);
        box-shadow: 0 24px 70px rgba(0,0,0,.35);
        margin-bottom: 22px;
        overflow: hidden;
    }

    .how-hero::before {
        content: '';
        position: absolute;
        left: 50%;
        top: -220px;
        width: 460px;
        height: 460px;
        border-radius: 50%;
        border: 1px solid rgba(201,164,92,.16);
        box-shadow: 0 0 0 40px rgba(201,164,92,.05), 0 0 0 80px rgba(201,164,92,.03);
        transform: translateX(-50%);
        pointer-events: none;
    }

    .how-kicker {
        color: var(--how-gold);
        font-size: .78rem;
        letter-spacing: .18em;
        text-transform: uppercase;
        font-weight: 900;
        margin-bottom: .5rem;
    }

    .how-title {
        position: relative;
        color: var(--how-cream);
        font-family: var(--how-display);
        font-size: clamp(2.5rem, 6vw, 5.2rem);
        line-height: .95;
        letter-spacing: 0;
        font-weight: 600;
        margin-bottom: .6rem;
    }

    .how-title em {
        font-style: normal;
        color: var(--how-gold);
    }

    .how-subtitle {
        color: var(--how-gold);
        font-size: clamp(1.15rem, 2.2vw, 1.8rem);
        font-weight: 700;
        margin-bottom: .8rem;
    }

    .how-body {
        color: rgba(246,239,227,.86);
        font-size: 1.05rem;
        line-height: 1.65;
        max-width: 760px;
    }

    .how-section {
        border-top: 1px solid rgba(201,164,92,.28);
        padding-top: 22px;
        margin-top: 26px;
        margin-bottom: 14px;
    }

    .how-section .how-kicker {
        margin-bottom: 0;
    }

    .how-section-title {
        color: var(--how-cream);
        font-family: var(--how-display);
        font-size: 2rem;
        font-weight: 600;
        letter-spacing: 0;
        margin-bottom: .2rem;
    }

    .how-mobile-note {
        color: rgba(246,239,227,.72);
        font-size: .9rem;
        line-height: 1.45;
    }

    @media (max-width: 760px) {
        .block-container {
            padding: 1rem .85rem 2rem .85rem;
        }

        .how-hero {
            border-radius: 18px;
            padding: 22px;
        }

        .how-title {
            font-size: 2.2rem;
            line-height: 1;
        }

        div[data-testid="column"] {
            min-width: 100% !important;
            width: 100% !important;
            flex: 1 1 100% !important;
        }

        .stButton > button {
            width: 100%;
            min-height: 2.7rem;
        }
    }

    .how-section-copy {
        color: rgba(246,239,227,.72);
        max-width: 760px;
        line-height: 1.6;
    }

    .how-badge {
        display: inline-block;
        background: rgba(201,164,92,.14);
        color: var(--how-gold);
        border: 1px solid rgba(201,164,92,.35);
        border-radius: 999px;
        padding: .25rem .7rem;
        font-size: .8rem;
        font-weight: 800;
        margin: .15rem .15rem .15rem 0;
    }

    .how-status {
        display: inline-block;
        border-radius: 999px;
        padding: .28rem .72rem;
        margin: .18rem .2rem .18rem 0;
        font-size: .82rem;
        font-weight: 900;
        letter-spacing: 0;
        border: 1px solid rgba(246,239,227,.26);
    }

    .how-status-success {
        background: rgba(41,142,74,.22);
        border-color: rgba(86,205,128,.7);
        color: #8ff0af;
    }

    .how-status-danger {
        background: rgba(154,42,42,.24);
        border-color: rgba(245,104,104,.72);
        color: #ffb1a8;
    }

    .how-status-warning {
        background: rgba(201,164,92,.2);
        border-color: rgba(241,202,112,.72);
        color: #f7d782;
    }

    .how-status-neutral {
        background: rgba(246,239,227,.1);
        border-color: rgba(246,239,227,.35);
        color: rgba(246,239,227,.9);
    }

    .how-status-admin {
        background: rgba(80,143,214,.2);
        border-color: rgba(123,184,255,.72);
        color: #a8d4ff;
    }

    .how-callout {
        border-left: 4px solid var(--how-gold);
        background: rgba(251,247,239,.06);
        padding: 18px 20px;
        border-radius: 16px;
        color: rgba(246,239,227,.9);
        margin: 14px 0;
    }

    .how-footer-note {
        color: rgba(246,239,227,.58);
        font-size: .88rem;
        margin-top: 8px;
    }

    hr {
        border-color: rgba(201,164,92,.2) !important;
    }

    /* ---------- V23.1 Form visibility fix ---------- */
    div[data-baseweb="input"],
    div[data-baseweb="textarea"],
    div[data-baseweb="select"] {
        background: rgba(251,247,239,.96) !important;
        border: 1px solid rgba(201,164,92,.55) !important;
        border-radius: 12px !important;
        box-shadow: none !important;
    }

    input,
    textarea,
    div[data-baseweb="input"] input,
    div[data-baseweb="textarea"] textarea {
        color: #111111 !important;
        caret-color: #111111 !important;
        background: rgba(251,247,239,.98) !important;
        padding-left: 0.85rem !important;
        padding-right: 0.85rem !important;
        text-indent: 0 !important;
        margin-left: 0 !important;
        font-weight: 650 !important;
        letter-spacing: 0 !important;
    }

    textarea {
        padding-top: 0.75rem !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: rgba(17,17,17,.55) !important;
        opacity: 1 !important;
    }

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div {
        color: #111111 !important;
    }

    label,
    [data-testid="stWidgetLabel"] p {
        color: rgba(246,239,227,.95) !important;
        font-weight: 800 !important;
    }

    .stNumberInput input {
        color: #111111 !important;
        caret-color: #111111 !important;
        padding-left: 0.85rem !important;
        text-indent: 0 !important;
    }

    /* ---------- V25.43.23 groove divider + card/button refinement ---------- */
    .how-divider {
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 30px 0;
    }

    .how-divider-line {
        flex: 1;
        height: 1px;
        background-image: repeating-linear-gradient(90deg, rgba(201,164,92,.4) 0 4px, transparent 4px 9px);
    }

    .how-divider-dot {
        flex: none;
        width: 7px;
        height: 7px;
        border-radius: 50%;
        border: 1px solid var(--how-gold);
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        position: relative;
        border-radius: 16px !important;
        box-shadow: 0 14px 34px rgba(0,0,0,.22) !important;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]::before {
        content: '';
        position: absolute;
        left: 16px;
        right: 16px;
        top: 0;
        height: 2px;
        background: linear-gradient(90deg, var(--how-gold), var(--how-oxblood-bright));
        opacity: .55;
        border-radius: 0 0 3px 3px;
    }

    .stButton > button,
    .stFormSubmitButton > button,
    .stDownloadButton > button,
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button,
    div[data-testid="stDownloadButton"] > button,
    a[data-testid="stLinkButton"] {
        box-shadow: 0 6px 16px rgba(0,0,0,.22) !important;
    }

    </style>
    """, unsafe_allow_html=True)

def groove_divider():
    st.markdown('<div class="how-divider"><span class="how-divider-line"></span><span class="how-divider-dot"></span><span class="how-divider-line"></span></div>', unsafe_allow_html=True)

def section_header(title, subtitle='', kicker='House Of Wax'):
    st.markdown(f"""
    <div class="how-section">
        <div class="how-kicker">{kicker}</div>
        <div class="how-section-title">{title}</div>
        <div class="how-section-copy">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def brand_badges(labels):
    badges_html=''.join([f'<span class="how-badge">{html.escape(safe(label))}</span>' for label in labels])
    st.markdown(badges_html, unsafe_allow_html=True)


# ---------- Data helpers ----------
def get_buyer(i):
    if hosted_enabled():
        r=hosted_select('buyers',{'id':int(i)},limit=1)
    else:
        r=df('SELECT * FROM buyers WHERE id=?',(int(i),))
    return None if r.empty else r.iloc[0]
def get_seller(i):
    if hosted_enabled():
        r=hosted_select('sellers',{'id':int(i)},limit=1)
    else:
        r=df('SELECT * FROM sellers WHERE id=?',(int(i),))
    return None if r.empty else r.iloc[0]
def ensure_buyer():
    b=table('buyers')
    if not b.empty: return int(b.iloc[0]['id'])
    data={'name':'Demo Buyer','email':'buyer@test.com','phone':'1234567890','city':'Charlotte','state':'NC','bio':'Demo buyer for testing.','status':'Trusted Buyer','rating':100,'completed_purchases':0,'unpaid_orders':0,'disputes':0,'strikes':0,'created_at':now()}
    core_insert('buyers',data,'''INSERT INTO buyers(name,email,phone,city,state,bio,status,rating,completed_purchases,unpaid_orders,disputes,strikes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['name','email','phone','city','state','bio','status','rating','completed_purchases','unpaid_orders','disputes','strikes','created_at']))
    return int(table('buyers').iloc[0]['id'])
def ensure_seller():
    s=table('sellers')
    if not s.empty: return int(s.iloc[0]['id'])
    data={'store_name':'Demo Wax Seller','owner_name':'Demo Owner','email':'seller@test.com','phone':'1234567890','city':'Charlotte','state':'NC','website':'https://example.com','instagram':'@demowax','store_bio':'A demo seller for testing.','seller_story':'We collect records, culture goods, vintage music pieces, and community stories.','specialties':'Soul, jazz, hip-hop, Carolina music, vintage tees','logo_url':'','banner_url':'','status':'Approved Seller','seller_level':'Verified Seller','rating':100,'completed_sales':12,'disputes':0,'strikes':0,'auction_override':'Yes','access_code':'','created_at':now()}
    keys=['store_name','owner_name','email','phone','city','state','website','instagram','store_bio','seller_story','specialties','logo_url','banner_url','status','seller_level','rating','completed_sales','disputes','strikes','auction_override','access_code','created_at']
    core_insert('sellers',data,'''INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in keys))
    return int(table('sellers').iloc[0]['id'])

def ensure_house_of_wax_official():
    rows=df("SELECT * FROM sellers WHERE lower(store_name)=lower('House Of Wax Official') OR lower(email)=lower('official@houseofwax.com')")
    if not rows.empty:
        sid=int(rows.iloc[0]['id'])
    else:
        run("""INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ('House Of Wax Official','House Of Wax','official@houseofwax.com','','Charlotte','NC','','@houseofwax','The official House Of Wax seller account for branded merchandise, official drops, curated goods, and platform items.','House Of Wax is the platform voice for music culture, collecting education, marketplace trust, and official brand drops.','House Of Wax branded merchandise, slipmats, culture goods, official drops, curated records','','','Approved Seller','Platform Official',100,0,0,0,'Yes','',now()))
        sid=int(df("SELECT id FROM sellers WHERE lower(email)=lower('official@houseofwax.com')").iloc[0]['id'])
    badge=df("SELECT id FROM seller_badges WHERE seller_id=? AND badge_name='Official House Of Wax'",(sid,))
    if badge.empty:
        run("INSERT INTO seller_badges(seller_id,badge_name,badge_type,active,created_at) VALUES(?,?,?,'Yes',?)",(sid,'Official House Of Wax','Platform',now()))
    existing=df("SELECT id FROM products WHERE seller_id=? AND title='House Of Wax Logo Tee'",(sid,))
    if existing.empty:
        run("""INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid,'HOW-TEE-001','','','','House Of Wax Merch','House Of Wax','House Of Wax Logo Tee','Apparel','House Of Wax','','Merch','New','New','Official sample item for testing.','Official House Of Wax branded tee sample. Replace with real photos and inventory when ready.',28.00,25,5.00,'','','','','Live','Fixed Price',now(),now()))
    return sid


def ensure_product():
    p=table('products')
    if not p.empty: return int(p.iloc[0]['id'])
    sid=ensure_seller()
    run('''INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,'DEMO-001','602547234567','CAT-001','A1/B1','Vinyl Records','Demo Artist','Demo Album','Vinyl','Demo Label','1978','Soul','VG+','VG','Light sleeve wear. Plays strong.','Demo product with barcode metadata.',24.99,1,5.00,'','','','','Live','Fixed Price',now(),now()))
    return int(table('products').iloc[0]['id'])
def seed_all(): return ensure_buyer(), ensure_seller(), ensure_house_of_wax_official(), ensure_product()
def create_buyer(email,name='Test Buyer'):
    email=(email or 'buyer@test.com').strip().lower()
    r=hosted_select('buyers',{'email':email},limit=1) if hosted_enabled() else df('SELECT id FROM buyers WHERE lower(email)=lower(?)',(email,))
    if not r.empty: return int(r.iloc[0]['id'])
    data={'name':name,'email':email,'phone':'','city':'','state':'','bio':'','status':'Trusted Buyer','rating':100,'completed_purchases':0,'unpaid_orders':0,'disputes':0,'strikes':0,'created_at':now()}
    pid=core_insert('buyers',data,'''INSERT INTO buyers(name,email,phone,city,state,bio,status,rating,completed_purchases,unpaid_orders,disputes,strikes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['name','email','phone','city','state','bio','status','rating','completed_purchases','unpaid_orders','disputes','strikes','created_at']))
    if pid:
        return int(pid)
    reread=hosted_select('buyers',{'email':email},limit=1) if hosted_enabled() else df('SELECT id FROM buyers WHERE lower(email)=lower(?)',(email,))
    return int(reread.iloc[0]['id']) if not reread.empty else 0
def barcode_lookup(code):
    if not code: return {}
    r=hosted_select('products',{'barcode':code.strip()},order='created_at.desc',limit=1) if hosted_enabled() else df('''SELECT barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,description,price,shipping_price,image_url FROM products WHERE barcode=? ORDER BY created_at DESC LIMIT 1''',(code.strip(),))
    return {} if r.empty else r.iloc[0].to_dict()
def badges(sid):
    r=hosted_select('seller_badges',{'seller_id':int(sid),'active':'Yes'}) if hosted_enabled() else df("SELECT badge_name FROM seller_badges WHERE seller_id=? AND active='Yes'",(int(sid),))
    return '' if r.empty else ' • '.join([safe(x) for x in r['badge_name'].tolist()])
def followers(sid):
    r=hosted_select('seller_followers',{'seller_id':int(sid)},select='id') if hosted_enabled() else df('SELECT COUNT(*) c FROM seller_followers WHERE seller_id=?',(int(sid),))
    return len(r) if hosted_enabled() else (0 if r.empty else int(r.iloc[0]['c'] or 0))
def fee(total,auction=False): return round(float(total)*float(setting('auction_commission_percent' if auction else 'platform_commission_percent','9'))/100,2)

def seller_profile_completion(sid):
    s=get_seller(sid)
    if s is None:
        return 0,[]
    checks=[
        ('Seller/display name',bool(safe(s.get('store_name')))),
        ('Short bio/about section',bool(safe(s.get('store_bio')) or safe(s.get('seller_story')))),
        ('Location',bool(safe(s.get('city')) or safe(s.get('state')))),
        ('Favorite genres/categories',bool(safe(s.get('specialties')))),
        ('Contact preference',bool(safe(s.get('contact_preference')) or safe(s.get('instagram')) or safe(s.get('website')))),
    ]
    score=int(round(sum(1 for _,ok in checks if ok)/len(checks)*100))
    return score,checks

def seller_quality_listing_stats(sid):
    prods=hosted_select('products',{'seller_id':int(sid)},in_filters={'listing_status':['Live','Active','Approved','Public']}) if hosted_enabled() else df("SELECT * FROM products WHERE seller_id=? AND listing_status IN ('Live','Active','Approved','Public')",(int(sid),))
    if prods.empty:
        return 0,0,0
    scores=[]
    for _,p in prods.iterrows():
        has_seller_photo=is_local_uploaded_image(p.get('image_url'))
        score,_,_=listing_quality_assessment(p.get('category'),p.get('artist'),p.get('title'),p.get('price'),p.get('description'),p.get('media_grade'),p.get('sleeve_grade'),p.get('image_url'),has_seller_photo,'')
        scores.append(score)
    strong=sum(1 for score in scores if score>=80)
    avg=int(round(sum(scores)/len(scores))) if scores else 0
    return len(prods),strong,avg

def seller_trust_badges(sid):
    profile_score,_=seller_profile_completion(sid)
    approved_count,strong_count,avg_quality=seller_quality_listing_stats(sid)
    badges_out=[]
    if approved_count==0:
        badges_out.append('New Seller')
    if profile_score>=80:
        badges_out.append('Profile Complete')
    if approved_count>=1:
        badges_out.append('Approved Listings')
    if strong_count>=1 or avg_quality>=80:
        badges_out.append('Quality Listings')
    if approved_count>=3 and profile_score>=80 and (strong_count>=2 or avg_quality>=80):
        badges_out.append('Trusted Seller')
    manual=badges(sid)
    if manual:
        badges_out.extend([b.strip() for b in manual.split('•') if b.strip()])
    clean=[]
    for b in badges_out:
        if b not in clean:
            clean.append(b)
    return clean

def seller_trust_summary(sid):
    profile_score,checks=seller_profile_completion(sid)
    approved_count,strong_count,avg_quality=seller_quality_listing_stats(sid)
    return {
        'profile_score':profile_score,
        'checks':checks,
        'approved_count':approved_count,
        'strong_count':strong_count,
        'avg_quality':avg_quality,
        'badges':seller_trust_badges(sid)
    }

def render_seller_trust_badges(sid, context='public'):
    summary=seller_trust_summary(sid)
    labels=summary['badges'] or ['New Seller']
    brand_badges(labels)
    st.caption('House Of Wax platform indicators based on profile completeness, live listings, and listing readiness. Not outside verification.')
    if context!='public':
        st.write(f"**Profile completeness:** {summary['profile_score']}%")
        st.write(f"**Live/public listings:** {summary['approved_count']} • **Strong readiness listings:** {summary['strong_count']} • **Average readiness:** {summary['avg_quality']}/100")
        missing=[name for name,ok in summary['checks'] if not ok]
        if missing:
            st.warning('Missing profile details: '+', '.join(missing))
        else:
            st.success('Seller profile is complete.')

# ---------- UI helpers ----------
def header():
    apply_brand_style()
    st.title('🎧 House Of Wax')
    st.caption(setting('site_tagline'))
    brand_badges(['Marketplace', 'Knowledge Hub', 'Culture Education', 'Collect Smarter'])
    if is_admin_unlocked():
        st.caption(f'Running {APP_VERSION}')
        st.info('Working prototype demo: marketplace, seller tools, moderation center, inquiries, purchase requests, profiles, badges, and database status are available for walkthroughs.')
        st.info(setting('announcement'))
def marketplace_context(label='House Of Wax Marketplace'):
    st.caption(label)
def admin_context(label='House Of Wax Admin'):
    st.caption(label)
    st.warning('This area is for platform management, seller approval, moderation, reports, diagnostics, and testing.')
def buyer_pick(key,label='Buyer account',preferred_id=None):
    if not is_admin_unlocked():
        bid=ensure_linked_buyer_profile()
        if bid:
            st.caption('Using the buyer profile linked to your signed-in account.')
            return bid
        st.warning('Sign in as a Buyer to use buyer account features.')
        return 0
    st.caption('Admin/testing profile picker. Normal users cannot switch buyer profiles.')
    if table('buyers').empty: ensure_buyer()
    buyers=table('buyers').sort_values('id',ascending=False) if 'id' in table('buyers').columns else table('buyers')
    opts=[f"{int(r['id'])} | {safe(r['name'])} | {safe(r['email'])} | {safe(r['status'])}" for _,r in buyers.iterrows()]
    ids=[int(r['id']) for _,r in buyers.iterrows()]
    try:
        preferred=int(preferred_id) if preferred_id else 0
    except Exception:
        preferred=0
    index=ids.index(preferred) if preferred in ids else 0
    return int(st.selectbox(label,opts,index=index,key=key).split('|')[0].strip())
def seller_pick(key,label='Seller account',preferred_id=None):
    if not is_admin_unlocked():
        sid=linked_seller_id()
        if sid:
            st.caption('Using the seller store linked to your signed-in account.')
            return sid
        st.warning('Sign in as a Seller to use seller tools.')
        return 0
    st.caption('Admin/testing profile picker. Normal users cannot switch seller stores.')
    if table('sellers').empty: ensure_seller()
    sellers=table('sellers').sort_values('id',ascending=False) if 'id' in table('sellers').columns else table('sellers')
    opts=[f"{int(r['id'])} | {safe(r['store_name'])} | {safe(r['email'])} | {safe(r['status'])}" for _,r in sellers.iterrows()]
    ids=[int(r['id']) for _,r in sellers.iterrows()]
    try:
        preferred=int(preferred_id) if preferred_id else 0
    except Exception:
        preferred=0
    index=ids.index(preferred) if preferred in ids else 0
    return int(st.selectbox(label,opts,index=index,key=key).split('|')[0].strip())
def apply_to_become_seller(store_name='', owner_name=''):
    if not is_authenticated():
        AUTH_STATUS['last_link_error']='Sign in before applying to become a seller.'
        return 0
    user=current_app_user()
    display=safe(owner_name) or safe(user.get('display_name')) or auth_user_email().split('@')[0]
    bid=int(user.get('buyer_id') or 0) or ensure_linked_buyer_profile(display)
    sid=int(user.get('seller_id') or 0)
    if not sid:
        sid=create_or_get_seller_for_auth(auth_user_email(),safe(store_name) or display)
    if sid:
        seller=get_seller(sid)
        current_status=normalize_seller_status(seller.get('status') if seller is not None else 'Pending Seller Approval')
        if current_status not in ['Approved Seller','Suspended Seller']:
            current_status='Pending Seller Approval'
            core_update('sellers',{'status':current_status},{'id':sid},"UPDATE sellers SET status=? WHERE id=?",(current_status,sid))
        upsert_app_user(auth_user_id(),auth_user_email(),display,'Buyer/Seller',bid,sid,'',safe(user.get('admin_access'),'No'),current_status,account_status(user))
        st.session_state['seller_tool_seller_id']=sid
        return sid
    AUTH_STATUS['last_link_error']='Seller application could not be created or linked.'
    return 0

def account_page():
    header()
    marketplace_context('House Of Wax Marketplace -> Account')
    st.header('My Account')
    st.write('You can buy and sell using the same House Of Wax account. Selling requires approval.')
    if is_authenticated():
        reconcile_authenticated_profile()
        user=current_app_user()
        buyer_id=ensure_linked_buyer_profile()
        seller_id=linked_seller_id()
        seller=get_seller(seller_id) if seller_id else None
        seller_status=seller_application_status(user)
        st.success('Signed in as '+auth_user_email())
        c1,c2,c3=st.columns(3)
        c1.metric('Account',safe(user.get('display_name')) or auth_user_email().split('@')[0])
        c2.metric('Buying','Ready to go' if buyer_id else 'One click away')
        c3.metric('Selling',seller_status)
        st.caption('One account per person. Buyer access stays active even after you apply to sell.')
        action=pending_action()
        if action:
            st.info('Saved action waiting: '+safe(action.get('action_type')))
            if st.button('Back to Item',key='account_back_to_pending_item',width='stretch'):
                restore_pending_action()
                st.rerun()
        if st.button('Go to Marketplace',key='account_go_to_marketplace',width='stretch'):
            request_marketplace_navigation('Search Music',clear_product=True,clear_seller=True)
            st.rerun()
        tabs=st.tabs(['Account','Buying','Selling','Sign Out'])
        with tabs[0]:
            st.subheader('Account')
            st.write('**Name:** '+(safe(user.get('display_name')) or 'Not set'))
            st.write('**Email:** '+auth_user_email())
            st.write('**Account status:** '+account_status(user))
            if is_admin_user(user):
                st.write('**Admin access:** Yes')
            st.caption('Tokens and secrets are never displayed.')
            if is_admin_unlocked():
                with st.expander('Diagnostics',expanded=False):
                    auth_diagnostics_section()
        with tabs[1]:
            st.subheader('Buying')
            if buyer_id:
                buyer=get_buyer(buyer_id)
                st.success('Buyer profile linked.')
                if buyer is not None:
                    st.write(f"**Buyer profile:** {safe(buyer.get('name'))} | {safe(buyer.get('email'))}")
                buyer_workspace_tabs(buyer_id)
            else:
                st.warning('Buyer profile is missing. The app will try to repair it now.')
                if st.button('Repair buyer profile link',key='account_repair_buyer_profile'):
                    if ensure_linked_buyer_profile():
                        st.success('Buyer profile linked.')
                        st.rerun()
                    else:
                        st.error('Buyer profile could not be linked. Check Auth Diagnostics.')
        with tabs[2]:
            st.subheader('Selling')
            st.info('Apply once from this same account. Do not create a second account to sell.')
            if not seller_id:
                with st.form('apply_to_become_seller_form'):
                    store_name=st.text_input('Store/display name',value=safe(user.get('display_name')) or auth_user_email().split('@')[0],key='apply_seller_store_name')
                    owner_name=st.text_input('Your name',value=safe(user.get('display_name')),key='apply_seller_owner_name')
                    sub=st.form_submit_button('Apply to Become a Seller')
                if sub:
                    sid=apply_to_become_seller(store_name,owner_name)
                    if sid:
                        st.success('Seller application created. You can complete your store and save drafts while House Of Wax reviews it.')
                        st.rerun()
                    else:
                        st.error('Seller application could not be saved. '+safe(AUTH_STATUS.get('last_link_error')))
            else:
                st.write('**Seller application status:** '+seller_status)
                if seller is not None:
                    st.write(f"**Store:** {safe(seller.get('store_name'))} | {safe(seller.get('email'))}")
                if seller_status=='Approved Seller':
                    st.success('Seller tools are unlocked. Publishing still requires accepted seller rules.')
                elif seller_status=='Suspended Seller':
                    st.error('Seller privileges are suspended. Buyer access remains available.')
                else:
                    st.warning('Seller application is pending. You can complete your store profile and save draft inventory, but cannot publish live until approved.')
                if st.button('Open Seller Dashboard',key='account_open_seller_dashboard',width='stretch'):
                    request_marketplace_navigation('Seller Dashboard')
                    st.rerun()
        with tabs[3]:
            if st.button('Sign Out',key='account_sign_out_button'):
                auth_sign_out()
                st.success('Signed out.')
                st.rerun()
        return
    tabs=st.tabs(['Sign In','Create Account','Account Status'])
    with tabs[0]:
        with st.form('signin_form'):
            email=st.text_input('Email',key='signin_email')
            password=st.text_input('Password',type='password',key='signin_password')
            sub=st.form_submit_button('Sign In')
        if sub:
            ok,msg=auth_sign_in(email,password)
            if ok:
                st.success(msg)
                restore_pending_action()
                st.rerun()
            else:
                st.error(msg)
        st.caption('Use the same account to buy and apply to sell.')
        with st.expander('Forgot password?'):
            if not hosted_enabled():
                st.info('Password reset requires Supabase Hosted to be configured.')
            else:
                reset_email=st.text_input('Email',key='forgot_password_email')
                if st.button('Send reset link',key='forgot_password_submit'):
                    ok,msg=request_password_reset_email(reset_email)
                    (st.success if ok else st.error)(msg)
    with tabs[1]:
        st.info('Create one House Of Wax account. Every registered account can buy. Apply to sell later from My Account.')
        with st.form('create_account_form'):
            name=st.text_input('Display name',key='create_name')
            email=st.text_input('Email',key='create_email')
            password=st.text_input('Password',type='password',key='create_password')
            confirm=st.text_input('Confirm password',type='password',key='create_confirm')
            sub=st.form_submit_button('Create House Of Wax Account')
        if sub:
            ok,msg=auth_create_account(name,email,password,confirm,'Buyer')
            if ok:
                st.success(msg)
                restore_pending_action()
                st.rerun()
            else:
                st.error(msg)
        st.caption('Public sign-up cannot create Admin accounts. Admin access must be granted by secure configuration or database field.')
    with tabs[2]:
        st.info('Not signed in.')
        st.write('Supabase Auth configured: '+('Yes' if hosted_enabled() else 'No'))
        st.caption('Local fallback login is for prototype testing only when Supabase Auth is not configured.')

def auth_diagnostics_section():
    st.markdown('### Auth Diagnostics')
    user=current_app_user()
    action=pending_action()
    buyer_id=int(user.get('buyer_id') or 0) if user else 0
    seller_id=int(user.get('seller_id') or 0) if user else 0
    buyer_found=get_buyer(buyer_id) is not None if buyer_id else False
    seller_found=get_seller(seller_id) is not None if seller_id else False
    rows=[
        ('Supabase Auth configured','Yes' if hosted_enabled() else 'No'),
        ('Current session detected','Yes' if is_authenticated() else 'No'),
        ('Current user ID',mask_identifier(auth_user_id())),
        ('Current user email',auth_user_email() if (is_authenticated() and (is_admin_unlocked() or auth_user_email())) else 'None'),
        ('Linked app_users row','Yes' if bool(user) else 'No'),
        ('Linked buyer ID',safe(buyer_id)),
        ('Buyer row found','Yes' if buyer_found else 'No'),
        ('Linked seller ID',safe(seller_id)),
        ('Seller row found','Yes' if seller_found else 'No'),
        ('Seller application status',seller_application_status(user)),
        ('Account status',account_status(user)),
        ('Effective role',effective_account_type()),
        ('Admin access source',admin_access_source()),
        ('Pending action',safe(action.get('action_type'),'None')),
        ('Pending product ID',safe(action.get('product_id'),'0')),
        ('Current page/route',safe(st.session_state.get('marketplace_navigation') or st.session_state.get('admin_navigation'),'Unknown')),
        ('Last hosted request auth mode',safe(SUPABASE_STATUS.get('last_auth_mode'),'None')),
        ('Last auth error',safe(AUTH_STATUS.get('last_error'),'None')[:240]),
        ('Last buyer profile save error',safe(AUTH_STATUS.get('last_buyer_save_error'),'None')[:240]),
        ('Last seller profile save error',safe(AUTH_STATUS.get('last_seller_save_error'),'None')[:240]),
        ('Last link error',safe(AUTH_STATUS.get('last_link_error'),'None')[:240]),
    ]
    st.dataframe(pd.DataFrame(rows,columns=['Check','Status']),width='stretch')
    st.caption('No password, access token, refresh token, anon key, or service key is displayed.')

def claim_existing_profile_section():
    st.markdown('### Claim existing prototype profile')
    if not is_authenticated():
        st.info('Sign in first, then use this controlled claim helper if you have an existing prototype buyer or seller profile.')
        return
    user=current_app_user()
    email=auth_user_email()
    st.caption('Profiles are matched only by your signed-in email. If multiple records match, ask Admin to resolve it.')
    buyer_matches=table('buyers')
    buyer_matches=buyer_matches[buyer_matches['email'].fillna('').str.lower()==email] if not buyer_matches.empty and 'email' in buyer_matches.columns else pd.DataFrame()
    seller_matches=table('sellers')
    seller_matches=seller_matches[seller_matches['email'].fillna('').str.lower()==email] if not seller_matches.empty and 'email' in seller_matches.columns else pd.DataFrame()
    c1,c2=st.columns(2)
    with c1:
        st.write('Buyer profile matches: '+str(len(buyer_matches)))
        if len(buyer_matches)==1 and st.button('Claim buyer profile',key='claim_buyer_profile'):
            upsert_app_user(auth_user_id(),email,safe(user.get('display_name')),safe(user.get('account_type'),'Buyer'),int(buyer_matches.iloc[0]['id']),int(user.get('seller_id') or 0),'',safe(user.get('admin_access'),'No'))
            st.success('Buyer profile linked.')
            st.rerun()
    with c2:
        st.write('Seller profile matches: '+str(len(seller_matches)))
        if len(seller_matches)==1 and st.button('Claim seller profile',key='claim_seller_profile'):
            upsert_app_user(auth_user_id(),email,safe(user.get('display_name')),safe(user.get('account_type'),'Seller'),int(user.get('buyer_id') or 0),int(seller_matches.iloc[0]['id']),'',safe(user.get('admin_access'),'No'))
            st.success('Seller profile linked.')
            st.rerun()
    if len(buyer_matches)>1 or len(seller_matches)>1:
        st.warning('Multiple matching profiles found. Admin must resolve duplicates before linking.')

def is_public_listing(p):
    return safe(p.get('listing_status')) in public_listing_query_statuses()

def is_available_listing(p):
    return safe(p.get('listing_status')) in PUBLIC_LISTING_STATUSES

def listing_availability_label(p):
    status=safe(p.get('listing_status'))
    if status=='Sold':
        return 'Sold'
    if status=='Hidden':
        return 'Hidden'
    if status in ['Under Review','Removed by House Of Wax']:
        return status
    if status in ['Pending Pickup/Payment','Pending']:
        return 'Pending'
    return 'Available'

def is_local_uploaded_image(path):
    s=safe(path)
    return bool(s) and ('house_of_wax_uploads' in s or s.startswith('uploads/') or s.startswith('listing_photos/'))

def listing_gallery_images(pid):
    try:
        if hosted_enabled():
            return hosted_select('product_gallery',{'product_id':int(pid)},order='id.asc')
        return df('SELECT * FROM product_gallery WHERE product_id=? ORDER BY id ASC',(int(pid),))
    except Exception:
        return pd.DataFrame()

def listing_primary_image(p):
    pid=int(p.get('id') or 0)
    gallery=listing_gallery_images(pid) if pid else pd.DataFrame()
    if not gallery.empty:
        main=gallery[gallery['caption'].fillna('').str.lower().str.contains('main listing photo',na=False)]
        local=gallery[gallery['image_url'].fillna('').apply(is_local_uploaded_image)]
        if not main.empty:
            return safe(main.iloc[0]['image_url'])
        if safe(p.get('image_url')) and is_local_uploaded_image(p.get('image_url')):
            return safe(p.get('image_url'))
        if not local.empty:
            return safe(local.iloc[0]['image_url'])
    if safe(p.get('image_url')):
        return safe(p.get('image_url'))
    if not gallery.empty:
        return safe(gallery.iloc[0]['image_url'])
    return ''

def has_listing_photos(pid):
    gallery=listing_gallery_images(pid)
    return not gallery.empty and gallery['image_url'].fillna('').apply(is_local_uploaded_image).any()

def enrich_activity_rows(records):
    if records.empty:
        return records
    out=records.copy()
    product_cache={}
    seller_cache={}
    for idx,row in out.iterrows():
        pid=int(row.get('product_id') or 0)
        sid=int(row.get('seller_id') or 0)
        if pid and pid not in product_cache:
            product_cache[pid]=hosted_select('products',{'id':pid},limit=1).iloc[0].to_dict() if hosted_enabled() and not hosted_select('products',{'id':pid},limit=1).empty else {}
        if sid and sid not in seller_cache:
            seller_cache[sid]=get_seller(sid)
        product=product_cache.get(pid,{})
        seller=seller_cache.get(sid)
        if product:
            for col in ['artist','title','category','listing_status','price']:
                out.at[idx,col]=safe(product.get(col))
        if seller is not None:
            out.at[idx,'store_name']=safe(seller.get('store_name'))
    return out

def render_listing_photo_gallery(pid, primary_image='', context='public'):
    gallery=listing_gallery_images(pid)
    if gallery.empty:
        if primary_image and not is_local_uploaded_image(primary_image):
            st.caption('Image source: search/database or supporting product image.')
        return
    st.subheader('Listing photos' if context!='admin' else 'Seller-uploaded photos / gallery')
    cols=st.columns(3)
    for i,(_,g) in enumerate(gallery.iterrows()):
        with cols[i%3]:
            if safe(g.get('image_url')):
                safe_image(safe(g.get('image_url')),caption=safe(g.get('caption'),'Supporting photo'),width='stretch',fallback_text='Photo unavailable.')

def render_buyer_inquiry_form(p, seller, key_prefix):
    status=safe(p.get('listing_status'))
    if status not in PUBLIC_LISTING_STATUSES:
        return
    st.info('House Of Wax keeps seller contact details controlled. The seller can respond based on their contact preference.')
    if not is_authenticated():
        set_pending_action('Ask Seller',p)
        st.warning('Sign in to ask the seller. We will bring you back to this item.')
        if st.button('Sign in or create Buyer account',key=f'inquiry_signin_{key_prefix}',width='stretch'):
            request_marketplace_navigation('My Account')
            st.rerun()
        return
    known_buyers=table('buyers')
    buyer_id=ensure_linked_buyer_profile()
    buyer_name=''
    buyer_contact=''
    if buyer_id:
        buyer=get_buyer(buyer_id)
        if buyer is not None:
            buyer_name=safe(buyer.get('name'))
            buyer_contact=safe(buyer.get('email')) or safe(buyer.get('phone'))
    if not buyer_id:
        st.warning('Complete your buyer profile to ask this seller.')
        with st.form(f'complete_buyer_for_inquiry_{key_prefix}'):
            profile_name=st.text_input('Name',value=safe(current_app_user().get('display_name')) or auth_user_email().split('@')[0],key=f'complete_buyer_name_inquiry_{key_prefix}')
            profile_phone=st.text_input('Phone optional',key=f'complete_buyer_phone_inquiry_{key_prefix}')
            sub_profile=st.form_submit_button('Save buyer profile and continue')
        if sub_profile:
            buyer_id=ensure_linked_buyer_profile(profile_name)
            if buyer_id:
                core_update('buyers',{'name':profile_name,'phone':profile_phone},{'id':buyer_id},'UPDATE buyers SET name=?,phone=? WHERE id=?',(profile_name,profile_phone,buyer_id))
                restore_pending_action()
                st.success('Buyer profile saved. You can ask the seller now.')
                st.rerun()
            else:
                st.error('Buyer profile could not be saved. Check Auth Diagnostics for the exact error.')
        return
    elif is_admin_unlocked() and not known_buyers.empty:
        use_buyer=st.checkbox('Use an existing buyer profile',value=False,key=f'inquiry_existing_buyer_{key_prefix}')
        if use_buyer:
            buyer_id=buyer_pick(f'inquiry_buyer_{key_prefix}')
            buyer=get_buyer(buyer_id)
            if buyer is not None:
                buyer_name=safe(buyer.get('name'))
                buyer_contact=safe(buyer.get('email')) or safe(buyer.get('phone'))
    with st.form(f'inquiry_form_{key_prefix}'):
        name=st.text_input('Buyer name',value=buyer_name,key=f'inquiry_name_{key_prefix}')
        contact=st.text_input('Buyer email or phone',value=buyer_contact,key=f'inquiry_contact_{key_prefix}')
        method=st.selectbox('Preferred contact method',['Email','Phone','Text message','House Of Wax message'],key=f'inquiry_method_{key_prefix}')
        message=st.text_area('Message/question',key=f'inquiry_message_{key_prefix}',placeholder='Ask about condition, shipping, pickup, photos, or anything you need before buying.')
        sub=st.form_submit_button('Send inquiry')
    if sub:
        if not safe(name) or not safe(contact) or not safe(message):
            st.warning('Add your name, contact info, and question before sending.')
        else:
            data={'product_id':int(p['id']),'seller_id':int(p['seller_id']),'buyer_id':int(buyer_id or 0),'buyer_name':name,'buyer_contact':contact,'preferred_contact_method':method,'message':message,'status':'New','created_at':now(),'updated_at':now()}
            new_id=core_insert('listing_inquiries',data,'''INSERT INTO listing_inquiries(product_id,seller_id,buyer_id,buyer_name,buyer_contact,preferred_contact_method,message,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['product_id','seller_id','buyer_id','buyer_name','buyer_contact','preferred_contact_method','message','status','created_at','updated_at']))
            if new_id or not hosted_enabled():
                clear_pending_action()
                st.success('Inquiry sent. The seller can view it inside Seller Tools.')
            else:
                st.error('Inquiry could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

def render_purchase_request_form(p, key_prefix):
    if not is_available_listing(p):
        st.info('Purchase requests are available only while a listing is available.')
        return
    st.info(f"Buying at the listed price of {money(p['price'])}. Checkout is not live yet, so this sends a purchase request so the seller can confirm availability, pickup/shipping, and next steps. Want to propose a different price instead? Use Make an Offer.")
    if not is_authenticated():
        set_pending_action('Request to Buy',p)
        st.warning('Sign in to request this item. We will bring you back here.')
        if st.button('Sign in or create Buyer account',key=f'purchase_signin_{key_prefix}',width='stretch'):
            request_marketplace_navigation('My Account')
            st.rerun()
        return
    known_buyers=table('buyers')
    buyer_id=ensure_linked_buyer_profile()
    buyer_name=''
    buyer_contact=''
    if buyer_id:
        buyer=get_buyer(buyer_id)
        if buyer is not None:
            buyer_name=safe(buyer.get('name'))
            buyer_contact=safe(buyer.get('email')) or safe(buyer.get('phone'))
    if not buyer_id:
        st.warning('Complete your buyer profile to request this item.')
        with st.form(f'complete_buyer_for_purchase_{key_prefix}'):
            profile_name=st.text_input('Name',value=safe(current_app_user().get('display_name')) or auth_user_email().split('@')[0],key=f'complete_buyer_name_purchase_{key_prefix}')
            profile_phone=st.text_input('Phone optional',key=f'complete_buyer_phone_purchase_{key_prefix}')
            sub_profile=st.form_submit_button('Save buyer profile and continue')
        if sub_profile:
            buyer_id=ensure_linked_buyer_profile(profile_name)
            if buyer_id:
                core_update('buyers',{'name':profile_name,'phone':profile_phone},{'id':buyer_id},'UPDATE buyers SET name=?,phone=? WHERE id=?',(profile_name,profile_phone,buyer_id))
                restore_pending_action()
                st.success('Buyer profile saved. You can request this item now.')
                st.rerun()
            else:
                st.error('Buyer profile could not be saved. Check Auth Diagnostics for the exact error.')
        return
    elif is_admin_unlocked() and not known_buyers.empty:
        use_buyer=st.checkbox('Use an existing buyer profile',value=False,key=f'purchase_existing_buyer_{key_prefix}')
        if use_buyer:
            buyer_id=buyer_pick(f'purchase_buyer_{key_prefix}')
            buyer=get_buyer(buyer_id)
            if buyer is not None:
                buyer_name=safe(buyer.get('name'))
                buyer_contact=safe(buyer.get('email')) or safe(buyer.get('phone'))
    with st.form(f'purchase_request_form_{key_prefix}'):
        name=st.text_input('Buyer name',value=buyer_name,key=f'purchase_name_{key_prefix}')
        contact=st.text_input('Buyer email or phone',value=buyer_contact,key=f'purchase_contact_{key_prefix}')
        method=st.selectbox('Preferred contact method',['Email','Phone','Text message','House Of Wax message'],key=f'purchase_method_{key_prefix}')
        fulfillment=st.selectbox('Pickup or shipping preference',['Shipping','Local pickup','Either / discuss with seller'],key=f'purchase_fulfillment_{key_prefix}')
        message=st.text_area('Buyer message',key=f'purchase_message_{key_prefix}',placeholder='Confirm availability, shipping/pickup details, or anything the seller should know.')
        sub=st.form_submit_button('Send purchase request')
    if sub:
        if not safe(name) or not safe(contact):
            st.warning('Add your name and contact info before sending a purchase request.')
        else:
            data={'product_id':int(p['id']),'seller_id':int(p['seller_id']),'buyer_id':int(buyer_id or 0),'buyer_name':name,'buyer_contact':contact,'preferred_contact_method':method,'fulfillment_preference':fulfillment,'offer_price':0.0,'buyer_message':message,'status':'New','created_at':now(),'updated_at':now()}
            new_id=core_insert('purchase_requests',data,'''INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,preferred_contact_method,fulfillment_preference,offer_price,buyer_message,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['product_id','seller_id','buyer_id','buyer_name','buyer_contact','preferred_contact_method','fulfillment_preference','offer_price','buyer_message','status','created_at','updated_at']))
            if new_id or not hosted_enabled():
                clear_pending_action()
                st.success('Purchase request sent. The seller can review it inside Seller Tools.')
            else:
                st.error('Purchase request could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

def render_offer_form(p, key_prefix):
    if not is_available_listing(p):
        st.info('Offers are available only while a listing is available.')
        return
    st.info(f"Listed at {money(p['price'])}. Propose a price below and the seller can accept, counter, or decline.")
    if not is_authenticated():
        set_pending_action('Make Offer',p)
        st.warning('Sign in to make an offer. We will bring you back here.')
        if st.button('Sign in or create Buyer account',key=f'offer_signin_{key_prefix}',width='stretch'):
            request_marketplace_navigation('My Account')
            st.rerun()
        return
    buyer_id=ensure_linked_buyer_profile()
    buyer_name=''
    buyer_contact=''
    if buyer_id:
        buyer=get_buyer(buyer_id)
        if buyer is not None:
            buyer_name=safe(buyer.get('name'))
            buyer_contact=safe(buyer.get('email')) or safe(buyer.get('phone'))
    if not buyer_id:
        st.warning('Complete your buyer profile to make an offer.')
        with st.form(f'complete_buyer_for_offer_{key_prefix}'):
            profile_name=st.text_input('Name',value=safe(current_app_user().get('display_name')) or auth_user_email().split('@')[0],key=f'complete_buyer_name_offer_{key_prefix}')
            profile_phone=st.text_input('Phone optional',key=f'complete_buyer_phone_offer_{key_prefix}')
            sub_profile=st.form_submit_button('Save buyer profile and continue')
        if sub_profile:
            buyer_id=ensure_linked_buyer_profile(profile_name)
            if buyer_id:
                core_update('buyers',{'name':profile_name,'phone':profile_phone},{'id':buyer_id},'UPDATE buyers SET name=?,phone=? WHERE id=?',(profile_name,profile_phone,buyer_id))
                restore_pending_action()
                st.success('Buyer profile saved. You can make an offer now.')
                st.rerun()
            else:
                st.error('Buyer profile could not be saved. Check Auth Diagnostics for the exact error.')
        return
    with st.form(f'offer_form_{key_prefix}'):
        name=st.text_input('Buyer name',value=buyer_name,key=f'offer_name_{key_prefix}')
        contact=st.text_input('Buyer email or phone',value=buyer_contact,key=f'offer_contact_{key_prefix}')
        offer=st.number_input('Your offer price',min_value=0.01,step=1.0,value=max(0.01,float(p['price'] or 0)*0.85),key=f'offer_amount_{key_prefix}')
        message=st.text_area('Message to seller - optional',key=f'offer_message_{key_prefix}',placeholder='Explain your offer if you want.')
        sub=st.form_submit_button('Send offer')
    if sub:
        if not safe(name) or not safe(contact):
            st.warning('Add your name and contact info before sending an offer.')
        elif not offer or float(offer)<=0:
            st.warning('Enter an offer amount greater than $0.')
        else:
            data={'product_id':int(p['id']),'seller_id':int(p['seller_id']),'buyer_id':int(buyer_id or 0),'buyer_name':name,'buyer_contact':contact,'preferred_contact_method':'House Of Wax message','fulfillment_preference':'Discuss with seller','offer_price':float(offer),'buyer_message':message,'status':'Offer Pending','created_at':now(),'updated_at':now()}
            new_id=core_insert('purchase_requests',data,'''INSERT INTO purchase_requests(product_id,seller_id,buyer_id,buyer_name,buyer_contact,preferred_contact_method,fulfillment_preference,offer_price,buyer_message,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['product_id','seller_id','buyer_id','buyer_name','buyer_contact','preferred_contact_method','fulfillment_preference','offer_price','buyer_message','status','created_at','updated_at']))
            if new_id or not hosted_enabled():
                clear_pending_action()
                st.success('Offer sent. The seller can accept, counter, or decline it inside Seller Tools.')
            else:
                st.error('Offer could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

REPORT_REASONS=['Misleading description','Wrong condition','Counterfeit / bootleg concern','Stolen item concern','Offensive or prohibited content','Seller behavior issue','Other']

def report_listing_form(listing=None, seller=None, key_prefix='report'):
    listing_id=int(listing.get('id') or 0) if listing is not None else 0
    seller_id=int((seller.get('id') if seller is not None else 0) or (listing.get('seller_id') if listing is not None else 0) or 0)
    with st.form(f'report_form_{key_prefix}_{listing_id}_{seller_id}'):
        reporter_name=st.text_input('Your name optional',key=f'report_name_{key_prefix}_{listing_id}_{seller_id}')
        reporter_contact=st.text_input('Your email or phone optional',key=f'report_contact_{key_prefix}_{listing_id}_{seller_id}')
        reason=st.selectbox('Reason',REPORT_REASONS,key=f'report_reason_{key_prefix}_{listing_id}_{seller_id}')
        details=st.text_area('Details',key=f'report_details_{key_prefix}_{listing_id}_{seller_id}',placeholder='Explain what House Of Wax should review. Do not enter sensitive private information.')
        sub=st.form_submit_button('Submit Report')
    if sub:
        if not safe(details):
            st.warning('Add a few details so House Of Wax knows what to review.')
            return
        data={'listing_id':listing_id,'seller_id':seller_id,'reporter_name':reporter_name,'reporter_contact':reporter_contact,'reason':reason,'details':details,'status':'Open','created_at':now(),'updated_at':now()}
        new_id=core_insert('listing_reports',data,'''INSERT INTO listing_reports(listing_id,seller_id,reporter_name,reporter_contact,reason,details,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['listing_id','seller_id','reporter_name','reporter_contact','reason','details','status','created_at','updated_at']))
        if new_id or not hosted_enabled():
            st.success('Report received. House Of Wax may review the listing or seller under platform rules.')
        else:
            st.error('Report could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

def buyer_activity_tables(bid):
    if hosted_enabled():
        inquiries=enrich_activity_rows(hosted_select('listing_inquiries',{'buyer_id':int(bid)},order='created_at.desc'))
        purchases=enrich_activity_rows(hosted_select('purchase_requests',{'buyer_id':int(bid)},order='created_at.desc'))
    else:
        inquiries=df("""SELECT i.*,p.artist,p.title,p.listing_status,s.store_name FROM listing_inquiries i LEFT JOIN products p ON i.product_id=p.id LEFT JOIN sellers s ON i.seller_id=s.id WHERE i.buyer_id=? ORDER BY i.created_at DESC""",(int(bid),))
        purchases=df("""SELECT pr.*,p.artist,p.title,p.listing_status,s.store_name FROM purchase_requests pr LEFT JOIN products p ON pr.product_id=p.id LEFT JOIN sellers s ON pr.seller_id=s.id WHERE pr.buyer_id=? ORDER BY pr.created_at DESC""",(int(bid),))
    return inquiries,purchases

def buyer_request_history(bid):
    st.subheader('Buyer inquiries and purchase requests')
    st.caption('These views show activity tied to the selected buyer profile. Requests sent without selecting a buyer profile are still delivered to the seller, but will not appear here.')
    inquiries,purchases=buyer_activity_tables(bid)
    itab,ptab=st.tabs(['My inquiries','My purchase requests'])
    with itab:
        if inquiries.empty:
            st.info('No buyer inquiries are linked to this buyer profile yet.')
        else:
            cols=[c for c in ['id','store_name','artist','title','preferred_contact_method','message','status','listing_status','created_at'] if c in inquiries.columns]
            st.dataframe(inquiries[cols],width='stretch')
    with ptab:
        if purchases.empty:
            st.info('No purchase requests are linked to this buyer profile yet.')
        else:
            cols=[c for c in ['id','store_name','artist','title','fulfillment_preference','offer_price','buyer_message','status','listing_status','created_at'] if c in purchases.columns]
            st.dataframe(purchases[cols],width='stretch')

def enrich_listing_with_seller_columns(products):
    if products.empty:
        return products
    out=products.copy()
    for col in ['store_name','seller_status','seller_level','seller_city','seller_state']:
        if col not in out.columns:
            out[col]=''
    for idx,row in out.iterrows():
        seller=get_seller(int(row.get('seller_id') or 0)) if safe(row.get('seller_id')) else None
        if seller is not None:
            out.at[idx,'store_name']=safe(seller.get('store_name'))
            out.at[idx,'seller_status']=normalize_seller_status(seller.get('status'))
            out.at[idx,'seller_level']=safe(seller.get('seller_level'))
            out.at[idx,'seller_city']=safe(seller.get('city'))
            out.at[idx,'seller_state']=safe(seller.get('state'))
        else:
            out.at[idx,'seller_status']='Missing Seller'
    return out

def load_global_marketplace_listings():
    statuses=live_marketplace_statuses()
    if hosted_enabled():
        prods=hosted_select('products',in_filters={'listing_status':statuses},order='created_at.desc')
    else:
        placeholders=','.join(['?']*len(statuses))
        prods=df(f"""SELECT p.*,s.store_name,s.status seller_status,s.seller_level,s.city seller_city,s.state seller_state
            FROM products p
            LEFT JOIN sellers s ON p.seller_id=s.id
            WHERE p.listing_status IN ({placeholders})
            ORDER BY p.created_at DESC""",tuple(statuses))
    prods=enrich_listing_with_seller_columns(prods)
    if prods.empty:
        return prods
    return prods[prods['seller_status'].apply(lambda value: normalize_seller_status(value)=='Approved Seller')].copy()

def filter_global_marketplace_listings(prods, keyword='', category='All', fmt='All', condition='All', seller='All', location='', min_price='', max_price='', sort_by='Newest'):
    shown=prods.copy()
    if keyword:
        term=keyword.strip().lower()
        fields=['artist','title']
        mask=pd.Series(False,index=shown.index)
        for field in fields:
            if field in shown.columns:
                mask=mask | shown[field].fillna('').astype(str).str.lower().str.contains(term,na=False,regex=False)
        words=[word for word in re.split(r'\s+',term) if word]
        if len(words)>1:
            word_mask=pd.Series(True,index=shown.index)
            combined=(shown.get('artist',pd.Series('',index=shown.index)).fillna('').astype(str)+' '+shown.get('title',pd.Series('',index=shown.index)).fillna('').astype(str)).str.lower()
            for word in words:
                word_mask=word_mask & combined.str.contains(word,na=False,regex=False)
            mask=mask | word_mask
        shown=shown[mask]
    if category!='All' and 'category' in shown.columns:
        shown=shown[shown['category'].fillna('').astype(str)==category]
    if fmt!='All' and 'format' in shown.columns:
        shown=shown[shown['format'].fillna('').astype(str)==fmt]
    if condition!='All':
        condition_mask=pd.Series(False,index=shown.index)
        for field in ['media_grade','sleeve_grade']:
            if field in shown.columns:
                condition_mask=condition_mask | shown[field].fillna('').astype(str).str.contains(condition,na=False,regex=False)
        shown=shown[condition_mask]
    if seller!='All' and 'store_name' in shown.columns:
        shown=shown[shown['store_name'].fillna('').astype(str)==seller]
    if location:
        term=location.strip().lower()
        location_mask=pd.Series(False,index=shown.index)
        for field in ['seller_city','seller_state']:
            if field in shown.columns:
                location_mask=location_mask | shown[field].fillna('').astype(str).str.lower().str.contains(term,na=False,regex=False)
        shown=shown[location_mask]
    min_value,min_error=parse_money_input(min_price,'Minimum price')
    max_value,max_error=parse_money_input(max_price,'Maximum price')
    if min_price and not min_error:
        shown=shown[pd.to_numeric(shown['price'],errors='coerce').fillna(0)>=float(min_value)]
    if max_price and not max_error:
        shown=shown[pd.to_numeric(shown['price'],errors='coerce').fillna(0)<=float(max_value)]
    if min_error:
        st.warning(min_error)
    if max_error:
        st.warning(max_error)
    if sort_by=='Price low to high':
        shown=shown.sort_values('price',ascending=True,na_position='last')
    elif sort_by=='Price high to low':
        shown=shown.sort_values('price',ascending=False,na_position='last')
    elif sort_by=='Artist/title A-Z':
        shown=shown.sort_values([c for c in ['artist','title'] if c in shown.columns],ascending=True,na_position='last') if any(c in shown.columns for c in ['artist','title']) else shown
    else:
        shown=shown.sort_values('created_at',ascending=False,na_position='last') if 'created_at' in shown.columns else shown
    return shown

def product_card(p):
    with st.container(border=True):
        seller=get_seller(int(p['seller_id'])) if safe(p.get('seller_id')) else None
        image=listing_primary_image(p)
        if image: safe_image(image,width=220,fallback_text='Listing image unavailable.')
        else: st.info('No listing image yet.')
        if has_listing_photos(int(p['id'])):
            status_badge('📷 Seller photos included','success')
        elif image:
            status_badge('Reference image','warning')
        st.subheader(safe(p.get('title'),'Untitled listing'))
        st.write('**Artist:** '+safe(p.get('artist'),'Unknown artist'))
        st.caption(f"Format: {safe(p.get('format')) or 'Not listed'}")
        st.caption(f"Condition: {safe(p.get('media_grade'),'Not listed')}")
        status_label=listing_availability_label(p)
        price_col,status_col=st.columns(2)
        price_col.metric('Price',money(p['price']))
        if status_label=='Available':
            with status_col:
                status_badge('Live','success')
        elif status_label=='Pending':
            with status_col:
                status_badge(status_label,'warning')
        elif status_label=='Sold':
            with status_col:
                status_badge(status_label,'danger')
        else:
            with status_col:
                listing_status_badge(status_label)
        if seller is not None:
            st.caption('Seller: '+safe(seller.get('store_name')))
            public_seller_trust_badge(seller)
            if st.button('View Store',key=f"seller_store_from_item_{int(p['id'])}_{int(seller.get('id'))}",width='stretch'):
                st.session_state['seller_id']=int(seller.get('id'))
                st.session_state.pop('product_id',None)
                st.rerun()
        if st.button('View Item',key=f"item_{int(p['id'])}",width='stretch'): st.session_state['product_id']=int(p['id']); st.rerun()
        if is_available_listing(p):
            if st.button('Ask Seller',key=f"ask_item_{int(p['id'])}",width='stretch'):
                set_pending_action('Ask Seller',p)
                st.session_state['product_id']=int(p['id'])
                st.session_state[f'open_inquiry_{int(p["id"])}']=True
                if not is_authenticated():
                    request_marketplace_navigation('My Account')
                st.rerun()
            if st.button('Buy',key=f"buy_request_item_{int(p['id'])}",width='stretch'):
                set_pending_action('Request to Buy',p)
                st.session_state['product_id']=int(p['id'])
                st.session_state[f'open_purchase_{int(p["id"])}']=True
                if not is_authenticated():
                    request_marketplace_navigation('My Account')
                st.rerun()
            if st.button('Make an Offer',key=f"offer_item_{int(p['id'])}",width='stretch'):
                set_pending_action('Make Offer',p)
                st.session_state['product_id']=int(p['id'])
                st.session_state[f'open_offer_{int(p["id"])}']=True
                if not is_authenticated():
                    request_marketplace_navigation('My Account')
                st.rerun()
        else:
            st.caption('Buyer actions are hidden unless the listing is live/public and available.')
        with st.expander('Report Listing',expanded=False):
            report_listing_form(p,seller,f'card_listing_{int(p["id"])}')
def seller_profile(sid):
    s=get_seller(sid)
    if s is None: st.error('Seller not found.'); return
    if st.button('← Back to marketplace'): st.session_state.pop('seller_id',None); st.rerun()
    if safe(s['banner_url']): safe_image(safe(s['banner_url']),width='stretch',fallback_text='Banner image unavailable.')
    col1,col2=st.columns([1,4])
    with col1:
        if safe(s['logo_url']): safe_image(safe(s['logo_url']),width='stretch',fallback_text='Logo image unavailable.')
        else: st.markdown('## 🏪')
    with col2:
        st.title(safe(s['store_name']))
        public_seller_trust_badge(s)
        st.caption(f"Rating {s['rating']}% • Sales {s['completed_sales']} • Followers {followers(sid)}")
        render_seller_trust_badges(sid,'public')
        if safe(s['instagram']): st.write('Instagram: '+safe(s['instagram']))
        if safe(s['website']):
            site_url=safe(s['website']).strip()
            if not site_url.startswith(('http://','https://')):
                site_url='https://'+site_url
            st.link_button('Seller website',site_url)
    with st.expander('Follow this seller'):
        bid=ensure_linked_buyer_profile() if is_authenticated() else 0
        if not bid:
            st.info('Sign in as a Buyer to follow this seller.')
        elif st.button('Follow seller',key=f'followbtn{sid}'):
            existing=hosted_select('seller_followers',{'seller_id':sid,'buyer_id':bid},limit=1) if hosted_enabled() else df('SELECT id FROM seller_followers WHERE seller_id=? AND buyer_id=?',(sid,bid))
            if existing.empty:
                data={'seller_id':sid,'buyer_id':bid,'created_at':now()}
                new_id=core_insert('seller_followers',data,'INSERT INTO seller_followers(seller_id,buyer_id,created_at) VALUES(?,?,?)',(sid,bid,now()))
                if new_id or not hosted_enabled():
                    st.success('Followed.')
                else:
                    st.error('Could not follow this seller. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
            else: st.info('Already following.')
    anns=hosted_select('store_announcements',{'seller_id':sid,'status':'Active'},order='created_at.desc') if hosted_enabled() else df("SELECT * FROM store_announcements WHERE seller_id=? AND status='Active' ORDER BY created_at DESC",(sid,))
    if not anns.empty:
        st.subheader('Store announcements')
        for _,a in anns.iterrows():
            with st.container(border=True): st.write('**'+safe(a['title'])+'**'); st.write(safe(a['body']))
    evs=hosted_select('seller_events',{'seller_id':sid,'status':'Active'},order='event_date.asc') if hosted_enabled() else df("SELECT * FROM seller_events WHERE seller_id=? AND status='Active' ORDER BY event_date",(sid,))
    if not evs.empty:
        st.subheader('Drops / events')
        for _,e in evs.iterrows():
            with st.container(border=True): st.write(f"**{safe(e['event_title'])}** — {safe(e['event_type'])}"); st.caption(safe(e['event_date'])); st.write(safe(e['description']))
    st.subheader('About this seller')
    if safe(s['seller_story']) or safe(s['store_bio']):
        st.write(safe(s['seller_story'],safe(s['store_bio'])))
    else:
        st.info("This seller hasn't added a bio yet.")
    location=', '.join([x for x in [safe(s.get('city')),safe(s.get('state'))] if x])
    st.write('**Location:** '+safe(location,'Not listed'))
    st.write('**Favorite genres/categories:** '+safe(s['specialties'],'Not listed'))
    st.write('**Contact preference:** '+safe(s.get('contact_preference'),'Use House Of Wax messages when available.'))
    with st.expander('Report Seller',expanded=False):
        st.caption('Use this if a seller appears misleading, unsafe, abusive, or against House Of Wax platform rules.')
        report_listing_form(None,s,f'seller_{sid}')
    pol=hosted_select('seller_policies',{'seller_id':sid},limit=1) if hosted_enabled() else df('SELECT * FROM seller_policies WHERE seller_id=?',(sid,))
    if not pol.empty:
        p=pol.iloc[0]
        st.subheader('Store policies')
        if safe(p.get('shipping_policy')): st.write('**Shipping:** '+safe(p.get('shipping_policy')))
        if safe(p.get('return_policy')): st.write('**Returns:** '+safe(p.get('return_policy')))
        if safe(p.get('local_pickup_policy')): st.write('**Pickup / meetups:** '+safe(p.get('local_pickup_policy')))
    st.subheader('Reviews')
    reviews=seller_reviews(sid)
    if reviews.empty:
        st.info('No reviews yet. Reviews appear here once a buyer completes a purchase and leaves feedback.')
    else:
        summary=seller_review_summary(sid)
        st.metric('Average rating',f"{summary['average']} / 5",help=f"Based on {summary['count']} review(s)")
        for _,rv in reviews.iterrows():
            with st.container(border=True):
                st.write('⭐ '*int(rv.get('rating') or 0)+f" ({int(rv.get('rating') or 0)}/5)")
                st.caption(f"{safe(rv.get('buyer_display_name'),'A House Of Wax buyer')} • {safe(rv.get('created_at'))}")
                if safe(rv.get('review_text')):
                    st.write(safe(rv.get('review_text')))
    st.subheader('Public inventory')
    prods=hosted_select('products',{'seller_id':int(sid)},in_filters={'listing_status':public_listing_query_statuses()},order='created_at.desc') if hosted_enabled() else df("SELECT * FROM products WHERE seller_id=? AND listing_status IN ('Live','Active','Approved','Public','Pending Pickup/Payment','Pending','Sold') ORDER BY created_at DESC",(sid,))
    if prods.empty: st.info('No public inventory yet. Draft, Hidden, Under Review, and Removed listings stay private or unavailable inside Seller Tools.')
    else:
        cols=st.columns(3)
        for i,(_,p) in enumerate(prods.iterrows()):
            with cols[i%3]: product_card(p)
def product_detail(pid):
    r=hosted_select('products',{'id':int(pid)},limit=1) if hosted_enabled() else df('SELECT * FROM products WHERE id=?',(int(pid),))
    if r.empty: st.error('Product missing.'); st.session_state.pop('product_id',None); return
    p=r.iloc[0]; s=get_seller(int(p['seller_id']))
    is_public=is_public_listing(p)
    is_available=is_available_listing(p)
    if st.button('← Back to marketplace'): st.session_state.pop('product_id',None); st.rerun()
    l,rcol=st.columns([1.2,1])
    with l:
        primary_image=listing_primary_image(p)
        if primary_image: safe_image(primary_image,width='stretch',fallback_text='Listing image unavailable.')
        else: st.markdown('## 🎵')
        if has_listing_photos(int(pid)):
            status_badge('📷 Seller photos included','success')
            st.caption('This listing includes real photos of the seller\'s exact copy.')
        elif primary_image:
            status_badge('Reference image','warning')
            st.caption('This is official release art, not a photo of the seller\'s exact copy. Ask the seller for condition photos if you want to see the real item before buying.')
        render_listing_photo_gallery(pid,primary_image,'public')
    with rcol:
        st.title(f"{safe(p['artist'])} — {safe(p['title'])}"); st.write('**Price:** '+money(p['price'])); st.write('**Shipping:** '+money(p['shipping_price']))
        sold_comps=sold_price_history(p['artist'],exclude_product_id=int(pid))
        if not sold_comps.empty:
            comp_prices=sold_comps['price'].dropna().astype(float)
            comp_prices=comp_prices[comp_prices>0]
            if not comp_prices.empty:
                # st.expander's label renders as markdown, where a bare $ is
                # read as LaTeX math delimiters -- escape it or "$12-$18"
                # renders as a garbled equation instead of a price range.
                price_range=f"{money(comp_prices.min())}–{money(comp_prices.max())}".replace('$','\\$')
                with st.expander(f"Recently sold: {len(comp_prices)} similar copy(ies), {price_range}"):
                    st.caption(f"Other {safe(p['artist'])} copies sold on House Of Wax — use this to gauge a fair price.")
                    for _,comp in sold_comps.iterrows():
                        st.write(f"**{safe(comp.get('title'))}** • {safe(comp.get('media_grade'),'Condition not listed')} • {money(comp.get('price'))} • {safe(comp.get('updated_at'))[:10]}")
        if is_public:
            share_block('product',int(pid),f"{safe(p['artist'])} — {safe(p['title'])}")
        status_label=listing_availability_label(p)
        if status_label!='Available':
            st.warning(status_label)
        for label,col in [('Category','category'),('Format','format'),('Label','label'),('Release year','release_year'),('Barcode / UPC / EAN','barcode'),('Catalog #','catalog_number'),('Matrix / runout','matrix_runout'),('Condition','media_grade')]: st.write(f"**{label}:** {safe(p[col],'Not listed')}")
        if safe(p.get('external_release_url')):
            release_url=safe(p.get('external_release_url')).strip()
            if not release_url.startswith(('http://','https://')):
                release_url='https://'+release_url
            st.link_button('View release info',release_url)
        if s is not None:
            st.write('**Seller:** '+safe(s.get('store_name')))
            render_seller_trust_badges(int(s['id']),'public')
            if is_available:
                st.caption('Questions before buying? Contact the seller through House Of Wax.')
                if st.button('Contact Seller / Ask About This Item',key=f'detail_ask_top_{pid}',width='stretch'):
                    set_pending_action('Ask Seller',p)
                    st.session_state[f'open_inquiry_{pid}']=True
                    if not is_authenticated():
                        request_marketplace_navigation('My Account')
                    st.rerun()
                if st.button('Buy',key=f'detail_purchase_top_{pid}',width='stretch'):
                    set_pending_action('Request to Buy',p)
                    st.session_state[f'open_purchase_{pid}']=True
                    if not is_authenticated():
                        request_marketplace_navigation('My Account')
                    st.rerun()
                if st.button('Make an Offer',key=f'detail_offer_top_{pid}',width='stretch'):
                    set_pending_action('Make Offer',p)
                    st.session_state[f'open_offer_{pid}']=True
                    if not is_authenticated():
                        request_marketplace_navigation('My Account')
                    st.rerun()
                st.caption('Checkout is not live yet. Buy sends a purchase request, not a payment.')
            if st.button('View seller public profile'): st.session_state['seller_id']=int(s['id']); st.session_state.pop('product_id',None); st.rerun()
    st.subheader('Description'); st.write(safe(p['description'],'No description.'))
    if safe(p.get('video_url')):
        st.subheader('Video')
        try:
            st.video(safe(p.get('video_url')))
        except Exception:
            st.caption('Video could not be loaded from the link the seller provided.')
    st.info('This listing was published by the seller. Report concerns to House Of Wax.')
    with st.expander('Report Listing',expanded=False):
        report_listing_form(p,s,f'listing_{pid}')
    st.divider(); st.subheader('Buyer actions')
    if not is_public:
        st.info('Buyer actions appear only for public marketplace listings.')
        return
    if is_available:
        st.session_state.pop(f'open_inquiry_{pid}',False)
        with st.expander('Ask About This Item / Contact Seller',expanded=True):
            render_buyer_inquiry_form(p,s,f'product_{pid}')
        purchase_expanded=bool(st.session_state.pop(f'open_purchase_{pid}',False))
        with st.expander('Buy',expanded=purchase_expanded):
            render_purchase_request_form(p,f'product_{pid}')
        offer_expanded=bool(st.session_state.pop(f'open_offer_{pid}',False))
        with st.expander('Make an Offer',expanded=offer_expanded):
            render_offer_form(p,f'product_{pid}')
    else:
        st.info(f"This listing is {listing_availability_label(p).lower()}, so public buyer actions are turned off.")

# ---------- Pages ----------

# ---------- House Of Wax Knowledge Hub ----------
KNOWLEDGE_CATEGORIES=[
    'Record Collecting 101',
    'Vinyl Grading School',
    'Barcode, Catalog & Matrix Guides',
    'Spotting Bootlegs and Reissues',
    'How to Buy Safely',
    'Care, Storage & Cleaning',
    'Genre Education',
    'Music History & Culture',
    'House Of Wax Trust Standards',
    'Marketplace Education'
]

def seed_knowledge():
    if hosted_enabled():
        return
    posts=table('knowledge_posts')
    if posts.empty:
        starters=[
            ('What Does VG+ Mean When Buying Vinyl?','Vinyl Grading School','Beginners','Beginner','VG+ means Very Good Plus. It usually describes a record that has been played but still has strong sound quality.','VG+ does not mean perfect. It usually means the record may show light marks, minor sleeve scuffs, or small signs of handling, but it should play well without major issues like repeated skips. Buyers should read condition notes, review photos, and ask questions when a grade is not clear.','On House Of Wax, grading education helps buyers understand what they are paying for before they purchase.'),
            ('What Is a Matrix / Runout?','Barcode, Catalog & Matrix Guides','Collectors','Beginner','A matrix or runout is information etched or stamped near the center label of a record.','The matrix/runout area can help collectors identify a pressing, plant, mastering engineer, or version. It is one of the most useful clues when comparing originals, reissues, promos, and different pressings.','House Of Wax encourages sellers and buyers to record matrix/runout information whenever possible.'),
            ('How to Spot a Bootleg or Unofficial Pressing','Spotting Bootlegs and Reissues','Buyers','Intermediate','Bootlegs and unofficial pressings can look real at first glance, but details often reveal the truth.','Collectors should compare label design, barcode, catalog number, matrix/runout, print quality, release history, and seller notes. A suspiciously low price on a rare record can also be a warning sign.','House Of Wax believes transparency protects both buyers and honest sellers.'),
            ('How to Store Vinyl Records the Right Way','Care, Storage & Cleaning','Beginners','Beginner','Good storage protects sound quality, jacket condition, and long-term value.','Store records vertically, avoid heat and sunlight, use inner and outer sleeves, and keep records away from moisture. Never stack records flat for long periods because weight can cause warping or ring wear.','Better storage means better collecting and fewer condition disputes.'),
            ('Why Buyer and Seller Feedback Should Be Public','House Of Wax Trust Standards','Everyone','Beginner','Public feedback helps the community understand who they are doing business with.','Trust matters in a marketplace built around used, collectible, and condition-sensitive goods. Public feedback gives buyers and sellers more confidence before a transaction.','House Of Wax is built around education, transparency, and accountability.')
        ]
        for title,cat,aud,level,summary,body,tip in starters:
            data={'title':title,'category':cat,'audience':aud,'level':level,'summary':summary,'body':body,'house_tip':tip,'status':'Published','featured':'Yes' if 'VG+' in title else 'No','created_at':now(),'updated_at':now()}
            core_insert('knowledge_posts',data,"""INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",tuple(data[k] for k in ['title','category','audience','level','summary','body','house_tip','status','featured','created_at','updated_at']))
    terms=table('glossary_terms')
    if terms.empty:
        starter_terms=[
            ('VG+','Vinyl grading','Very Good Plus. A common collector grade for a used record that should still play well.','Helps buyers understand condition and price.','A VG+ record may have light sleeve scuffs but should not have deep scratches.'),
            ('Matrix / Runout','Record identification','Etched or stamped information near the center label of a vinyl record.','Can help identify the exact pressing.','A1/B1 or stamped plant codes can point to a specific version.'),
            ('Catalog Number','Record identification','The label or release number assigned to a record, CD, cassette, or music item.','Helps verify the release and compare versions.','A catalog number printed on the spine may match the label listing.'),
            ('Reissue','Pressing history','A later release of an album or single after the original issue.','Reissues can be valuable, but they are not the same as originals.','A 2020 reissue of a 1972 soul record is not the original 1972 pressing.'),
            ('Promo Copy','Record collecting','A promotional copy distributed to radio stations, DJs, reviewers, or industry contacts.','Promos can be collectible but should be clearly described.','White label promo copies often have special labels or stamps.')
        ]
        for term,cat,definition,why,example in starter_terms:
            data={'term':term,'category':cat,'plain_definition':definition,'why_it_matters':why,'example':example,'status':'Published','created_at':now(),'updated_at':now()}
            core_insert('glossary_terms',data,"""INSERT OR IGNORE INTO glossary_terms(term,category,plain_definition,why_it_matters,example,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",tuple(data[k] for k in ['term','category','plain_definition','why_it_matters','example','status','created_at','updated_at']))

def make_social_pack(title,category,summary,body,tip):
    core=safe(summary) or safe(body)[:180]
    hashtag_base='#HouseOfWax #VinylCommunity #RecordCollecting #MusicCulture #CollectSmarter'
    caption=f"{title}\n\n{core}\n\nHouse Of Wax is here to help people collect smarter, buy with confidence, and understand the culture behind the music.\n\n{hashtag_base}"
    reel=f"Hook: Before you buy another record, learn this: {title}\n\nScene 1: Show the record/detail being discussed.\nScene 2: Explain the simple definition in one sentence.\nScene 3: Show why it matters for buyers and collectors.\nScene 4: End with: Collect smarter with House Of Wax."
    fb=f"House Of Wax Knowledge Hub: {title}\n\n{core}\n\nWhy it matters: {safe(tip,'Education builds trust in the marketplace.')}\n\nLearn more inside House Of Wax."
    newsletter=f"This week in the House Of Wax Knowledge Hub: {title}. {core} This is part of our mission to make record collecting, marketplace trust, and music culture easier to understand for everyone."
    return {'Instagram/Facebook caption':caption,'Short-form video script':reel,'Facebook educational post':fb,'Newsletter blurb':newsletter,'Hashtags':hashtag_base,'CTA':'Learn more in the House Of Wax Knowledge Hub.'}

def knowledge_card(row, key_prefix='knowledge'):
    with st.container(border=True):
        if safe(row.get('image_url')): safe_image(safe(row.get('image_url')),width='stretch',fallback_text='Image unavailable.')
        st.subheader(safe(row.get('title')))
        st.caption(f"{safe(row.get('category'))} • {safe(row.get('level'))} • {safe(row.get('audience'))}")
        st.write(safe(row.get('summary')))
        unique_key=f"read_knowledge_{key_prefix}_{int(row['id'])}"
        if st.button('Read article',key=unique_key):
            st.session_state['selected_knowledge_id']=int(row['id']); st.rerun()

def tester_start_here(key_prefix='main'):
    st.markdown('## Tester Start Here')
    st.info('House Of Wax is a working prototype. Use sample contact info only. Do not enter payment info, passwords, private addresses, or sensitive private information. Some data may be temporary/local during prototype testing.')
    st.write('Use one path at a time. The goal is to see where the app feels clear, where it slows you down, and where trust or listing details feel missing.')
    buyer, seller, admin = st.tabs(['Buyer Test Path','Seller Test Path','Admin Test Path'])
    with buyer:
        st.subheader('Buyer Test Path')
        for item in [
            'Go to Marketplace.',
            'Open a live marketplace item.',
            'Review photos and condition.',
            'Click Contact Seller / Ask About This Item.',
            'Submit a sample inquiry.',
            'Click Buy, or click Make an Offer to try proposing a price.',
            'Submit a sample purchase request or offer.',
            'Leave tester feedback.'
        ]:
            st.write(f'- {item}')
    with seller:
        st.subheader('Seller Test Path')
        for item in [
            'Go to My House of Wax.',
            'Choose Seller role.',
            'Open Seller Tools.',
            'Create or update My Store / Seller Profile.',
            'Click Add Inventory / Upload Product.',
            'Add a sample item.',
            'Add condition and photos.',
            'Preview listing.',
            'Save as Draft.',
            'Publish to My Store if your seller account is approved.',
            'Check My Listings / Inventory.',
            'Leave tester feedback.'
        ]:
            st.write(f'- {item}')
        st.caption('Your public store/profile may only show live/public listings. Draft, hidden, and moderation listings stay inside Seller Tools.')
    with admin:
        st.subheader('Admin Test Path')
        for item in [
            'Go to My House of Wax.',
            'Turn on Testing/Admin mode if needed.',
            'Open Admin Tools.',
            'Open Moderation Center.',
            'Review seller approval and listing/seller reports.',
            'Add moderation notes if needed.',
            'Hide/remove a reported listing or suspend/reinstate a seller when needed.',
            'Check Admin Tester Feedback Review.',
            'Leave tester feedback.'
        ]:
            st.write(f'- {item}')
    with st.container(border=True):
        st.markdown('### Completion Checklist')
        st.checkbox('Buyer flow completed',key=f'tester_check_buyer_{key_prefix}')
        st.checkbox('Seller flow completed',key=f'tester_check_seller_{key_prefix}')
        st.checkbox('Admin flow completed, if applicable',key=f'tester_check_admin_{key_prefix}')
        st.checkbox('Feedback submitted',key=f'tester_check_feedback_{key_prefix}')

def tester_feedback_form(key_prefix='public'):
    st.markdown('## Tester Feedback')
    st.info('Use sample information only. Do not enter sensitive private information, real payment details, passwords, private addresses, or anything you would not want reviewed by the House Of Wax team.')
    st.write('Test buyer flow, seller flow, Knowledge Center, and admin/moderation flow if available, and tell us where you got stuck. This helps House Of Wax improve before adding risky production features.')
    st.caption('New here? The full testing checklist (Buyer/Seller/Admin paths) lives on the Home page under Tester Start Here.')
    with st.form(f'tester_feedback_form_{key_prefix}'):
        tester_name=st.text_input('Tester name optional',key=f'tester_feedback_name_{key_prefix}')
        tester_type=st.selectbox('Tester type',['Buyer','Seller','Admin/Reviewer','Investor/Advisor','Other'],key=f'tester_feedback_type_{key_prefix}')
        page_flow=st.text_input('Page/flow tested',placeholder='Example: Marketplace buyer flow, Seller upload, Knowledge Center, Moderation Center',key=f'tester_feedback_flow_{key_prefix}')
        worked_well=st.text_area('What worked well',key=f'tester_feedback_worked_{key_prefix}')
        confusing=st.text_area('What was confusing',key=f'tester_feedback_confusing_{key_prefix}')
        felt_broken=st.text_area('What felt broken',key=f'tester_feedback_broken_{key_prefix}')
        missing=st.text_area('What is missing',key=f'tester_feedback_missing_{key_prefix}')
        ease_rating=st.slider('Ease of use rating',1,5,3,key=f'tester_feedback_rating_{key_prefix}')
        would_use_again=st.selectbox('Would you use this again',['Yes','Maybe','No'],key=f'tester_feedback_use_again_{key_prefix}')
        open_notes=st.text_area('Open notes',key=f'tester_feedback_notes_{key_prefix}')
        submitted=st.form_submit_button('Submit tester feedback')
    if submitted:
        if not safe(page_flow) and not safe(worked_well) and not safe(confusing) and not safe(felt_broken) and not safe(missing) and not safe(open_notes):
            st.warning('Add at least one note or a page/flow tested before submitting.')
        else:
            data={'tester_name':tester_name,'tester_type':tester_type,'page_flow':page_flow,'worked_well':worked_well,'confusing':confusing,'felt_broken':felt_broken,'missing':missing,'ease_rating':int(ease_rating),'would_use_again':would_use_again,'open_notes':open_notes,'status':'New','created_at':now()}
            new_id=core_insert('tester_feedback',data,'''INSERT INTO tester_feedback(tester_name,tester_type,page_flow,worked_well,confusing,felt_broken,missing,ease_rating,would_use_again,open_notes,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',tuple(data[k] for k in ['tester_name','tester_type','page_flow','worked_well','confusing','felt_broken','missing','ease_rating','would_use_again','open_notes','status','created_at']))
            if new_id or not hosted_enabled():
                st.success('Feedback saved. Thank you for helping test House Of Wax.')
            else:
                st.error('Feedback could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

def admin_tester_feedback_view():
    st.subheader('Tester Feedback Review')
    st.warning('Tester feedback is private/admin-facing. Do not publish tester contact details or sensitive notes.')
    feedback=table('tester_feedback')
    if feedback.empty:
        st.info('No tester feedback has been submitted yet.')
        return
    tester_types=['All']+sorted([safe(x) for x in feedback['tester_type'].dropna().unique().tolist() if safe(x)])
    selected=st.selectbox('Filter by tester type',tester_types,key='admin_feedback_type_filter')
    filtered=feedback.copy()
    if selected!='All':
        filtered=filtered[filtered['tester_type']==selected]
    st.metric('Feedback entries shown',len(filtered))
    cols=[c for c in ['id','tester_type','page_flow','ease_rating','would_use_again','status','created_at','worked_well','confusing','felt_broken','missing','open_notes'] if c in filtered.columns]
    st.dataframe(filtered[cols].sort_values('id',ascending=False),width='stretch')
    st.download_button('Download tester feedback CSV',filtered[cols].to_csv(index=False),file_name='house_of_wax_tester_feedback.csv',key='tester_feedback_csv_download')
    if not filtered.empty:
        pick=st.selectbox('Feedback entry',filtered.sort_values('id',ascending=False)['id'].tolist(),key='admin_feedback_pick')
        row=filtered[filtered['id']==pick].iloc[0]
        with st.container(border=True):
            st.write(f"**Tester type:** {safe(row.get('tester_type'))}")
            st.write(f"**Page/flow tested:** {safe(row.get('page_flow'))}")
            st.write(f"**Ease rating:** {safe(row.get('ease_rating'))}/5")
            st.write(f"**Would use again:** {safe(row.get('would_use_again'))}")
            for label,col in [('Worked well','worked_well'),('Confusing','confusing'),('Felt broken','felt_broken'),('Missing','missing'),('Open notes','open_notes')]:
                if safe(row.get(col)):
                    st.markdown(f'**{label}**')
                    st.write(safe(row.get(col)))

def knowledge_center_education_hub():
    st.write('A practical guide to buying, selling, collecting, photos, condition, trust, and House Of Wax marketplace standards.')
    st.info("We're starting with vinyl records and music collectibles, with merch, memorabilia, clothing, and more culture goods on the way.")
    st.caption('New here? The full testing checklist (Buyer/Seller/Admin paths) lives on the Home page under Tester Start Here.')

    overview, buying, selling, condition, photos, trust, buyer_faq, seller_faq, rules = st.tabs([
        'What is House Of Wax?',
        'How buying works',
        'How selling works',
        'Condition guide',
        'Photo guide',
        'Trust + safety',
        'Buyer FAQ',
        'Seller FAQ',
        'Rules summary'
    ])
    with overview:
        st.subheader('What Is House Of Wax?')
        st.write('House Of Wax is a marketplace and culture platform for vinyl records, music collectibles, merch, memorabilia, and culture goods.')
        st.write('The first wedge is vinyl records and music collectibles because buyers care deeply about pressing details, condition, photos, seller trust, and the story behind the item.')
        st.write('The platform is built around better listings, buyer questions, seller profiles, review tools, and education that helps people collect smarter.')
    with buying:
        st.subheader('How Buying Works')
        for item in [
            'Browse Marketplace for live listings from approved sellers.',
            'Review photos, condition notes, seller profile, trust badges, and listing readiness information.',
            'Ask the seller a question if condition, shipping, photos, or availability are unclear.',
            'Use Buy when you are ready to move forward.',
            'In the prototype, checkout/payment may not be live yet. Buy sends purchase intent, not payment.',
            'Pending means the item is being held or worked out. Sold means it should no longer be available.'
        ]:
            st.write(f'- {item}')
    with selling:
        st.subheader('How Selling Works')
        for item in [
            'Create or update a seller profile so buyers understand who they are buying from.',
            'Search for a music item or enter details manually.',
            'Confirm the match before using search/database information.',
            'Add seller details, price, quantity, shipping, and condition notes.',
            'Add real photos of the exact item whenever possible.',
            'Preview the listing and review the listing readiness checklist.',
            'Save as Draft if it is not ready, or Publish to My Store when your seller account is approved.',
            'Respond to buyer inquiries and purchase requests.',
            'Mark items Pending or Sold when availability changes.'
        ]:
            st.write(f'- {item}')
    with condition:
        st.subheader('Condition Guide for Records and Music Collectibles')
        condition_rows=[
            ('Mint / Near Mint','Unused or almost flawless. Use carefully; most used items are not truly Mint.'),
            ('Very Good Plus','Played but strong. May have light marks or sleeve scuffs, but should not have major playback problems.'),
            ('Very Good','Noticeable wear. May have surface noise, marks, shelf wear, or visible use, but still collectible if described honestly.'),
            ('Good+','Well used but playable. More wear than Very Good -- expect consistent surface noise or handling marks -- but not yet heavy damage.'),
            ('Good','Heavy wear. Buyers should expect clear flaws, noise, or cosmetic issues. Detailed notes matter.'),
            ('Fair / Poor','Major flaws, damage, missing parts, warps, skips, tears, stains, or heavy wear. Sell only with clear photos and direct notes.')
        ]
        st.dataframe(pd.DataFrame(condition_rows,columns=['Level','Plain-language meaning']),width='stretch')
        st.write('Media condition covers the record, CD, cassette, or item itself. Sleeve, jacket, or case condition covers the packaging.')
        st.write('Condition honesty protects buyers, sellers, and the House Of Wax marketplace. High-value items need detailed photos, clear notes, and no guesswork.')
        st.caption('House Of Wax education helps sellers describe condition clearly, but it is not a professional grading guarantee.')
    with photos:
        st.subheader('Photo Guide')
        st.write('Photos build buyer trust because they show the actual thing being sold.')
        for item in [
            'Front cover or main item view.',
            'Back cover or reverse side.',
            'Vinyl/media surface, disc, cassette shell, or item material.',
            'Labels, tags, barcodes, catalog numbers, matrix/runout details, or authenticity details when relevant.',
            'Sleeve, jacket, case, inserts, booklets, posters, hype stickers, and included extras.',
            'Scratches, warps, stains, tears, writing, seam splits, cracked cases, missing parts, fading, or other damage.'
        ]:
            st.write(f'- {item}')
        st.write('For music items, search/database cover art can be a reference, but seller condition photos are still important. For non-music items, exact item photos are preferred; official/product images should only support the real item photos.')
    with trust:
        st.subheader('Trust and Safety Guide')
        for item in [
            'Seller profiles help buyers understand the seller, location, specialties, and marketplace history.',
            'Trust badges are House Of Wax platform indicators based on profile completeness, live listings, and marketplace history.',
            'Listing readiness helps sellers include clear details, photos, condition notes, price, and complete item information.',
            'The Moderation Center lets House Of Wax review reports, hide/remove problem listings, and manage seller approval.',
            'House Of Wax may investigate reports when photos, condition, item identity, safety, or seller behavior appears unclear or unsafe.',
            'Counterfeit, stolen, unsafe, misleading, or deceptive listings do not belong on House Of Wax.'
        ]:
            st.write(f'- {item}')
    with buyer_faq:
        st.subheader('Buyer FAQ')
        faq=[
            ('What does Buy mean?','It means you want to move forward. In the prototype it creates a purchase request so the seller can confirm availability, pickup/shipping, and next steps.'),
            ('Is payment live?','Not yet. The current prototype does not process checkout or payment.'),
            ('How do I contact a seller?','Use Contact Seller / Ask About This Item on live/public listings.'),
            ('How do I know if an item is available?','Live listings can show buyer action buttons. Pending and Sold items show unavailable status.'),
            ('What does Pending mean?','The item may be held, in discussion, or waiting on next steps.'),
            ('What does Sold mean?','The item should no longer be available to buy.'),
            ('What should I check before buying?','Photos, condition, seller profile, trust badges, listing quality, price, shipping/pickup, and any flaws or missing details.')
        ]
        for q,a in faq:
            with st.expander(q):
                st.write(a)
    with seller_faq:
        st.subheader('Seller FAQ')
        faq=[
            ('Do I need exact item photos?','Yes when possible. Exact photos are especially important for condition-sensitive and non-music items.'),
            ('Why does my seller account need approval?','House Of Wax approves who can sell. Approved sellers can publish directly, and House Of Wax can moderate reports afterward.'),
            ('What makes a strong listing?','Clear title, category, price, condition, seller notes, real photos, item identifiers, and honest flaws.'),
            ('What happens if House Of Wax reviews a report?','A listing may be hidden, placed under review, removed, or the seller may be restricted based on platform rules.'),
            ('How do I improve listing readiness?','Add condition notes, photos, accurate item details, price, format/category, and seller-specific information.'),
            ('What should I do when an item sells?','Update the listing status to Pending or Sold so buyers do not keep requesting unavailable items.')
        ]
        for q,a in faq:
            with st.expander(q):
                st.write(a)
    with rules:
        st.subheader('Marketplace Rules Summary')
        for item in [
            'Keep listings accurate.',
            'Use real photos when possible or required.',
            'No counterfeit, stolen, unsafe, or misleading items.',
            'Respect buyers and sellers.',
            'House Of Wax can review, request changes, reject, or remove listings.'
        ]:
            st.write(f'- {item}')

    if is_admin_unlocked():
        st.divider()
        st.markdown('### Admin / Founder Knowledge')
        st.warning('This section appears only because Admin role or Testing mode is enabled.')
        admin_rows=[
            ('Launch wedge notes','Start with vinyl records and music collectibles, then expand after seller and buyer behavior is validated.'),
            ('Testing script','Use the V25.34 buyer, seller, and admin testing script to watch confusion points and trust signals.'),
            ('Validation metrics','Track sellers tested, listings created, listings submitted, listings approved, buyer inquiries, purchase requests, and seller response rate.'),
            ('Business plan / funding roadmap','Use the funding roadmap for grants, lenders, partners, and investor conversations.'),
            ('Production readiness notes','Before public launch: real auth, hosted database, permanent image storage, payment/legal terms, and admin permission checks.')
        ]
        st.dataframe(pd.DataFrame(admin_rows,columns=['Founder/admin topic','Why it matters']),width='stretch')
    with st.expander('Tester Feedback',expanded=False):
        tester_feedback_form('knowledge_center')

def knowledge_hub():
    seed_knowledge()
    header()
    marketplace_context('House Of Wax Marketplace → Knowledge Hub')
    st.header('Knowledge Hub')
    st.write("Everything you need to buy and sell smarter — grading, pressings, barcodes and matrix numbers, trust, and the stories behind the music. Written by House Of Wax, not sponsored by sellers.")
    knowledge_center_education_hub()
    groove_divider()
    st.markdown('## Article Library + Glossary')
    if 'selected_knowledge_id' in st.session_state:
        selected_kid=int(st.session_state['selected_knowledge_id'])
        rows=hosted_select('knowledge_posts',{'id':selected_kid},limit=1) if hosted_enabled() else df('SELECT * FROM knowledge_posts WHERE id=?',(selected_kid,))
        if rows.empty:
            st.session_state.pop('selected_knowledge_id',None); st.rerun()
        post=rows.iloc[0]
        if st.button('← Back to Knowledge Hub'):
            st.session_state.pop('selected_knowledge_id',None); st.rerun()
        st.title(safe(post['title']))
        st.caption(f"{safe(post['category'])} • {safe(post['level'])} • For {safe(post['audience'])}")
        share_block('article',int(post['id']),safe(post['title']))
        if safe(post['image_url']): safe_image(safe(post['image_url']),width='stretch',fallback_text='Post image unavailable.')
        if safe(post.get('video_url')):
            try:
                st.video(safe(post.get('video_url')))
            except Exception:
                st.caption('Video could not be loaded from the link provided.')
        st.markdown('### Quick answer')
        st.write(safe(post['summary']))
        st.markdown('### Full guide')
        st.write(safe(post['body']))
        st.markdown('### House Of Wax tip')
        st.info(safe(post['house_tip'],'Collect smarter with House Of Wax.'))
        with st.expander('House Of Wax social media copy for this education post'):
            pack=make_social_pack(post['title'],post['category'],post['summary'],post['body'],post['house_tip'])
            for k,v in pack.items():
                st.markdown(f'**{k}**')
                st.text_area(k,v,height=140,key=f"social_pack_{k}_{int(post['id'])}")
        return
    featured=hosted_select('knowledge_posts',{'status':'Published','featured':'Yes'},order='updated_at.desc') if hosted_enabled() else df("SELECT * FROM knowledge_posts WHERE status='Published' AND featured='Yes' ORDER BY updated_at DESC")
    if not featured.empty:
        st.subheader('Featured education')
        knowledge_card(featured.iloc[0], 'featured')
    st.subheader('Search the education library')
    q=st.text_input('Search topics like VG+, barcode, runout, bootleg, storage, trust')
    cats=['All']+KNOWLEDGE_CATEGORIES
    cat=st.selectbox('Category',cats)
    posts=hosted_select('knowledge_posts',{'status':'Published'},order='updated_at.desc') if hosted_enabled() else df("SELECT * FROM knowledge_posts WHERE status='Published' ORDER BY updated_at DESC")
    if q:
        term=q.lower()
        posts=posts[
            posts['title'].fillna('').str.lower().str.contains(term) |
            posts['summary'].fillna('').str.lower().str.contains(term) |
            posts['body'].fillna('').str.lower().str.contains(term) |
            posts['category'].fillna('').str.lower().str.contains(term)
        ]
    if cat!='All': posts=posts[posts['category']==cat]
    cols=st.columns(2)
    for i,(_,row) in enumerate(posts.iterrows()):
        with cols[i%2]: knowledge_card(row, f'library_{i}')
    groove_divider()
    st.subheader('Collector glossary')
    terms=hosted_select('glossary_terms',{'status':'Published'},order='term.asc') if hosted_enabled() else df("SELECT * FROM glossary_terms WHERE status='Published' ORDER BY term")
    tq=st.text_input('Search glossary')
    if tq:
        term=tq.lower()
        terms=terms[
            terms['term'].fillna('').str.lower().str.contains(term) |
            terms['plain_definition'].fillna('').str.lower().str.contains(term) |
            terms['category'].fillna('').str.lower().str.contains(term)
        ]
    for _,t in terms.iterrows():
        with st.expander(f"{safe(t['term'])} — {safe(t['category'])}"):
            st.write(safe(t['plain_definition']))
            st.caption(f"Why it matters: {safe(t['why_it_matters'])}")
            if safe(t['example']): st.write(f"Example: {safe(t['example'])}")


def seed_content_series():
    series = [
        ('Wax 101','Beginner-friendly education about records, formats, collecting basics, and marketplace language.','New collectors','Clear, simple, useful','Education article'),
        ('Crate Talk','Short editorial posts about digging, discovery, collecting habits, and music culture.','Collectors and culture seekers','Conversational, stylish, curious','Editorial post'),
        ('Behind the Record','Stories behind records, pressings, labels, eras, artwork, and music scenes.','Music fans and collectors','Story-driven, cultural, researched','Feature article'),
        ('The Culture File','Broader music culture, regional scenes, flyers, fashion, streetwear, memorabilia, and community.','Culture seekers','Editorial, sharp, informed','Culture essay'),
        ('Then & Now','How formats, artists, scenes, prices, or collector habits changed over time.','Collectors and casual readers','Comparative, accessible','Then-and-now feature'),
        ('Press Play','Listening recommendations, genre intros, and discovery guides from House Of Wax.','Music discovery audience','Curated, enthusiastic, credible','Recommendation guide'),
        ('Format Focus','Deep dives on vinyl, CD, cassette, 12-inch singles, promos, test pressings, and other formats.','Collectors','Educational, specific, practical','Format guide'),
        ('House Rules','Trust, buyer/seller expectations, grading standards, feedback, and marketplace behavior.','Buyers and sellers','Direct, fair, trustworthy','Trust guide')
    ]
    for s in series:
        exists=df("SELECT id FROM content_series WHERE lower(series_name)=lower(?)",(s[0],))
        if exists.empty:
            run("INSERT INTO content_series(series_name,description,audience,tone,default_format,active,created_at) VALUES(?,?,?,?,?,'Yes',?)",(*s,now()))

def generate_repurposing_assets(title, summary, category, series_name):
    title=safe(title)
    summary=safe(summary)
    category=safe(category,'House Of Wax')
    series_name=safe(series_name,'Wax 101')
    tag=category.replace(' ','').replace('&','')
    short_caption=f"{title}\n\nHouse Of Wax note: {summary}\n\n#{tag} #HouseOfWax #MusicCulture #VinylCommunity"
    reel_script=f"Hook: Here is something every House Of Wax collector should know about {title}.\n\nPoint 1: {summary}\n\nPoint 2: Slow down, verify details, and learn the language before you buy.\n\nClose: Follow House Of Wax for collecting knowledge, music culture, and marketplace trust."
    newsletter=f"This week in {series_name}: {title}. {summary} Read it in the House Of Wax Knowledge Hub."
    marketplace=f"Related marketplace reminder: use this knowledge when reviewing listings, condition notes, catalog details, and seller information."
    return short_caption, reel_script, newsletter, marketplace


def content_admin():
    seed_knowledge()
    seed_content_series()
    header()
    st.header('House Of Wax Content Admin')
    st.write('Create House Of Wax educational content only. This is for teaching and brand authority, not seller promotion.')
    tabs=st.tabs(['Article creator','Glossary builder','Social copy generator','Draft library','Content calendar','Reports','Instagram Posting','YouTube Posting','Facebook Posting'])
    with tabs[0]:
        with st.form('knowledge_article_form'):
            title=st.text_input('Article title')
            category=st.selectbox('Category',KNOWLEDGE_CATEGORIES)
            audience=st.selectbox('Audience',['Beginners','Collectors','Buyers','Sellers','Everyone'])
            level=st.selectbox('Level',['Beginner','Intermediate','Advanced'])
            summary=st.text_area('Short plain-English summary')
            body=st.text_area('Full educational article')
            tip=st.text_area('House Of Wax tip')
            img_file=st.file_uploader('Optional image',type=['png','jpg','jpeg','webp'])
            img_url=st.text_input('Or image URL')
            video_url=st.text_input('Optional video URL (YouTube or other video link)')
            status=st.selectbox('Status',['Draft','Published'])
            featured=st.selectbox('Featured',['No','Yes'])
            submitted=st.form_submit_button('Save education article')
        if submitted:
            img=save_file(img_file,'knowledge_images') or img_url
            data={'title':title,'category':category,'audience':audience,'level':level,'summary':summary,'body':body,'house_tip':tip,'image_url':img,'video_url':safe(video_url).strip(),'status':status,'featured':featured,'created_at':now(),'updated_at':now()}
            new_id=core_insert('knowledge_posts',data,"""INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,image_url,video_url,status,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",tuple(data[k] for k in ['title','category','audience','level','summary','body','house_tip','image_url','video_url','status','featured','created_at','updated_at']))
            if new_id or not hosted_enabled():
                st.success('Knowledge article saved.')
            else:
                st.error('Knowledge article could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
        st.dataframe(table('knowledge_posts'),width='stretch')
    with tabs[1]:
        with st.form('glossary_form'):
            term=st.text_input('Term')
            category=st.text_input('Category',value='Record collecting')
            definition=st.text_area('Plain-English definition')
            why=st.text_area('Why it matters')
            example=st.text_area('Example')
            status=st.selectbox('Status',['Published','Draft'])
            submitted=st.form_submit_button('Save glossary term')
        if submitted:
            clean_term=safe(term).strip()
            data={'term':clean_term,'category':category,'plain_definition':definition,'why_it_matters':why,'example':example,'status':status,'updated_at':now()}
            existing=hosted_select('glossary_terms',{'term':clean_term},limit=1) if hosted_enabled() else df('SELECT id FROM glossary_terms WHERE lower(term)=lower(?)',(clean_term,))
            if not existing.empty:
                ok=core_update('glossary_terms',data,{'id':int(existing.iloc[0]['id'])},'UPDATE glossary_terms SET term=?,category=?,plain_definition=?,why_it_matters=?,example=?,status=?,updated_at=? WHERE id=?',(clean_term,category,definition,why,example,status,now(),int(existing.iloc[0]['id'])))
            else:
                data['created_at']=now()
                ok=core_insert('glossary_terms',data,"""INSERT INTO glossary_terms(term,category,plain_definition,why_it_matters,example,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",tuple(data[k] for k in ['term','category','plain_definition','why_it_matters','example','status','created_at','updated_at']))
            if ok or not hosted_enabled():
                st.success('Glossary term saved.')
            else:
                st.error('Glossary term could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
        st.dataframe(table('glossary_terms'),width='stretch')
    with tabs[2]:
        posts=table('knowledge_posts')
        if posts.empty: st.info('Create an article first.')
        else:
            pid=st.selectbox('Choose education article',posts['id'].tolist())
            post=posts[posts['id']==pid].iloc[0]
            pack=make_social_pack(post['title'],post['category'],post['summary'],post['body'],post['house_tip'])
            platform=st.selectbox('Save draft for platform',['Instagram','TikTok/Reels','Facebook','YouTube Shorts','Email/Newsletter','In-App'])
            for k,v in pack.items():
                st.markdown(f'**{k}**')
                st.text_area(k,v,height=140,key=f"admin_pack_{k}")
            if st.button('Save social draft for House Of Wax'):
                run("""INSERT INTO content_drafts(source_type,source_id,title,platform,caption,script,hashtags,cta,status,created_at,updated_at) VALUES('Knowledge Article',?,?,?,?,?,?,?,'Draft',?,?)""",
                    (int(pid),safe(post['title']),platform,pack['Instagram/Facebook caption'],pack['Short-form video script'],pack['Hashtags'],pack['CTA'],now(),now()))
                st.success('Draft saved.')
    with tabs[3]:
        drafts=table('content_drafts')
        st.dataframe(drafts,width='stretch')
        if not drafts.empty:
            did=st.selectbox('Draft ID',drafts['id'].tolist())
            status=st.selectbox('Draft status',['Draft','Ready','Posted','Archived'])
            if st.button('Update draft status'):
                run('UPDATE content_drafts SET status=?,updated_at=? WHERE id=?',(status,now(),int(did))); st.success('Draft updated.')
    with tabs[4]:
        with st.form('calendar_form'):
            ctype=st.selectbox('Content type',['Article','Short-form video','Instagram post','Facebook post','Email','In-app feature'])
            topic=st.text_input('Topic')
            platform=st.selectbox('Platform',['House Of Wax App','Instagram','TikTok','YouTube Shorts','Facebook','Email'])
            pdate=st.text_input('Planned date')
            status=st.selectbox('Status',['Planned','Drafting','Ready','Posted'])
            notes=st.text_area('Notes')
            submitted=st.form_submit_button('Add to calendar')
        if submitted:
            run("""INSERT INTO content_calendar(content_type,topic,platform,planned_date,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                (ctype,topic,platform,pdate,status,notes,now(),now()))
            st.success('Calendar item saved.')
        st.dataframe(table('content_calendar'),width='stretch')
    with tabs[5]:
        rep=st.selectbox('Content report',['knowledge_posts','glossary_terms','content_drafts','content_calendar','homepage_blocks','quick_tips','did_you_know','newsletter_signups'])
        data=table(rep)
        st.dataframe(data,width='stretch')
        st.download_button('Download CSV',data.to_csv(index=False),file_name=f'{rep}.csv')
    with tabs[6]:
        st.subheader('Post to Instagram')
        if not instagram_configured():
            st.warning('Instagram is not connected yet. Add INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID in Secrets.')
        else:
            st.caption('Posts go live immediately on the connected @shophouseofwax account.')
            source=st.radio('Image source',['Paste an image URL','Use a knowledge article image','Use a product listing image'],horizontal=True,key='ig_source')
            image_url=''
            default_caption=''
            if source=='Paste an image URL':
                image_url=st.text_input('Image URL',key='ig_manual_image_url').strip()
            elif source=='Use a knowledge article image':
                posts=table('knowledge_posts')
                posts=posts[posts['image_url'].astype(str).str.len()>0] if not posts.empty else posts
                if posts.empty:
                    st.info('No knowledge articles with images yet.')
                else:
                    pid=st.selectbox('Choose article',posts['id'].tolist(),format_func=lambda i: safe(posts[posts['id']==i].iloc[0]['title']) or f'Article {i}',key='ig_article_pick')
                    post=posts[posts['id']==pid].iloc[0]
                    image_url=safe(post['image_url'])
                    pack=make_social_pack(post['title'],post['category'],post['summary'],post['body'],post['house_tip'])
                    default_caption=pack['Instagram/Facebook caption']
            else:
                prods=table('products')
                if not prods.empty:
                    prods=prods[prods['listing_status'].isin(PUBLIC_LISTING_STATUSES) & (prods['image_url'].astype(str).str.len()>0)]
                if prods.empty:
                    st.info('No live listings with images yet.')
                else:
                    prid=st.selectbox('Choose listing',prods['id'].tolist(),format_func=lambda i: (safe(prods[prods['id']==i].iloc[0]['artist'])+' — '+safe(prods[prods['id']==i].iloc[0]['title'])).strip(' —') or f'Listing {i}',key='ig_product_pick')
                    prod=prods[prods['id']==prid].iloc[0]
                    image_url=safe(prod['image_url'])
                    default_caption=f"{safe(prod['artist'])} — {safe(prod['title'])}\n\n{safe(prod['description'])[:200]}\n\nFind it on House Of Wax.\n\n#HouseOfWax #VinylCommunity #RecordCollecting"
            if image_url:
                safe_image(image_url,width='stretch',fallback_text='Image preview unavailable.')
            caption=st.text_area('Caption',value=default_caption,height=160,key='ig_caption_box')
            if st.button('Post to Instagram now',disabled=not image_url):
                ok,result=post_to_instagram(image_url,caption)
                if ok:
                    st.success('Posted to Instagram.')
                    permalink=fetch_instagram_permalink(result)
                    if permalink:
                        st.markdown(f'[View the post]({permalink})')
                else:
                    st.error(result)
    with tabs[7]:
        st.subheader('Upload to YouTube')
        if not youtube_configured():
            st.warning('YouTube is not connected yet. Add YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN in Secrets.')
        else:
            st.caption("Uploads default to Private. YouTube will likely reject Public until this API project passes Google's compliance audit -- the connection itself is ready and will not need to be redone once that's approved.")
            video_file=st.file_uploader('Video file',type=['mp4','mov','m4v','webm'],key='yt_video_file')
            yt_title=st.text_input('Video title',key='yt_title')
            yt_description=st.text_area('Video description',key='yt_description',height=120)
            yt_privacy=st.selectbox('Visibility',['private','unlisted','public'],key='yt_privacy',help='Public will likely be rejected by YouTube until the app passes Google\'s audit.')
            if st.button('Upload to YouTube',disabled=not(video_file and yt_title)):
                with st.spinner('Uploading to YouTube...'):
                    ok,result=upload_video_to_youtube(video_file.getvalue(),safe(video_file.type) or 'video/mp4',yt_title,yt_description,yt_privacy)
                if ok:
                    st.success('Uploaded to YouTube.')
                    st.markdown(f'[View the video](https://youtu.be/{result})')
                else:
                    st.error(result)
    with tabs[8]:
        st.subheader('Post to Facebook')
        if not facebook_configured():
            st.warning('Facebook is not connected yet. Add FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID in Secrets.')
        else:
            st.caption('Posts go live immediately on the connected House Of Wax Facebook Page.')
            fb_source=st.radio('Image source',['No image (text post)','Paste an image URL','Use a knowledge article image','Use a product listing image'],horizontal=True,key='fb_source')
            fb_image_url=''
            fb_default_message=''
            if fb_source=='Paste an image URL':
                fb_image_url=st.text_input('Image URL',key='fb_manual_image_url').strip()
            elif fb_source=='Use a knowledge article image':
                fb_posts=table('knowledge_posts')
                fb_posts=fb_posts[fb_posts['image_url'].astype(str).str.len()>0] if not fb_posts.empty else fb_posts
                if fb_posts.empty:
                    st.info('No knowledge articles with images yet.')
                else:
                    fb_pid=st.selectbox('Choose article',fb_posts['id'].tolist(),format_func=lambda i: safe(fb_posts[fb_posts['id']==i].iloc[0]['title']) or f'Article {i}',key='fb_article_pick')
                    fb_post=fb_posts[fb_posts['id']==fb_pid].iloc[0]
                    fb_image_url=safe(fb_post['image_url'])
                    fb_pack=make_social_pack(fb_post['title'],fb_post['category'],fb_post['summary'],fb_post['body'],fb_post['house_tip'])
                    fb_default_message=fb_pack['Facebook educational post']
            elif fb_source=='Use a product listing image':
                fb_prods=table('products')
                if not fb_prods.empty:
                    fb_prods=fb_prods[fb_prods['listing_status'].isin(PUBLIC_LISTING_STATUSES) & (fb_prods['image_url'].astype(str).str.len()>0)]
                if fb_prods.empty:
                    st.info('No live listings with images yet.')
                else:
                    fb_prid=st.selectbox('Choose listing',fb_prods['id'].tolist(),format_func=lambda i: (safe(fb_prods[fb_prods['id']==i].iloc[0]['artist'])+' — '+safe(fb_prods[fb_prods['id']==i].iloc[0]['title'])).strip(' —') or f'Listing {i}',key='fb_product_pick')
                    fb_prod=fb_prods[fb_prods['id']==fb_prid].iloc[0]
                    fb_image_url=safe(fb_prod['image_url'])
                    fb_default_message=f"{safe(fb_prod['artist'])} — {safe(fb_prod['title'])}\n\n{safe(fb_prod['description'])[:200]}\n\nFind it on House Of Wax."
            if fb_image_url:
                safe_image(fb_image_url,width='stretch',fallback_text='Image preview unavailable.')
            fb_message=st.text_area('Message',value=fb_default_message,height=140,key='fb_message_box')
            if st.button('Post to Facebook now',disabled=not(fb_message.strip() or fb_image_url)):
                ok,result=post_to_facebook_page(fb_message,fb_image_url)
                if ok:
                    st.success('Posted to Facebook.')
                    st.markdown(f'[View the post](https://facebook.com/{result})')
                else:
                    st.error(result)


# ---------- V18 Home + Editorial Experience ----------
def seed_homepage_editorial():
    seed_knowledge()
    if hosted_enabled():
        return
    if table('homepage_blocks').empty:
        blocks=[
            ('hero','House Of Wax','Music. Culture. Collecting. Community.','Discover the stories, sounds, formats, and knowledge behind the music you collect. House Of Wax is where marketplace trust meets music culture education.','Visit Knowledge Hub','Knowledge Hub','Active',1),
            ('featured_story','What Does VG+ Really Mean?','Featured Story','VG+ does not mean perfect. It means the record has been played but should still sound strong, with only light signs of use. Before you buy used vinyl, learn what grades actually mean.','Read the Guide','Knowledge Hub','Active',2),
            ('weekly_focus','This Week at House Of Wax','Matrix / Runout','The small letters and numbers etched near the center of a record can tell a big story. Matrix and runout information can help identify pressings, mastering details, and release versions.','Learn About Runouts','Knowledge Hub','Active',3),
            ('genre_spotlight','Southern Soul Essentials','Genre / Era Spotlight','Southern soul is more than a sound. It carries church roots, regional storytelling, blues influence, deep vocals, and a sense of place.','Explore Spotlight','Knowledge Hub','Active',4),
            ('editorial_pick','Format Focus: Why Cassettes Still Matter','House Of Wax Editorial Pick','Cassettes are portable, imperfect, personal, and deeply tied to mixtape culture. Their return is not just nostalgia — it is about physical connection.','Read More','Knowledge Hub','Active',5),
            ('newsletter','Join House Of Wax','Join the Culture','Get collector tips, music culture stories, grading guides, and marketplace education from House Of Wax.','Join the List','Newsletter','Active',6)
        ]
        for b in blocks:
            run("INSERT INTO homepage_blocks(block_name,title,subtitle,body,button_text,button_target,status,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(*b,now(),now()))
    if table('quick_tips').empty:
        for tip,cat in [
            ('A barcode can help identify a reissue, but it does not tell the whole story.','Barcode, Catalog & Matrix Guides'),
            ('A clean sleeve does not always mean the record is clean. Check both media and sleeve grades.','Vinyl Grading School'),
            ('Original pressings are not always the best sounding version. Research matters.','Record Collecting 101'),
            ('A promo copy can be collectible, but condition and demand still matter.','Record Collecting 101'),
            ('If a rare record is priced too low, slow down and verify the details.','How to Buy Safely')]:
            run("INSERT INTO quick_tips(tip_text,category,status,created_at,updated_at) VALUES(?,?,'Active',?,?)",(tip,cat,now(),now()))
    if table('did_you_know').empty:
        for fact,cat in [
            ('The matrix/runout area of a record can sometimes help identify the pressing plant, mastering engineer, or version.','Barcode, Catalog & Matrix Guides'),
            ('VG+ is one of the most common collector grades, but it still allows minor signs of use.','Vinyl Grading School'),
            ('Some reissues are highly respected by collectors, especially when they are well mastered and clearly documented.','Spotting Bootlegs and Reissues'),
            ('Music memorabilia can carry cultural value even when it is not rare.','Music History & Culture')]:
            run("INSERT INTO did_you_know(fact_text,category,status,created_at,updated_at) VALUES(?,?,'Active',?,?)",(fact,cat,now(),now()))

def home_block(name):
    r=hosted_select('homepage_blocks',{'block_name':name,'status':'Active'},order='sort_order.asc,id.asc',limit=1) if hosted_enabled() else df("SELECT * FROM homepage_blocks WHERE block_name=? AND status='Active' ORDER BY sort_order,id LIMIT 1",(name,))
    return {} if r.empty else r.iloc[0].to_dict()

def mini_card(title,subtitle,body,video_url=''):
    with st.container(border=True):
        st.caption(safe(subtitle))
        st.subheader(safe(title))
        st.write(safe(body))
        if safe(video_url):
            try:
                st.video(safe(video_url))
            except Exception:
                st.caption('Video could not be loaded from the link provided.')

def home():
    seed_homepage_editorial()
    header()
    marketplace_context('House Of Wax Marketplace → Home')
    hero=home_block('hero')
    st.markdown(f'''
    <div class="how-hero">
        <div class="how-kicker">House Of Wax</div>
        <div class="how-title">{safe(hero.get('title'),'House Of Wax')}</div>
        <div class="how-subtitle">{safe(hero.get('subtitle'),'Music. Culture. Collecting. Community.')}</div>
        <div class="how-body">{safe(hero.get('body'),'Discover records, learn the culture, and collect smarter.')}</div>
        <div class="how-callout">A marketplace with a built-in culture magazine — built to help people collect smarter and understand the story behind the music.</div>
    </div>
    ''', unsafe_allow_html=True)
    a,b,c=st.columns(3)
    if a.button('Explore Marketplace'): request_marketplace_navigation('Search Music'); st.rerun()
    if b.button('Visit Knowledge Hub'): request_marketplace_navigation('Knowledge Hub'); st.rerun()
    if c.button("Read This Week's Feature"): request_marketplace_navigation('Knowledge Hub'); st.rerun()
    render_liveavatar_widget()
    with st.expander('Tester Start Here',expanded=True):
        tester_start_here('home')
    st.info('Looking for music? Open Search Music and type an artist or album name.')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Knowledge Articles',len(table('knowledge_posts')))
    c2.metric('Glossary Terms',len(table('glossary_terms')))
    c3.metric('Marketplace Items',len(table('products')))
    c4.metric('Community Posts',len(table('culture_posts')))
    groove_divider()
    x=home_block('featured_story'); mini_card(x.get('title','What Does VG+ Really Mean?'),x.get('subtitle','This Week at House Of Wax'),x.get('body','Learn grading before you buy.'),x.get('video_url',''))

    section_header('Learn the Culture','Start with the basics or go deeper into pressings, grading, formats, trust, and music history.','Education + Discovery')
    with st.container(border=True):
        st.subheader('Everything you need to collect smarter, in one place')
        st.write('Record collecting basics, grading, barcodes and matrix numbers, bootlegs and reissues, care and storage, genre history, and House Of Wax trust standards all live inside the Knowledge Hub.')
        if st.button('Visit the Knowledge Hub',key='learn_culture_cta',width='stretch'):
            request_marketplace_navigation('Knowledge Hub'); st.rerun()
    groove_divider()
    q,d=st.columns(2)
    with q:
        section_header('Collector Quick Tips','Useful knowledge in seconds.','Collect Smarter')
        tips=hosted_select('quick_tips',{'status':'Active'},order='id.asc',limit=5) if hosted_enabled() else df("SELECT * FROM quick_tips WHERE status='Active' ORDER BY id LIMIT 5")
        for _,tip in tips.iterrows(): st.write(f"• {safe(tip['tip_text'])}")
    with d:
        section_header('Did You Know?','Fast facts from House Of Wax.','Quick Culture')
        facts=hosted_select('did_you_know',{'status':'Active'},order='id.asc',limit=4) if hosted_enabled() else df("SELECT * FROM did_you_know WHERE status='Active' ORDER BY id LIMIT 4")
        for _,fact in facts.iterrows(): mini_card('Did you know?',safe(fact['category']),safe(fact['fact_text']))
    groove_divider()
    x=home_block('genre_spotlight'); mini_card(x.get('title','Southern Soul Essentials'),x.get('subtitle','Culture Spotlight'),x.get('body','Explore the sound, labels, artists, and culture.'),x.get('video_url',''))
    groove_divider()
    section_header('Latest From the Knowledge Hub','House Of Wax education, culture, and collecting guides.','Read + Learn')
    posts=hosted_select('knowledge_posts',{'status':'Published'},order='updated_at.desc',limit=6) if hosted_enabled() else df("SELECT * FROM knowledge_posts WHERE status='Published' ORDER BY updated_at DESC LIMIT 6")
    cols=st.columns(3)
    for i,(_,post) in enumerate(posts.iterrows()):
        with cols[i%3]: knowledge_card(post, f'home_latest_{i}')
    groove_divider()
    news=home_block('newsletter')
    st.markdown(f"## {safe(news.get('title'),'Join House Of Wax')}")
    st.write(safe(news.get('body'),'Get collector tips, music culture stories, grading guides, and marketplace education from House Of Wax.'))
    n1,n2,n3=st.columns([1,1,1])
    name=n1.text_input('Name',key='newsletter_name')
    email=n2.text_input('Email',key='newsletter_email')
    if n3.button('Join the List'):
        if not safe(email): st.warning('Enter an email first.')
        else:
            data={'email':email,'name':name,'source':'Homepage','created_at':now(),'updated_at':now()}
            new_id=core_insert('newsletter_signups',data,"INSERT INTO newsletter_signups(email,name,source,created_at,updated_at) VALUES(?,?,?,?,?)",tuple(data[k] for k in ['email','name','source','created_at','updated_at']))
            if new_id or not hosted_enabled():
                send_newsletter_welcome_email(email,name)
                st.success('You are on the House Of Wax list.')
            else:
                st.error('Signup could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))

def homepage_editor():
    seed_homepage_editorial()
    st.subheader('Homepage Editor')
    tabs=st.tabs(['Homepage Blocks','Quick Tips','Did You Know','Newsletter Signups'])
    with tabs[0]:
        st.dataframe(table('homepage_blocks'),width='stretch')
        with st.form('home_block_form'):
            bn=st.selectbox('Block',['hero','featured_story','weekly_focus','genre_spotlight','editorial_pick','newsletter'])
            title=st.text_input('Title'); sub=st.text_input('Subtitle'); body=st.text_area('Body')
            btn=st.text_input('Button text'); target=st.text_input('Button target')
            video_url=st.text_input('Optional video URL (YouTube or other video link)')
            status=st.selectbox('Status',['Active','Draft','Hidden'])
            order=st.number_input('Sort order',min_value=0,value=1)
            if st.form_submit_button('Save homepage block'):
                data={'block_name':bn,'title':title,'subtitle':sub,'body':body,'button_text':btn,'button_target':target,'video_url':safe(video_url).strip(),'status':status,'sort_order':int(order),'created_at':now(),'updated_at':now()}
                new_id=core_insert('homepage_blocks',data,"INSERT INTO homepage_blocks(block_name,title,subtitle,body,button_text,button_target,video_url,status,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",tuple(data[k] for k in ['block_name','title','subtitle','body','button_text','button_target','video_url','status','sort_order','created_at','updated_at']))
                if new_id or not hosted_enabled():
                    st.success('Homepage block saved.')
                else:
                    st.error('Homepage block could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[1]:
        st.dataframe(table('quick_tips'),width='stretch')
        with st.form('tip_form'):
            tip=st.text_area('Quick tip'); cat=st.text_input('Category')
            status=st.selectbox('Status',['Active','Draft','Hidden'],key='tip_status')
            if st.form_submit_button('Save quick tip'):
                data={'tip_text':tip,'category':cat,'status':status,'created_at':now(),'updated_at':now()}
                new_id=core_insert('quick_tips',data,"INSERT INTO quick_tips(tip_text,category,status,created_at,updated_at) VALUES(?,?,?,?,?)",tuple(data[k] for k in ['tip_text','category','status','created_at','updated_at']))
                if new_id or not hosted_enabled():
                    st.success('Quick tip saved.')
                else:
                    st.error('Quick tip could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[2]:
        st.dataframe(table('did_you_know'),width='stretch')
        with st.form('fact_form'):
            fact=st.text_area('Fact'); cat=st.text_input('Category',key='fact_cat')
            status=st.selectbox('Status',['Active','Draft','Hidden'],key='fact_status')
            if st.form_submit_button('Save fact'):
                data={'fact_text':fact,'category':cat,'status':status,'created_at':now(),'updated_at':now()}
                new_id=core_insert('did_you_know',data,"INSERT INTO did_you_know(fact_text,category,status,created_at,updated_at) VALUES(?,?,?,?,?)",tuple(data[k] for k in ['fact_text','category','status','created_at','updated_at']))
                if new_id or not hosted_enabled():
                    st.success('Fact saved.')
                else:
                    st.error('Fact could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[3]:
        data=table('newsletter_signups')
        st.dataframe(data,width='stretch')
        if not data.empty:
            st.download_button('Download newsletter signups',data.to_csv(index=False),file_name='newsletter_signups.csv')

def test_setup():
    header(); admin_context('House Of Wax Admin → Test Setup'); st.header('Test setup')
    if st.button('Create/repair demo buyer, seller, and product'): st.success(f'Demo ready: buyer/seller/product IDs {seed_all()}')
    st.code('Buyer: buyer@test.com\nSeller: seller@test.com')
    st.subheader('Buyers'); st.dataframe(table('buyers'),width='stretch'); st.subheader('Sellers'); st.dataframe(table('sellers'),width='stretch'); st.subheader('Products'); st.dataframe(table('products'),width='stretch')
def marketplace():
    header(); marketplace_context('House Of Wax Marketplace → Search Music'); st.header('Search Music')
    st.write('Type an artist or album name to search all sellers.')
    st.caption('Search all live listings from House Of Wax sellers.')
    with st.expander('Tester Feedback for this page',expanded=False):
        tester_feedback_form('marketplace')
    if 'seller_id' in st.session_state: seller_profile(int(st.session_state['seller_id'])); return
    if 'product_id' in st.session_state: product_detail(int(st.session_state['product_id'])); return
    prods=load_global_marketplace_listings()
    if prods.empty:
        all_products=table('products')
        if all_products.empty:
            st.info("Nothing's live yet. If you're a seller, be the first to add something in Seller Tools.")
        else:
            st.info("Nothing's live for buyers to see right now — check back soon.")
            if is_admin_unlocked():
                statuses=', '.join([f"{safe(k)}: {int(v)}" for k,v in all_products['listing_status'].fillna('Blank').value_counts().items()])
                st.caption('Admin note: current listing statuses: '+safe(statuses,'none')+'. To make a listing appear, open My House of Wax, choose Seller role, open Seller Dashboard, select an approved seller, and Publish to My Store from Add Inventory or My Inventory.')
        return
    q=st.text_input('Search by artist or album',placeholder="Example: Marvin Gaye or What's Going On",help='Search all live listings from House Of Wax sellers.',key='global_marketplace_search')
    category='All'
    fmt='All'
    condition='All'
    seller_filter='All'
    location=''
    min_price=''
    max_price=''
    sort_by='Newest'
    with st.expander('More filters',expanded=False):
        st.caption('Optional. Leave filters blank to see all matching listings.')
        f1,f2,f3=st.columns(3)
        categories=['All']+sorted([safe(x) for x in prods['category'].dropna().unique().tolist() if safe(x)])
        formats=['All']+sorted([safe(x) for x in prods['format'].dropna().unique().tolist() if safe(x)])
        conditions=['All conditions']+sorted(set([safe(x) for col in ['media_grade','sleeve_grade'] if col in prods.columns for x in prods[col].dropna().unique().tolist() if safe(x)]))
        category=f1.selectbox('Category',categories,index=0,key='simple_marketplace_category')
        fmt=f2.selectbox('Format',formats,index=0,key='simple_marketplace_format')
        condition_choice=f3.selectbox('Condition',conditions,index=0,key='simple_marketplace_condition')
        condition='All' if condition_choice=='All conditions' else condition_choice
        f4,f5,f6=st.columns(3)
        sellers=['All']+sorted([safe(x) for x in prods['store_name'].dropna().unique().tolist() if safe(x)])
        seller_filter=f4.selectbox('Seller/store',sellers,index=0,key='simple_marketplace_seller')
        location=f5.text_input('Location',placeholder='Leave blank',key='simple_marketplace_location')
        sort_by=f6.selectbox('Sort',['Newest','Price low to high','Price high to low','Artist/title A-Z'],key='simple_marketplace_sort')
        p1,p2=st.columns(2)
        min_price=p1.text_input('Minimum price',placeholder='Leave blank',key='simple_marketplace_min_price')
        max_price=p2.text_input('Maximum price',placeholder='Leave blank',key='simple_marketplace_max_price')
    prods=filter_global_marketplace_listings(prods,q,category,fmt,condition,seller_filter,location,min_price,max_price,sort_by)
    seller_count=prods['store_name'].fillna('').replace('',pd.NA).dropna().nunique() if not prods.empty and 'store_name' in prods.columns else 0
    st.caption(f'Showing {len(prods)} live listing{"s" if len(prods)!=1 else ""} from {seller_count} seller{"s" if seller_count!=1 else ""}')
    if prods.empty:
        st.info('No matching live listings found. Try a different artist, title, barcode, or seller name.')
        return
    cols=st.columns(2)
    for i,(_,p) in enumerate(prods.iterrows()):
        with cols[i%2]: product_card(p)
def seller_stores():
    header(); marketplace_context('House Of Wax Marketplace → Seller Stores'); st.header('Seller Stores')
    st.write('Browse individual stores and see what each seller has available.')
    if 'seller_id' in st.session_state: seller_profile(int(st.session_state['seller_id'])); return
    sellers=table('sellers')
    if sellers.empty: st.info('No sellers yet.'); return
    for _,s in sellers.iterrows():
        with st.container(border=True):
            if safe(s['banner_url']): safe_image(safe(s['banner_url']),width='stretch',fallback_text='Banner image unavailable.')
            st.subheader(safe(s['store_name']))
            public_seller_trust_badge(s)
            st.caption(f"Rating {s['rating']}% • Followers {followers(int(s['id']))}")
            st.write(safe(s['store_bio']))
            if badges(int(s['id'])): st.info('Badges: '+badges(int(s['id'])))
            if st.button('Open public profile',key=f"openseller{int(s['id'])}"): st.session_state['seller_id']=int(s['id']); st.rerun()
def buyer_workspace_tabs(bid):
    # The reachable home for a signed-in buyer's own profile, inquiries,
    # purchase requests, and Want List -- called directly from account_page()'s
    # Buying tab. This used to only be reachable through buyer_dashboard() via
    # a "My House of Wax" navigation target that was never actually wired
    # into the live sidebar menu, silently stranding every signed-in buyer.
    st.session_state['buyer_id']=bid
    b=get_buyer(bid)
    if b is None:
        st.error('Linked buyer profile was not found.')
        return
    tabs=st.tabs(['My Profile','My Inquiries','My Purchase Requests','My Want List'])
    with tabs[0]:
        with st.form('bp_auth'):
            name=st.text_input('Name',value=safe(b['name']))
            phone=st.text_input('Phone',value=safe(b.get('phone')))
            city=st.text_input('City',value=safe(b.get('city')))
            state=st.text_input('State',value=safe(b.get('state')))
            bio=st.text_area('Bio',value=safe(b['bio']))
            sub=st.form_submit_button('Save buyer profile')
        if sub:
            AUTH_STATUS['last_buyer_save_error']=''
            ok=core_update('buyers',{'name':name,'phone':phone,'city':city,'state':state,'bio':bio},{'id':bid},'UPDATE buyers SET name=?,phone=?,city=?,state=?,bio=? WHERE id=?',(name,phone,city,state,bio,bid))
            reloaded=get_buyer(bid)
            if ok and reloaded is not None:
                st.success('Buyer profile saved and reloaded.')
                st.write(f"Saved profile: {safe(reloaded.get('name'))} | {safe(reloaded.get('email'))}")
            else:
                AUTH_STATUS['last_buyer_save_error']=safe(SUPABASE_STATUS.get('last_error'),'Buyer profile save failed.')
                st.error('Buyer profile did not save. Supabase error: '+AUTH_STATUS['last_buyer_save_error'])
    inquiries,purchases=buyer_activity_tables(bid)
    with tabs[1]:
        st.subheader('My Inquiries')
        if inquiries.empty:
            st.info('No questions sent yet.')
        else:
            cols=[c for c in ['id','store_name','artist','title','preferred_contact_method','message','status','created_at'] if c in inquiries.columns]
            st.dataframe(inquiries[cols],width='stretch')
    with tabs[2]:
        st.subheader('My Purchase Requests')
        if purchases.empty:
            st.info('No purchase requests sent yet.')
        else:
            cols=[c for c in ['id','store_name','artist','title','fulfillment_preference','offer_price','buyer_message','status','created_at'] if c in purchases.columns]
            st.dataframe(purchases[cols],width='stretch')
            countered=purchases[purchases['status']=='Seller Countered'] if 'status' in purchases.columns else purchases.iloc[0:0]
            if not countered.empty:
                st.markdown('#### Seller counter-offers awaiting your response')
                for _,cr in countered.iterrows():
                    crid=int(cr['id'])
                    with st.container(border=True):
                        st.write(f"**{safe(cr.get('artist'))} — {safe(cr.get('title'))}** from {safe(cr.get('store_name'))}")
                        st.write(f"Your offer: {money(cr.get('offer_price'))} → Seller's counter: {money(cr.get('counter_price'))}")
                        if safe(cr.get('counter_message')):
                            st.caption(safe(cr.get('counter_message')))
                        cc1,cc2=st.columns(2)
                        if cc1.button('Accept Counter',key=f'buyer_accept_counter_{crid}',width='stretch'):
                            core_update('purchase_requests',{'status':'Seller Accepted','offer_price':float(cr.get('counter_price') or 0),'updated_at':now()},{'id':crid},'UPDATE purchase_requests SET status=?,offer_price=?,updated_at=? WHERE id=?',('Seller Accepted',float(cr.get('counter_price') or 0),now(),crid))
                            st.success('Counter accepted. The seller will follow up on pickup/payment.')
                            st.rerun()
                        if cc2.button('Decline Counter',key=f'buyer_decline_counter_{crid}',width='stretch'):
                            core_update('purchase_requests',{'status':'Closed','updated_at':now()},{'id':crid},'UPDATE purchase_requests SET status=?,updated_at=? WHERE id=?',('Closed',now(),crid))
                            st.info('Counter declined.')
                            st.rerun()
            sold=purchases[purchases['status']=='Sold'] if 'status' in purchases.columns else purchases.iloc[0:0]
            to_review=sold[~sold['id'].apply(lambda i: buyer_already_reviewed(int(i)))] if not sold.empty else sold
            if not to_review.empty:
                st.markdown('#### Leave a review')
                for _,sr in to_review.iterrows():
                    srid=int(sr['id'])
                    with st.container(border=True):
                        st.write(f"**{safe(sr.get('artist'))} — {safe(sr.get('title'))}** from {safe(sr.get('store_name'))}")
                        with st.form(f'review_form_{srid}'):
                            rating=st.slider('Rating',1,5,5,key=f'review_rating_{srid}')
                            review_text=st.text_area('Your review - optional',key=f'review_text_{srid}')
                            display_name=st.text_input('Display name shown on your review',value=safe(b.get('name')),key=f'review_name_{srid}')
                            review_submitted=st.form_submit_button('Submit review')
                        if review_submitted:
                            rvid=add_seller_review(sr.get('seller_id'),bid,srid,sr.get('product_id'),rating,review_text,display_name)
                            if rvid or not hosted_enabled():
                                st.success('Review posted. Thank you.')
                                st.rerun()
                            else:
                                st.error('Review could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[3]:
        want_list_manager(bid)

def buyer_dashboard_admin_lookup():
    st.caption('Admin/testing buyer profile inspection is enabled.')
    buyers=table('buyers')
    if buyers.empty:
        st.warning('No profile found yet. Create one from Sell on House Of Wax or use Create/open by email below.')
    else:
        latest=buyers.sort_values('id',ascending=False).head(8)
        st.success('Saved profiles found.')
        st.dataframe(latest[[c for c in ['id','name','email','status','created_at'] if c in latest.columns]],width='stretch')
        active_id=st.session_state.get('buyer_id')
        if active_id:
            active=get_buyer(int(active_id))
            if active is not None:
                st.info(f"Currently active buyer profile: {safe(active.get('name'))} | {safe(active.get('email'))}")
    mode=st.radio('Open buyer by',['Choose existing buyer','Create/open by email'],horizontal=True)
    if mode=='Choose existing buyer':
        bid=buyer_pick('buyerdb',preferred_id=st.session_state.get('buyer_id'))
        st.session_state['buyer_id']=bid
    else:
        email=st.text_input('Buyer email',value='buyer@test.com'); name=st.text_input('Buyer name',value='Test Buyer')
        if st.button('Create/open buyer'):
            bid=create_buyer(email,name)
            if bid:
                st.session_state['buyer_id']=bid
                st.success('Buyer profile saved/opened from the database and set as active.')
            else:
                st.error('Buyer profile could not be saved or reopened. Check System Diagnostics for Supabase errors.')
        existing=hosted_select('buyers',{'email':email.strip().lower()},limit=1) if hosted_enabled() else df('SELECT id FROM buyers WHERE lower(email)=lower(?)',(email.strip(),))
        bid=int(existing.iloc[0]['id']) if not existing.empty else st.session_state.get('buyer_id',ensure_buyer())
    b=get_buyer(bid); st.success(f"Loaded buyer: {safe(b['name'])} | {safe(b['email'])}")
    tabs=st.tabs(['Profile','Inquiries / Purchase Requests','Messages','Following'])
    with tabs[0]:
        with st.form('bp'):
            name=st.text_input('Name',value=safe(b['name']))
            email=st.text_input('Email',value=safe(b['email']))
            phone=st.text_input('Phone',value=safe(b.get('phone')))
            city=st.text_input('City',value=safe(b.get('city')))
            state=st.text_input('State',value=safe(b.get('state')))
            bio=st.text_area('Bio',value=safe(b['bio']))
            sub=st.form_submit_button('Save buyer profile')
        if sub:
            ok=core_update('buyers',{'name':name,'email':email.strip().lower(),'phone':phone,'city':city,'state':state,'bio':bio},{'id':bid},'UPDATE buyers SET name=?,email=?,phone=?,city=?,state=?,bio=? WHERE id=?',(name,email,phone,city,state,bio,bid))
            st.session_state['buyer_id']=bid
            if ok and get_buyer(bid) is not None:
                st.success('Buyer profile saved and reloaded.')
            else:
                AUTH_STATUS['last_buyer_save_error']=safe(SUPABASE_STATUS.get('last_error'),'Buyer profile save failed.')
                st.error('Buyer profile did not save. Supabase error: '+AUTH_STATUS['last_buyer_save_error'])
    with tabs[1]: buyer_request_history(bid)
    with tabs[2]: st.dataframe(df('SELECT * FROM messages WHERE buyer_id=? ORDER BY created_at DESC',(bid,)),width='stretch')
    with tabs[3]:
        follows=hosted_select('seller_followers',{'buyer_id':bid}) if hosted_enabled() else df('SELECT * FROM seller_followers WHERE buyer_id=?',(bid,))
        if follows.empty:
            st.dataframe(follows,width='stretch')
        else:
            sellers_ref=table('sellers')[['id','store_name','rating']].rename(columns={'id':'seller_id'})
            st.dataframe(follows.merge(sellers_ref,on='seller_id',how='left'),width='stretch')

# ---------- V24 Barcode Lookup + Auto-Fill ----------
MUSIC_CATEGORIES=['Vinyl Records','CDs','Cassettes','Albums','Music Releases']
NON_MUSIC_PHOTO_REQUIRED=['Clothing','Music Memorabilia','Culture Goods','House Of Wax Merch','Official Drops','Slipmats & Accessories']

def is_music_category(category):
    return safe(category) in MUSIC_CATEGORIES

def normalize_barcode(code):
    return re.sub(r'[^0-9]', '', safe(code))

def partial_barcode_ready(code, min_digits=5):
    return len(normalize_barcode(code)) >= min_digits

def barcode_match_label(result, artist='', title=''):
    match_type=safe(result.get('_barcode_match_type'))
    if match_type=='exact':
        return 'Strong match'
    if match_type=='partial':
        details=search_match_details(result,artist,title)
        if details['artist_matched'] and details['title_matched']:
            return 'Possible match'
        return 'Broad match'
    return match_confidence_label(result,artist,title)

def mark_barcode_results(results, match_type, fragment=''):
    marked=[]
    for res in results:
        item=dict(res)
        item['_barcode_match_type']=match_type
        if fragment:
            item['_barcode_fragment']=fragment
            if not safe(item.get('barcode')) and match_type=='exact':
                item['barcode']=normalize_barcode(fragment)
        marked.append(item)
    return marked

def seed_listing_media_policy():
    policies=[
        ('Vinyl Records','Barcode/Release image','Optional','Use release cover art from barcode/database lookup by default. Seller may upload actual item photos for condition proof.'),
        ('CDs','Barcode/Release image','Optional','Use release cover art from barcode/database lookup by default. Seller may upload actual item photos.'),
        ('Cassettes','Barcode/Release image','Optional','Use release cover art from barcode/database lookup by default. Seller may upload actual item photos.'),
        ('Clothing','Seller photo','Yes','Seller should upload or enter a real photo of the exact item.'),
        ('Music Memorabilia','Seller photo','Yes','Seller should upload or enter a real photo of the exact item.'),
        ('Culture Goods','Seller photo','Yes','Seller should upload or enter a real photo of the exact item.'),
        ('House Of Wax Merch','Seller or official product image','Yes','Use official product image if standardized; otherwise upload exact item/photo.'),
        ('Official Drops','Seller or official product image','Yes','Use official drop image or seller photo.'),
        ('Slipmats & Accessories','Seller or official product image','Yes','Use official/accessory image or seller photo.')
    ]
    for p in policies:
        exists=df("SELECT id FROM listing_media_policy WHERE category=?",(p[0],))
        if exists.empty:
            run("INSERT INTO listing_media_policy(category,default_image_source,seller_photo_recommended,notes) VALUES(?,?,?,?)",p)

def cache_lookup_result(barcode, result):
    run("""INSERT INTO barcode_lookup_cache(barcode,source,external_id,artist,title,format,label,release_year,country,genre,style,catalog_number,image_url,external_url,raw_summary,created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (barcode, safe(result.get('source')), safe(result.get('external_id')), safe(result.get('artist')), safe(result.get('title')),
         safe(result.get('format')), safe(result.get('label')), safe(result.get('release_year')), safe(result.get('country')),
         safe(result.get('genre')), safe(result.get('style')), safe(result.get('catalog_number')), safe(result.get('image_url')),
         safe(result.get('external_url')), safe(result.get('raw_summary')), now()))

def lookup_musicbrainz_barcode(barcode):
    barcode=normalize_barcode(barcode)
    if not barcode:
        return []
    try:
        url='https://musicbrainz.org/ws/2/release/'
        params={'query':f'barcode:{barcode}','fmt':'json','limit':5}
        headers={'User-Agent':'HouseOfWaxPrototype/1.0 (prototype lookup)'}
        r=requests.get(url,params=params,headers=headers,timeout=8)
        if r.status_code!=200:
            return []
        data=r.json()
        results=[]
        for rel in data.get('releases',[])[:5]:
            artist=''
            credits=rel.get('artist-credit') or []
            if credits:
                parts=[]
                for c in credits:
                    if isinstance(c,dict):
                        if 'artist' in c and isinstance(c['artist'],dict):
                            parts.append(c['artist'].get('name',''))
                        elif 'name' in c:
                            parts.append(c.get('name',''))
                artist=' '.join([p for p in parts if p]).strip()
            label=''
            cat=''
            infos=rel.get('label-info') or []
            if infos:
                first=infos[0] or {}
                label=(first.get('label') or {}).get('name','') if isinstance(first.get('label'),dict) else ''
                cat=first.get('catalog-number','')
            fmt=''
            media=rel.get('media') or []
            if media:
                fmt=media[0].get('format','')
            year=safe(rel.get('date'))[:4]
            rid=safe(rel.get('id'))
            cover=f'https://coverartarchive.org/release/{rid}/front-500' if rid else ''
            ext=f'https://musicbrainz.org/release/{rid}' if rid else ''
            results.append({
                'source':'MusicBrainz','external_id':rid,'artist':artist,'title':safe(rel.get('title')),
                'format':fmt,'label':label,'release_year':year,'country':safe(rel.get('country')),
                'genre':'','style':'','catalog_number':cat,'image_url':cover,'external_url':ext,
                'raw_summary':f"MusicBrainz release match for barcode {barcode}"
            })
        return results
    except Exception:
        return []

def lookup_discogs_barcode(barcode):
    barcode=normalize_barcode(barcode)
    if not barcode:
        return []
    token=''
    try:
        token=st.secrets.get('DISCOGS_TOKEN','')
    except Exception:
        token=''
    if not token:
        return []
    try:
        url='https://api.discogs.com/database/search'
        params={'barcode':barcode,'type':'release','token':token,'per_page':5}
        headers={'User-Agent':'HouseOfWaxPrototype/1.0'}
        r=requests.get(url,params=params,headers=headers,timeout=8)
        if r.status_code!=200:
            return []
        data=r.json()
        results=[]
        for item in data.get('results',[])[:5]:
            title=safe(item.get('title'))
            artist=''
            album=title
            if ' - ' in title:
                artist,album=title.split(' - ',1)
            formats=item.get('format') or []
            labels=item.get('label') or []
            genres=item.get('genre') or []
            styles=item.get('style') or []
            rid=safe(item.get('id'))
            results.append({
                'source':'Discogs','external_id':rid,'artist':artist,'title':album,
                'format':', '.join(formats) if isinstance(formats,list) else safe(formats),
                'label':', '.join(labels) if isinstance(labels,list) else safe(labels),
                'release_year':safe(item.get('year')),'country':safe(item.get('country')),
                'genre':', '.join(genres) if isinstance(genres,list) else safe(genres),
                'style':', '.join(styles) if isinstance(styles,list) else safe(styles),
                'catalog_number':'','image_url':safe(item.get('cover_image')) or safe(item.get('thumb')),
                'external_url':f'https://www.discogs.com/release/{rid}' if rid else '',
                'raw_summary':f"Discogs release match for barcode {barcode}"
            })
        return results
    except Exception:
        return []


def discogs_token_status():
    try:
        token=st.secrets.get('DISCOGS_TOKEN','')
        return bool(token)
    except Exception:
        return False

def resend_configured():
    try:
        return bool(st.secrets.get('RESEND_API_KEY',''))
    except Exception:
        return False

def send_newsletter_welcome_email(email, name):
    greeting=f"Hi {safe(name)}," if safe(name) else "Hi,"
    body_html=f"""<p>{greeting}</p>
<p>You're on the House Of Wax list. Expect collector tips, music culture stories, grading guides, and marketplace updates.</p>
<p>&mdash; House Of Wax</p>"""
    send_email(email,'Welcome to House Of Wax',body_html)

def send_seller_approved_email(email, store_name):
    body_html=f"""<p>Hi,</p>
<p>Good news &mdash; <strong>{html.escape(safe(store_name,'your store'))}</strong> is approved to sell on House Of Wax.</p>
<p>Sign in and open Seller Dashboard to accept the seller rules and start publishing listings.</p>
<p>&mdash; House Of Wax</p>"""
    send_email(email,"You're approved to sell on House Of Wax",body_html)

def add_want(buyer_id, artist, title=''):
    artist=safe(artist).strip()
    if not buyer_id or not artist:
        return 0
    data={'buyer_id':int(buyer_id),'artist':artist,'title':safe(title).strip(),'status':'Active','created_at':now(),'updated_at':now()}
    return core_insert('want_list',data,"""INSERT INTO want_list(buyer_id,artist,title,status,created_at,updated_at) VALUES(?,?,?,?,?,?)""",(data['buyer_id'],data['artist'],data['title'],data['status'],data['created_at'],data['updated_at']))

def buyer_want_list(buyer_id):
    if not buyer_id:
        return pd.DataFrame()
    return hosted_select('want_list',{'buyer_id':buyer_id,'status':'Active'},order='created_at.desc') if hosted_enabled() else df("SELECT * FROM want_list WHERE buyer_id=? AND status='Active' ORDER BY created_at DESC",(buyer_id,))

def remove_want(want_id):
    if hosted_enabled():
        return hosted_delete('want_list',{'id':int(want_id)})
    run('DELETE FROM want_list WHERE id=?',(int(want_id),))
    return True

def want_list_live_matches(artist, title=''):
    # Checked at the moment a buyer adds a want, so they get an immediate
    # answer instead of only finding out the next time something matches.
    artist_clean=safe(artist).strip().lower()
    if not artist_clean:
        return pd.DataFrame()
    live=hosted_select('products',{},in_filters={'listing_status':PUBLIC_LISTING_STATUSES}) if hosted_enabled() else df('SELECT * FROM products')
    if live.empty or 'artist' not in live.columns:
        return pd.DataFrame()
    if not hosted_enabled():
        live=live[live['listing_status'].isin(PUBLIC_LISTING_STATUSES)] if 'listing_status' in live.columns else live
    matches=live[live['artist'].fillna('').str.strip().str.lower()==artist_clean]
    title_clean=safe(title).strip().lower()
    if title_clean and 'title' in matches.columns:
        matches=matches[matches['title'].fillna('').str.strip().str.lower()==title_clean]
    return matches

def find_want_list_matches_for_notify(artist, title=''):
    # Cross-buyer lookup (does this new listing match ANY buyer's want, not
    # just the seller's own) needs to see other buyers' rows despite RLS
    # normally scoping want_list to its owner -- routed through a
    # security-definer RPC (find_want_list_matches) the same way
    # is_admin_user() safely bypasses RLS elsewhere in this app.
    artist_clean=safe(artist).strip()
    if not artist_clean:
        return []
    if hosted_enabled():
        try:
            url,anon=supabase_config()
            r=requests.post(f'{url}/rest/v1/rpc/find_want_list_matches',headers=hosted_headers(),json={'p_artist':artist_clean,'p_title':safe(title).strip()},timeout=10)
            return r.json() if r.status_code==200 and r.content else []
        except Exception:
            return []
    rows=df("SELECT w.buyer_id,b.email,b.name,w.title as want_title FROM want_list w JOIN buyers b ON b.id=w.buyer_id WHERE w.status='Active' AND lower(w.artist)=lower(?) AND (w.title IS NULL OR w.title='' OR lower(w.title)=lower(?))",(artist_clean,safe(title).strip()))
    return rows.to_dict('records') if not rows.empty else []

def send_want_list_match_email(email, name, artist, title_wanted, product):
    greeting=f"Hi {safe(name)}," if safe(name) else "Hi,"
    want_desc=f"{html.escape(safe(artist))} — {html.escape(safe(title_wanted))}" if safe(title_wanted) else html.escape(safe(artist))
    body_html=f"""<p>{greeting}</p>
<p>Something on your House Of Wax Want List just got listed:</p>
<p><strong>{html.escape(safe(product.get('artist')))} — {html.escape(safe(product.get('title')))}</strong><br>
Condition: {html.escape(safe(product.get('media_grade'),'Not listed'))} &bull; Price: {money(product.get('price'))}</p>
<p>You were watching for: {want_desc}</p>
<p>Sign in to House Of Wax and check My Account &rarr; My Want List, or head to Search Music to find it.</p>
<p>&mdash; House Of Wax</p>"""
    send_email(email,f"It's here: {safe(product.get('artist'))} just got listed",body_html)

def notify_want_list_matches(product):
    matches=find_want_list_matches_for_notify(product.get('artist'),product.get('title'))
    for m in matches:
        email=safe(m.get('email'))
        if email:
            send_want_list_match_email(email,safe(m.get('name')),product.get('artist'),m.get('want_title'),product)

def want_list_manager(buyer_id):
    st.subheader('My Want List')
    st.caption("Tell House Of Wax what you're hunting for. We'll email you the moment a matching copy gets listed.")
    with st.form('add_want_form'):
        w_artist=st.text_input('Artist / Brand')
        w_title=st.text_input('Title - optional (leave blank to be notified about anything by this artist)')
        submitted=st.form_submit_button('Add to Want List')
    if submitted:
        if not safe(w_artist).strip():
            st.warning('Artist is required.')
        else:
            wid=add_want(buyer_id,w_artist,w_title)
            if wid or not hosted_enabled():
                st.success(f'Added to your Want List: {safe(w_artist)}'+(f' — {safe(w_title)}' if safe(w_title).strip() else '')+'.')
                existing=want_list_live_matches(w_artist,w_title)
                if not existing.empty:
                    st.info(f"Good news — {len(existing)} matching listing(s) are already live. Check Search Music.")
            else:
                st.error('Could not save to your Want List. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    wants=buyer_want_list(buyer_id)
    if wants.empty:
        st.info('Nothing on your Want List yet.')
        return
    st.markdown('#### Currently watching for')
    for _,w in wants.iterrows():
        wid=int(w['id'])
        with st.container(border=True):
            c1,c2=st.columns([4,1])
            c1.write(f"**{safe(w.get('artist'))}**"+(f" — {safe(w.get('title'))}" if safe(w.get('title')) else " — any title"))
            if c2.button('Remove',key=f'remove_want_{wid}'):
                remove_want(wid)
                st.rerun()

def add_seller_review(seller_id, buyer_id, purchase_request_id, product_id, rating, review_text, buyer_display_name):
    data={'seller_id':int(seller_id),'buyer_id':int(buyer_id),'purchase_request_id':int(purchase_request_id),'product_id':int(product_id) if product_id else None,'rating':int(rating),'review_text':safe(review_text).strip(),'buyer_display_name':safe(buyer_display_name),'created_at':now(),'updated_at':now()}
    return core_insert('seller_reviews',data,"""INSERT INTO seller_reviews(seller_id,buyer_id,purchase_request_id,product_id,rating,review_text,buyer_display_name,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)""",(data['seller_id'],data['buyer_id'],data['purchase_request_id'],data['product_id'],data['rating'],data['review_text'],data['buyer_display_name'],data['created_at'],data['updated_at']))

def seller_reviews(seller_id):
    if not seller_id:
        return pd.DataFrame()
    return hosted_select('seller_reviews',{'seller_id':seller_id},order='created_at.desc') if hosted_enabled() else df('SELECT * FROM seller_reviews WHERE seller_id=? ORDER BY created_at DESC',(seller_id,))

def buyer_already_reviewed(purchase_request_id):
    existing=hosted_select('seller_reviews',{'purchase_request_id':purchase_request_id},limit=1) if hosted_enabled() else df('SELECT id FROM seller_reviews WHERE purchase_request_id=?',(purchase_request_id,))
    return not existing.empty

def seller_review_summary(seller_id):
    reviews=seller_reviews(seller_id)
    if reviews.empty:
        return None
    return {'average':round(float(reviews['rating'].mean()),1),'count':int(len(reviews))}

def send_email(to_email, subject, html_body):
    # Fails quietly and returns False on any problem -- email is a nice-to-have
    # notification, never something that should block or falsely fail the
    # action that triggered it (newsletter signup, seller approval, etc).
    # Without a verified sending domain on Resend, delivery is restricted to
    # the Resend account's own verified email address; this will start
    # reaching real recipients once a domain is verified there.
    to_email=safe(to_email).strip()
    if not to_email or not is_valid_email(to_email):
        return False
    try:
        api_key=st.secrets.get('RESEND_API_KEY','')
    except Exception:
        api_key=''
    if not api_key:
        return False
    try:
        url='https://api.resend.com/emails'
        headers={'Authorization':f'Bearer {api_key}','Content-Type':'application/json'}
        payload={'from':'House Of Wax <hello@shophouseofwax.com>','to':[to_email],'subject':subject,'html':html_body}
        r=requests.post(url,json=payload,headers=headers,timeout=8)
        return r.status_code in (200,201)
    except Exception:
        return False

def instagram_configured():
    try:
        return bool(st.secrets.get('INSTAGRAM_ACCESS_TOKEN','')) and bool(st.secrets.get('INSTAGRAM_BUSINESS_ACCOUNT_ID',''))
    except Exception:
        return False

def post_to_instagram(image_url, caption):
    # Unlike send_email, this runs from a direct "Post now" button click, so
    # failures are returned as a message to show the admin instead of being
    # swallowed. Instagram's Graph API needs a two-step call: create a media
    # container from a publicly reachable image_url, then publish it.
    image_url=safe(image_url).strip()
    caption=safe(caption)
    if not image_url:
        return False,'An image URL is required.'
    try:
        access_token=st.secrets.get('INSTAGRAM_ACCESS_TOKEN','')
        account_id=st.secrets.get('INSTAGRAM_BUSINESS_ACCOUNT_ID','')
    except Exception:
        access_token=''; account_id=''
    if not access_token or not account_id:
        return False,'Instagram is not connected. Add INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_BUSINESS_ACCOUNT_ID in Secrets.'
    try:
        create_url=f'https://graph.facebook.com/v21.0/{account_id}/media'
        r=requests.post(create_url,data={'image_url':image_url,'caption':caption,'access_token':access_token},timeout=20)
        payload=r.json() if r.content else {}
        creation_id=payload.get('id')
        if r.status_code not in (200,201) or not creation_id:
            return False,'Instagram rejected the image/caption: '+safe(payload.get('error',{}).get('message'),'Unknown error')
        publish_url=f'https://graph.facebook.com/v21.0/{account_id}/media_publish'
        r2=requests.post(publish_url,data={'creation_id':creation_id,'access_token':access_token},timeout=20)
        payload2=r2.json() if r2.content else {}
        media_id=payload2.get('id')
        if r2.status_code not in (200,201) or not media_id:
            return False,'Instagram rejected publishing: '+safe(payload2.get('error',{}).get('message'),'Unknown error')
        return True,media_id
    except Exception as e:
        return False,'Connection to Instagram failed: '+str(e)

def fetch_instagram_permalink(media_id):
    media_id=safe(media_id).strip()
    if not media_id:
        return ''
    try:
        access_token=st.secrets.get('INSTAGRAM_ACCESS_TOKEN','')
    except Exception:
        access_token=''
    if not access_token:
        return ''
    try:
        r=requests.get(f'https://graph.facebook.com/v21.0/{media_id}',params={'fields':'permalink','access_token':access_token},timeout=10)
        if r.status_code==200:
            return safe(r.json().get('permalink'))
    except Exception:
        pass
    return ''

def facebook_configured():
    try:
        return bool(st.secrets.get('FACEBOOK_PAGE_ACCESS_TOKEN','')) and bool(st.secrets.get('FACEBOOK_PAGE_ID',''))
    except Exception:
        return False

def post_to_facebook_page(message, image_url=None):
    try:
        access_token=st.secrets.get('FACEBOOK_PAGE_ACCESS_TOKEN','')
        page_id=st.secrets.get('FACEBOOK_PAGE_ID','')
    except Exception:
        access_token=''; page_id=''
    if not access_token or not page_id:
        return False,'Facebook is not connected. Add FACEBOOK_PAGE_ACCESS_TOKEN and FACEBOOK_PAGE_ID in Secrets.'
    image_url=safe(image_url).strip()
    try:
        if image_url:
            url=f'https://graph.facebook.com/v21.0/{page_id}/photos'
            payload={'url':image_url,'caption':safe(message),'access_token':access_token}
        else:
            if not safe(message).strip():
                return False,'A message is required when not posting an image.'
            url=f'https://graph.facebook.com/v21.0/{page_id}/feed'
            payload={'message':safe(message),'access_token':access_token}
        r=requests.post(url,data=payload,timeout=20)
        result=r.json() if r.content else {}
        post_id=result.get('post_id') or result.get('id')
        if r.status_code not in (200,201) or not post_id:
            return False,'Facebook rejected the post: '+safe(result.get('error',{}).get('message'),'Unknown error')
        return True,post_id
    except Exception as e:
        return False,'Connection to Facebook failed: '+str(e)

def youtube_configured():
    try:
        return bool(st.secrets.get('YOUTUBE_CLIENT_ID','')) and bool(st.secrets.get('YOUTUBE_CLIENT_SECRET','')) and bool(st.secrets.get('YOUTUBE_REFRESH_TOKEN',''))
    except Exception:
        return False

def get_youtube_access_token():
    # YouTube's refresh token grants a fresh, short-lived access token per
    # upload rather than being used directly -- this exchanges it each time.
    try:
        client_id=st.secrets.get('YOUTUBE_CLIENT_ID','')
        client_secret=st.secrets.get('YOUTUBE_CLIENT_SECRET','')
        refresh_token=st.secrets.get('YOUTUBE_REFRESH_TOKEN','')
    except Exception:
        return ''
    if not (client_id and client_secret and refresh_token):
        return ''
    try:
        r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':client_id,'client_secret':client_secret,'refresh_token':refresh_token,'grant_type':'refresh_token'},timeout=15)
        if r.status_code==200:
            return safe(r.json().get('access_token'))
    except Exception:
        pass
    return ''

def upload_video_to_youtube(video_bytes, mime_type, title, description, privacy_status='private'):
    # Until this API project passes Google's compliance audit, YouTube
    # restricts uploaded videos to private/unlisted regardless of the
    # requested privacyStatus -- 'public' will likely be rejected until then.
    if not video_bytes:
        return False,'A video file is required.'
    access_token=get_youtube_access_token()
    if not access_token:
        return False,'YouTube is not connected. Add YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN in Secrets, and make sure the refresh token has not expired.'
    metadata={'snippet':{'title':safe(title)[:100],'description':safe(description),'categoryId':'10'},'status':{'privacyStatus':privacy_status}}
    try:
        init_headers={'Authorization':f'Bearer {access_token}','Content-Type':'application/json; charset=UTF-8','X-Upload-Content-Type':mime_type,'X-Upload-Content-Length':str(len(video_bytes))}
        r=requests.post('https://www.googleapis.com/upload/youtube/v3/videos',params={'uploadType':'resumable','part':'snippet,status'},headers=init_headers,json=metadata,timeout=20)
        if r.status_code not in (200,201) or 'Location' not in r.headers:
            payload=r.json() if r.content else {}
            return False,'YouTube rejected the upload request: '+safe(payload.get('error',{}).get('message'),'Unknown error')
        upload_url=r.headers['Location']
        r2=requests.put(upload_url,headers={'Content-Type':mime_type},data=video_bytes,timeout=300)
        payload2=r2.json() if r2.content else {}
        video_id=payload2.get('id')
        if r2.status_code not in (200,201) or not video_id:
            return False,'YouTube rejected the video file: '+safe(payload2.get('error',{}).get('message'),'Unknown error')
        return True,video_id
    except Exception as e:
        return False,'Connection to YouTube failed: '+str(e)

def liveavatar_configured():
    try:
        return bool(st.secrets.get('LIVEAVATAR_BACKEND_URL','')) and bool(st.secrets.get('LIVEAVATAR_AVATAR_ID',''))
    except Exception:
        return False

def liveavatar_enabled():
    return liveavatar_configured() and setting('liveavatar_enabled','false')=='true'

def render_liveavatar_widget():
    if not liveavatar_enabled():
        return
    backend_url=safe(st.secrets.get('LIVEAVATAR_BACKEND_URL','')).rstrip('/')
    avatar_id=safe(st.secrets.get('LIVEAVATAR_AVATAR_ID',''))
    st.markdown('### Ask House Of Wax')
    st.caption('Talk to our AI assistant about grading, buying, or selling.')
    st.components.v1.html(f"""
    <div id="avatar-container">
      <video id="avatarVideo" autoplay playsinline style="width:100%;max-width:400px;border-radius:8px;"></video>
      <div style="display:flex;gap:8px;margin-top:8px;">
        <input id="questionInput" placeholder="Ask about grading, buying, selling..." style="flex:1;padding:6px;"/>
        <button id="askButton">Ask</button>
      </div>
      <div id="avatarStatus" style="font-size:12px;color:#888;margin-top:4px;"></div>
    </div>

    <script type="module">
      import StreamingAvatar, {{ AvatarQuality, StreamingEvents, TaskType }}
        from "https://esm.sh/@heygen/liveavatar-web-sdk";

      const statusEl = document.getElementById("avatarStatus");
      let avatar;

      async function init() {{
        try {{
          const tokenRes = await fetch("{backend_url}/get-token", {{ method: "POST" }});
          if (!tokenRes.ok) throw new Error("token request failed");
          const {{ token }} = await tokenRes.json();

          avatar = new StreamingAvatar({{ token }});
          avatar.on(StreamingEvents.STREAM_READY, (event) => {{
            document.getElementById("avatarVideo").srcObject = event.detail;
          }});

          await avatar.createStartAvatar({{
            quality: AvatarQuality.High,
            avatarName: "{avatar_id}",
          }});
        }} catch (err) {{
          statusEl.textContent = "The avatar assistant is unavailable right now.";
        }}
      }}

      document.getElementById("askButton").onclick = async () => {{
        const input = document.getElementById("questionInput");
        const question = input.value;
        if (!question.trim()) return;
        statusEl.textContent = "Thinking...";
        try {{
          const res = await fetch("{backend_url}/ask", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ question }}),
          }});
          const {{ answer }} = await res.json();
          if (avatar) await avatar.speak({{ text: answer, taskType: TaskType.REPEAT }});
          statusEl.textContent = "";
        }} catch (err) {{
          statusEl.textContent = "Sorry, that didn't go through -- try again.";
        }}
        input.value = "";
      }};

      init();
    </script>
    """, height=520)

def suggest_price_range_from_discogs(release_id, media_grade=None, sleeve_grade=None):
    # Discogs' price_suggestions endpoint returns a suggested price per
    # condition grade (Mint, Near Mint, VG+, etc.), but it only works if
    # the Discogs account behind DISCOGS_TOKEN has complete seller
    # settings on Discogs itself -- otherwise it errors. Fails quietly so
    # callers can fall back to House Of Wax's own sales history.
    if not release_id:
        return None
    try:
        token=st.secrets.get('DISCOGS_TOKEN','')
    except Exception:
        token=''
    if not token:
        return None
    try:
        url=f'https://api.discogs.com/marketplace/price_suggestions/{release_id}'
        params={'token':token}
        headers={'User-Agent':'HouseOfWaxPrototype/1.0'}
        r=requests.get(url,params=params,headers=headers,timeout=8)
        if r.status_code!=200:
            return None
        data=r.json()
        by_grade={grade:info.get('value') for grade,info in data.items() if isinstance(info,dict) and info.get('value')}
        values=list(by_grade.values())
        if not values:
            return None
        if safe(media_grade):
            target_grade=worse_grade(media_grade,sleeve_grade)
            target_value=by_grade.get(DISCOGS_GRADE_ALIASES.get(target_grade,''))
            if target_value:
                grade_idx=GRADE_INDEX.get(target_grade,0)
                next_worse=GRADE_SCALE[grade_idx+1] if grade_idx+1<len(GRADE_SCALE) else None
                low_value=by_grade.get(DISCOGS_GRADE_ALIASES.get(next_worse,'')) if next_worse else None
                low=low_value if low_value else round(target_value*0.85,2)
                return {'low':min(low,target_value),'high':max(low,target_value),'source':f'Discogs marketplace, priced for {target_grade} condition','by_grade':by_grade,'grade_used':target_grade}
            mult=grade_price_multiplier(media_grade,sleeve_grade)
            mid=(min(values)+max(values))/2
            return {'low':round(mid*mult*0.85,2),'high':round(mid*mult*1.15,2),'source':'Discogs marketplace (adjusted for your condition; exact grade data unavailable)','by_grade':by_grade,'grade_used':target_grade}
        return {'low':min(values),'high':max(values),'source':'Discogs marketplace (real listings, varies by condition)','by_grade':by_grade}
    except Exception:
        return None

def sold_price_history(artist, exclude_product_id=None, limit=8):
    # Buyer-facing counterpart to suggest_price_range_from_how_history --
    # sellers already see this signal when pricing a new listing, buyers
    # browsing a listing get none of it without this.
    artist_clean=safe(artist).strip().lower()
    if not artist_clean:
        return pd.DataFrame()
    sold=hosted_select('products',{'listing_status':'Sold'}) if hosted_enabled() else df("SELECT * FROM products WHERE listing_status='Sold'")
    if sold.empty or 'artist' not in sold.columns:
        return pd.DataFrame()
    matches=sold[sold['artist'].fillna('').str.strip().str.lower()==artist_clean]
    if exclude_product_id and 'id' in matches.columns:
        matches=matches[matches['id'].astype(int)!=int(exclude_product_id)]
    if 'updated_at' in matches.columns:
        matches=matches.sort_values('updated_at',ascending=False)
    return matches.head(limit)

def suggest_price_range_from_how_history(artist, media_grade=None, sleeve_grade=None):
    artist_clean=safe(artist).strip().lower()
    if not artist_clean:
        return None
    try:
        sold=hosted_select('products',{'listing_status':'Sold'}) if hosted_enabled() else df("SELECT * FROM products WHERE listing_status='Sold'")
        matches=sold[sold['artist'].fillna('').str.strip().str.lower()==artist_clean] if not sold.empty and 'artist' in sold.columns else pd.DataFrame()
        label='sold on House Of Wax'
        if len(matches)<2:
            live=hosted_select('products',{},in_filters={'listing_status':PUBLIC_LISTING_STATUSES}) if hosted_enabled() else df('SELECT * FROM products')
            if not live.empty and 'artist' in live.columns:
                matches=live[live['artist'].fillna('').str.strip().str.lower()==artist_clean]
                label='currently listed on House Of Wax'
        if matches.empty or 'price' not in matches.columns:
            return None
        prices=matches['price'].dropna().astype(float)
        prices=prices[prices>0]
        if len(prices)<2:
            return None
        low=float(prices.quantile(0.25)); high=float(prices.quantile(0.75))
        if safe(media_grade):
            mult=grade_price_multiplier(media_grade,sleeve_grade)
            low=round(low*mult,2); high=round(high*mult,2)
            label=f'{label}, adjusted for your condition'
        return {'low':low,'high':high,'count':int(len(prices)),'source':f'{len(prices)} similar item(s) {label}'}
    except Exception:
        return None

def suggest_seller_price_range(artist, discogs_release_id=None, media_grade=None, sleeve_grade=None):
    if discogs_release_id:
        result=suggest_price_range_from_discogs(discogs_release_id,media_grade,sleeve_grade)
        if result:
            return result
    return suggest_price_range_from_how_history(artist,media_grade,sleeve_grade)

def barcode_length_status(barcode):
    code=normalize_barcode(barcode)
    if not code:
        return 'No barcode entered'
    if not code.isdigit():
        return 'Contains letters or nonstandard characters after cleanup'
    if len(code) in [8,12,13,14]:
        return f'Valid barcode length ({len(code)} digits)'
    return f'Unusual barcode length ({len(code)} digits)'


def lookup_musicbrainz_text_search(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    barcode=normalize_barcode(barcode)
    query_parts=[]
    if barcode:
        query_parts.append(f'barcode:{barcode}')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if title:
        query_parts.append(f'release:"{title}"')
    if not query_parts and (artist or title):
        query_parts.append(f'{artist} {title}'.strip())
    if not query_parts:
        return []
    try:
        url='https://musicbrainz.org/ws/2/release/'
        params={'query':' AND '.join(query_parts),'fmt':'json','limit':10}
        headers={'User-Agent':'HouseOfWaxPrototype/1.0 (prototype lookup)'}
        r=requests.get(url,params=params,headers=headers,timeout=10)
        if r.status_code!=200:
            return []
        data=r.json()
        results=[]
        for rel in data.get('releases',[])[:10]:
            rel_artist=''
            credits=rel.get('artist-credit') or []
            if credits:
                parts=[]
                for c in credits:
                    if isinstance(c,dict):
                        if 'artist' in c and isinstance(c['artist'],dict):
                            parts.append(c['artist'].get('name',''))
                        elif 'name' in c:
                            parts.append(c.get('name',''))
                rel_artist=' '.join([p for p in parts if p]).strip()
            label=''
            cat=''
            infos=rel.get('label-info') or []
            if infos:
                first=infos[0] or {}
                label=(first.get('label') or {}).get('name','') if isinstance(first.get('label'),dict) else ''
                cat=first.get('catalog-number','')
            fmt=''
            media=rel.get('media') or []
            if media:
                fmt=media[0].get('format','')
            year=safe(rel.get('date'))[:4]
            rid=safe(rel.get('id'))
            cover=f'https://coverartarchive.org/release/{rid}/front-500' if rid else ''
            ext=f'https://musicbrainz.org/release/{rid}' if rid else ''
            results.append({
                'source':'MusicBrainz',
                'external_id':rid,
                'artist':rel_artist,
                'title':safe(rel.get('title')),
                'format':fmt,
                'label':label,
                'release_year':year,
                'country':safe(rel.get('country')),
                'genre':'',
                'style':'',
                'catalog_number':cat,
                'image_url':cover,
                'external_url':ext,
                'raw_summary':'MusicBrainz artist/title search match'
            })
        return results
    except Exception:
        return []

def lookup_discogs_text_search(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    barcode=normalize_barcode(barcode)
    token=''
    try:
        token=st.secrets.get('DISCOGS_TOKEN','')
    except Exception:
        token=''
    try:
        url='https://api.discogs.com/database/search'
        query=' '.join([artist,title]).strip()
        params={'type':'release','per_page':10}
        if barcode:
            params['barcode']=barcode
        if query:
            params['q']=query
        if token:
            params['token']=token
        headers={'User-Agent':'HouseOfWaxPrototype/1.0'}
        r=requests.get(url,params=params,headers=headers,timeout=10)
        if r.status_code!=200:
            return []
        data=r.json()
        results=[]
        for item in data.get('results',[])[:10]:
            full=safe(item.get('title'))
            rel_artist=''
            album=full
            if ' - ' in full:
                rel_artist,album=full.split(' - ',1)
            formats=item.get('format') or []
            labels=item.get('label') or []
            genres=item.get('genre') or []
            styles=item.get('style') or []
            rid=safe(item.get('id'))
            results.append({
                'source':'Discogs',
                'external_id':rid,
                'artist':rel_artist,
                'title':album,
                'format':', '.join(formats) if isinstance(formats,list) else safe(formats),
                'label':', '.join(labels) if isinstance(labels,list) else safe(labels),
                'release_year':safe(item.get('year')),
                'country':safe(item.get('country')),
                'genre':', '.join(genres) if isinstance(genres,list) else safe(genres),
                'style':', '.join(styles) if isinstance(styles,list) else safe(styles),
                'catalog_number':'',
                'image_url':safe(item.get('cover_image')) or safe(item.get('thumb')),
                'external_url':f'https://www.discogs.com/release/{rid}' if rid else '',
                'raw_summary':'Discogs search match'
            })
        return results
    except Exception:
        return []



def quick_source_health_check():
    checks=[]
    targets=[
        ('Apple/iTunes','https://itunes.apple.com/search',{'term':'Lady Gaga The Fame','media':'music','entity':'album','limit':1}),
        ('MusicBrainz','https://musicbrainz.org/ws/2/release/',{'query':'Lady Gaga The Fame','fmt':'json','limit':1}),
        ('Discogs','https://api.discogs.com/database/search',{'q':'Lady Gaga The Fame','type':'release','per_page':1}),
    ]
    for name,url,params in targets:
        try:
            headers={'User-Agent':'HouseOfWaxPrototype/1.0'}
            r=requests.get(url,params=params,headers=headers,timeout=8)
            detail=f'HTTP {r.status_code}'
            status='Reachable' if r.status_code in [200,401,403,429] else 'Problem'
            if name=='Discogs' and r.status_code in [401,403]:
                status='Needs token / limited'
            if name=='MusicBrainz' and r.status_code==503:
                status='Temporarily unavailable'
            checks.append({'Source':name,'Status':status,'Details':detail})
        except Exception as e:
            checks.append({'Source':name,'Status':'Connection error','Details':safe(e)})
    checks.append({'Source':'Discogs token','Status':'Connected' if discogs_token_status() else 'Not connected','Details':'Add DISCOGS_TOKEN in Streamlit secrets for stronger Discogs results.'})
    return checks

def universal_search_urls(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    q=' '.join([artist,title]).strip() or code
    q_enc=quote_plus(q)
    code_enc=quote_plus(code)
    links=[]
    if q:
        links.extend([
            ('Discogs search',f'https://www.discogs.com/search/?q={q_enc}&type=all'),
            ('MusicBrainz search',f'https://musicbrainz.org/search?query={q_enc}&type=release&method=indexed'),
            ('Apple Music/iTunes web search',f'https://music.apple.com/us/search?term={q_enc}'),
            ('Google shopping/web search',f'https://www.google.com/search?q={q_enc}+album+barcode+vinyl+CD'),
            ('Wikipedia search',f'https://en.wikipedia.org/w/index.php?search={q_enc}'),
            ('Wikidata search',f'https://www.wikidata.org/w/index.php?search={q_enc}'),
        ])
    if code:
        links.extend([
            ('Discogs barcode search',f'https://www.discogs.com/search/?q={code_enc}&type=all'),
            ('MusicBrainz barcode search',f'https://musicbrainz.org/search?query=barcode%3A{code_enc}&type=release&method=indexed'),
            ('Barcode Lookup search',f'https://www.barcodelookup.com/{code_enc}'),
            ('UPCitemdb search',f'https://www.upcitemdb.com/upc/{code_enc}'),
            ('Go-UPC search',f'https://go-upc.com/search?q={code_enc}'),
            ('GS1 GEPIR / Verified by GS1 search',f'https://www.gs1.org/services/verified-by-gs1'),
        ])
    return links

def combined_search_terms(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    combined=' '.join([artist,title]).strip()
    terms=[]
    if combined:
        terms.append(combined)
    if artist and title:
        terms.append(f'artist:{artist} release:{title}')
        terms.append(f'"{artist}" "{title}"')
    elif artist:
        terms.append(artist)
    elif title:
        terms.append(title)
    if code:
        terms.append(code)
    clean=[]
    seen=set()
    for term in terms:
        term=safe(term).strip()
        key=term.lower()
        if term and key not in seen:
            clean.append(term)
            seen.add(key)
    return clean

def token_overlap_score(needle='', haystack=''):
    needle_tokens=[t for t in re.findall(r'[a-z0-9]+', safe(needle).lower()) if len(t)>1]
    hay_tokens=set(re.findall(r'[a-z0-9]+', safe(haystack).lower()))
    if not needle_tokens or not hay_tokens:
        return 0
    hits=sum(1 for t in needle_tokens if t in hay_tokens)
    return int((hits / max(len(needle_tokens),1)) * 100)


def choose_best_search_result(results, artist='', title='', barcode=''):
    if not results:
        return None
    ranked=dedupe_and_rank_results(results,artist,title) if 'dedupe_and_rank_results' in globals() else results
    source_bonus={'Discogs':20,'Discogs Broad':18,'House Of Wax':25,'MusicBrainz':12,'MusicBrainz Broad':10,'Apple/iTunes':8}
    best=None
    best_score=-1
    for r in ranked:
        score=int(r.get('_match_score') or 0)
        src=safe(r.get('source'))
        score+=source_bonus.get(src,0)
        if safe(r.get('image_url')): score+=3
        if safe(r.get('format')) and 'digital' not in safe(r.get('format')).lower(): score+=4
        if safe(r.get('release_year')): score+=2
        if barcode and src in ['House Of Wax','Discogs','Discogs Broad','MusicBrainz','MusicBrainz Broad']:
            score+=3
        if score>best_score:
            best_score=score
            best=dict(r)
            best['_final_score']=score
    return best

def run_smart_best_match_search(artist='', title='', barcode=''):
    diagnostics=[]
    code=normalize_barcode(barcode)
    all_results=[]

    if code:
        barcode_results,barcode_diag=lookup_barcode_with_diagnostics(code)
        diagnostics.extend(barcode_diag)
        all_results.extend(barcode_results)

    if artist or title:
        text_results,text_diag=lookup_by_artist_title_with_diagnostics(artist,title,code)
        diagnostics.extend(text_diag)
        all_results.extend(text_results)

    if code and not all_results:
        broad_results,broad_diag=lookup_by_artist_title_with_diagnostics('', '', code)
        diagnostics.extend(broad_diag)
        all_results.extend(broad_results)

    ranked=dedupe_and_rank_results(all_results,artist,title) if all_results else []
    best=choose_best_search_result(ranked,artist,title,code)

    if best:
        diagnostics.append({'Step':'Smart best-match picker','Status':'Best match selected','Details':f"{safe(best.get('source'))}: {safe(best.get('artist'))} - {safe(best.get('title'))}"})
    else:
        diagnostics.append({'Step':'Smart best-match picker','Status':'No best match','Details':'No automatic source returned a usable candidate. Use manual seed to build House Of Wax database.'})
    return best,ranked,diagnostics

def match_identity(result):
    return (
        safe(result.get('source')).lower(),
        safe(result.get('external_id')).lower(),
        safe(result.get('artist')).lower(),
        safe(result.get('title')).lower()
    )

def search_match_details(result, artist='', title=''):
    result_artist=safe(result.get('artist'))
    result_title=safe(result.get('title'))
    artist_score=token_overlap_score(artist,result_artist)
    title_score=token_overlap_score(title,result_title)
    return {
        'artist_matched':bool(not artist or artist_score),
        'title_matched':bool(not title or title_score),
        'has_image':bool(safe(result.get('image_url'))),
        'has_year':bool(safe(result.get('release_year'))),
        'has_label':bool(safe(result.get('label'))),
        'has_source':bool(safe(result.get('source')))
    }

def match_confidence_label(result, artist='', title=''):
    match_type=safe(result.get('_barcode_match_type'))
    if match_type=='exact':
        return 'Strong match'
    if match_type=='partial':
        details=search_match_details(result,artist,title)
        if details['artist_matched'] and details['title_matched']:
            return 'Possible match'
        return 'Broad match'
    score=int(result.get('_final_score') or result.get('_match_score') or 0)
    details=search_match_details(result,artist,title)
    if details['artist_matched'] and details['title_matched'] and score >= 110:
        return 'Strong'
    if score >= 70 and (details['artist_matched'] or details['title_matched']):
        return 'Medium'
    return 'Weak'

def match_explanation(result, artist='', title=''):
    details=search_match_details(result,artist,title)
    reasons=[]
    if details['artist_matched'] and details['title_matched']:
        reasons.append('artist and title matched the search terms')
    elif details['artist_matched']:
        reasons.append('artist matched, but the title needs review')
    elif details['title_matched']:
        reasons.append('title matched, but the artist needs review')
    else:
        reasons.append('artist and title did not strongly match')
    reasons.append('image found' if details['has_image'] else 'no image found')
    found=[]
    if details['has_year']:
        found.append('year')
    if details['has_label']:
        found.append('label')
    if details['has_source']:
        found.append('source')
    reasons.append(('found '+', '.join(found)) if found else 'limited year/label/source details')
    return 'Chosen because '+', '.join(reasons)+'.'

def use_search_match(result, key_prefix='main'):
    st.session_state['v24_autofill_listing']=result
    st.session_state['v24_autofill_barcode']=normalize_barcode(result.get('barcode')) or st.session_state.get(f'v24_lookup_barcode_clean_{key_prefix}','')
    try:
        rid=create_or_update_how_release(st.session_state['v24_autofill_barcode'],result)
        st.session_state['v25_release_id']=rid
    except Exception:
        pass

def save_wrong_match_correction(result, barcode='', key_prefix='main'):
    code=normalize_barcode(barcode) or st.session_state.get(f'v24_lookup_barcode_clean_{key_prefix}','')
    summary=f"{safe(result.get('artist'))} - {safe(result.get('title'))} ({safe(result.get('source'))}, {safe(result.get('release_year'))})"
    note='Seller marked Smart Search recommended match as wrong.'
    release_id=None
    try:
        release_id=create_or_update_how_release(code,result,note) if code else None
    except Exception:
        release_id=None
    try:
        submit_release_correction(release_id,0,'recommended_match',summary,'Marked wrong',note)
        return True
    except Exception:
        if code:
            try:
                create_or_update_how_release(code,result,note)
                return True
            except Exception:
                return False
        return False

def render_best_match_card(best, key_prefix='main', ranked=None, artist='', title='', barcode=''):
    if not best:
        return
    st.markdown('### Recommended best match')
    with st.container(border=True):
        c1,c2=st.columns([1,2])
        with c1:
            if safe(best.get('image_url')):
                safe_image(safe(best.get('image_url')),width='stretch',fallback_text='Search result image unavailable.')
            else:
                st.info('No image returned.')
        with c2:
            st.write(f"**Artist:** {safe(best.get('artist'))}")
            st.write(f"**Title:** {safe(best.get('title'))}")
            st.write(f"**Source:** {safe(best.get('source'))}")
            st.write(f"**Format:** {safe(best.get('format'))}")
            st.write(f"**Label:** {safe(best.get('label'))}")
            st.write(f"**Year:** {safe(best.get('release_year'))}")
            if safe(best.get('external_url')):
                st.write(f"**Source URL:** {safe(best.get('external_url'))}")
            confidence=match_confidence_label(best,artist,title)
            st.write(f"**Confidence:** {confidence}")
            st.caption(f"Match score: {safe(best.get('_final_score')) or safe(best.get('_match_score'))}")
            st.write(match_explanation(best,artist,title))
            if st.button('Use recommended match',key=f'use_recommended_match_{key_prefix}'):
                use_search_match(best,key_prefix)
                st.success('Recommended match loaded into listing draft.')
            if st.button('Mark recommended match as wrong',key=f'mark_recommended_wrong_{key_prefix}'):
                saved=save_wrong_match_correction(best,barcode,key_prefix)
                st.session_state[f'v25_wrong_match_{key_prefix}']=True
                if saved:
                    st.warning('Marked wrong and saved for House Of Wax review.')
                else:
                    st.warning('Marked wrong for this session. Add a manual correction if this item has no barcode yet.')

    alternates=[]
    best_key=match_identity(best)
    for item in ranked or []:
        if match_identity(item)!=best_key:
            alternates.append(item)
        if len(alternates)>=3:
            break
    if alternates:
        st.markdown('### Top 3 Alternate Matches')
        for i,item in enumerate(alternates,1):
            with st.container(border=True):
                c1,c2=st.columns([1,3])
                with c1:
                    if safe(item.get('image_url')):
                        safe_image(safe(item.get('image_url')),width='stretch',fallback_text='Search result image unavailable.')
                with c2:
                    st.write(f"**{i}. {safe(item.get('artist'))} - {safe(item.get('title'))}**")
                    st.caption(f"{safe(item.get('source'))} • {safe(item.get('format'))} • {safe(item.get('release_year'))} • score {safe(item.get('_match_score'))}")
                    st.write(match_explanation(item,artist,title))
                    if st.button('Use this alternate',key=f'use_alternate_match_{key_prefix}_{i}'):
                        use_search_match(item,key_prefix)
                        st.success('Alternate match loaded into listing draft.')


def show_universal_search_links(artist='', title='', barcode=''):
    links=universal_search_urls(artist,title,barcode)
    if not links:
        return
    with st.expander('Backup source links — only if smart search fails'):
        st.write('Smart Search searches inside House Of Wax first. These links are only a backup for manual verification.')
        for label,url in links:
            st.markdown(f"- [{safe(label)}]({safe(url)})")
        st.markdown('#### Copy exact URLs')
        for label,url in links:
            st.text_input(label,value=url,key=f"copy_link_{abs(hash(label+url))}")


def render_source_health_panel(key_prefix='main'):
    with st.expander('Source health check / why search may return nothing'):
        st.write('This tests whether Streamlit can reach the outside music search sources.')
        if st.button('Run source health check',key=f'source_health_check_button_{key_prefix}'):
            st.session_state[f'source_health_results_{key_prefix}']=quick_source_health_check()
        if st.session_state.get(f'source_health_results_{key_prefix}'):
            st.dataframe(pd.DataFrame(st.session_state[f'source_health_results_{key_prefix}']),width='stretch')
        st.caption('If Apple/iTunes and MusicBrainz show connection errors, the app cannot reach outside APIs from the deployed environment. In that case use the manual links and internal House Of Wax database workflow.')

def manual_release_seed_form(artist='', title='', barcode='', key_prefix='main'):
    with st.expander('Manual release seed: add this item to House Of Wax database'):
        st.write('Use this when automatic search fails but you found the correct information manually.')
        with st.form(f'manual_release_seed_form_{key_prefix}'):
            code=st.text_input('Barcode',value=normalize_barcode(barcode))
            a=st.text_input('Artist',value=safe(artist))
            t=st.text_input('Title',value=safe(title))
            c1,c2,c3=st.columns(3)
            fmt=c1.text_input('Format',value='Vinyl')
            label=c2.text_input('Label')
            year=c3.text_input('Release year')
            genre=st.text_input('Genre/style')
            catalog=st.text_input('Catalog number')
            img=st.text_input('Cover/product image URL')
            ext=st.text_input('Source/release URL')
            notes=st.text_area('Notes / where you found the info')
            submit=st.form_submit_button('Seed House Of Wax release database')
        if submit:
            result={'source':'House Of Wax Manual','external_id':'','artist':a,'title':t,'format':fmt,'label':label,'release_year':year,'country':'','genre':genre,'style':'','catalog_number':catalog,'image_url':img,'external_url':ext,'raw_summary':notes}
            rid=create_or_update_how_release(code,result,notes)
            st.session_state['v24_autofill_listing']=result
            st.session_state['v24_autofill_barcode']=normalize_barcode(code)
            st.session_state['v25_release_id']=rid
            st.success('Manual release saved to House Of Wax database and loaded into listing draft.')


def lookup_itunes_text_search(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    term=' '.join([artist,title]).strip() or code
    if not term:
        return []
    try:
        url='https://itunes.apple.com/search'
        params={'term':term,'media':'music','entity':'album','limit':25}
        r=requests.get(url,params=params,timeout=10)
        if r.status_code!=200:
            return []
        data=r.json()
        results=[]
        for item in data.get('results',[])[:25]:
            album=safe(item.get('collectionName'))
            rel_artist=safe(item.get('artistName'))
            year=safe(item.get('releaseDate'))[:4]
            img=safe(item.get('artworkUrl100'))
            if img:
                img=img.replace('100x100bb','600x600bb')
            ext=safe(item.get('collectionViewUrl'))
            cid=safe(item.get('collectionId'))
            genre=safe(item.get('primaryGenreName'))
            # Do not filter aggressively here. The ranked display handles relevance.
            hay=f"{rel_artist} {album}".lower()
            results.append({
                'source':'Apple/iTunes',
                'external_id':cid,
                'artist':rel_artist,
                'title':album,
                'format':'Digital album / release reference',
                'label':'',
                'release_year':year,
                'country':safe(item.get('country')),
                'genre':genre,
                'style':'',
                'catalog_number':'',
                'image_url':img,
                'external_url':ext,
                'raw_summary':'Apple iTunes Search API album match'
            })
        return results
    except Exception:
        return []

def lookup_musicbrainz_broad_search(artist='', title='', barcode=''):
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    queries=[]
    if artist and title:
        queries.extend([
            f'artist:{artist} AND release:{title}',
            f'"{artist}" AND "{title}"',
            f'{artist} {title}'
        ])
    elif artist:
        queries.extend([f'artist:{artist}', artist])
    elif title:
        queries.extend([f'release:{title}', title])
    if code:
        queries.append(f'barcode:{code}')
    results=[]
    seen=set()
    for q in queries:
        try:
            url='https://musicbrainz.org/ws/2/release/'
            params={'query':q,'fmt':'json','limit':15}
            headers={'User-Agent':'HouseOfWaxPrototype/1.0 (prototype lookup)'}
            r=requests.get(url,params=params,headers=headers,timeout=10)
            if r.status_code!=200:
                continue
            data=r.json()
            for rel in data.get('releases',[])[:15]:
                rel_artist=''
                credits=rel.get('artist-credit') or []
                if credits:
                    parts=[]
                    for c in credits:
                        if isinstance(c,dict):
                            if 'artist' in c and isinstance(c['artist'],dict):
                                parts.append(c['artist'].get('name',''))
                            elif 'name' in c:
                                parts.append(c.get('name',''))
                    rel_artist=' '.join([p for p in parts if p]).strip()
                album=safe(rel.get('title'))
                key=(safe(rel.get('id')),album)
                if key in seen:
                    continue
                seen.add(key)
                label=''
                cat=''
                infos=rel.get('label-info') or []
                if infos:
                    first=infos[0] or {}
                    label=(first.get('label') or {}).get('name','') if isinstance(first.get('label'),dict) else ''
                    cat=first.get('catalog-number','')
                fmt=''
                media=rel.get('media') or []
                if media:
                    fmt=media[0].get('format','')
                year=safe(rel.get('date'))[:4]
                rid=safe(rel.get('id'))
                cover=f'https://coverartarchive.org/release/{rid}/front-500' if rid else ''
                ext=f'https://musicbrainz.org/release/{rid}' if rid else ''
                results.append({
                    'source':'MusicBrainz Broad',
                    'external_id':rid,
                    'artist':rel_artist,
                    'title':album,
                    'format':fmt,
                    'label':label,
                    'release_year':year,
                    'country':safe(rel.get('country')),
                    'genre':'',
                    'style':'',
                    'catalog_number':cat,
                    'image_url':cover,
                    'external_url':ext,
                    'raw_summary':f'MusicBrainz broad search match: {q}'
                })
        except Exception:
            continue
        if len(results) >= 10:
            break
    return results[:15]

def lookup_discogs_broad_search(artist='', title='', barcode=''):
    # Broad q search. Works best with a DISCOGS_TOKEN, but will still attempt a public search.
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    token=''
    try:
        token=st.secrets.get('DISCOGS_TOKEN','')
    except Exception:
        token=''
    queries=[]
    if artist and title:
        queries.append(f'{artist} {title}')
    elif artist:
        queries.append(artist)
    elif title:
        queries.append(title)
    if code:
        queries.append(code)
    results=[]
    seen=set()
    for q in queries:
        try:
            params={'q':q,'type':'release','per_page':15}
            if token:
                params['token']=token
            headers={'User-Agent':'HouseOfWaxPrototype/1.0'}
            r=requests.get('https://api.discogs.com/database/search',params=params,headers=headers,timeout=10)
            if r.status_code!=200:
                continue
            data=r.json()
            for item in data.get('results',[])[:15]:
                rid=safe(item.get('id'))
                full=safe(item.get('title'))
                key=(rid,full)
                if key in seen:
                    continue
                seen.add(key)
                rel_artist=''
                album=full
                if ' - ' in full:
                    rel_artist,album=full.split(' - ',1)
                formats=item.get('format') or []
                labels=item.get('label') or []
                genres=item.get('genre') or []
                styles=item.get('style') or []
                results.append({
                    'source':'Discogs Broad',
                    'external_id':rid,
                    'artist':rel_artist,
                    'title':album,
                    'format':', '.join(formats) if isinstance(formats,list) else safe(formats),
                    'label':', '.join(labels) if isinstance(labels,list) else safe(labels),
                    'release_year':safe(item.get('year')),
                    'country':safe(item.get('country')),
                    'genre':', '.join(genres) if isinstance(genres,list) else safe(genres),
                    'style':', '.join(styles) if isinstance(styles,list) else safe(styles),
                    'catalog_number':'',
                    'image_url':safe(item.get('cover_image')) or safe(item.get('thumb')),
                    'external_url':f'https://www.discogs.com/release/{rid}' if rid else '',
                    'raw_summary':f'Discogs broad search match: {q}'
                })
        except Exception:
            continue
        if len(results) >= 10:
            break
    return results[:15]

def lookup_itunes_combined_search(artist='', title='', barcode=''):
    return lookup_itunes_text_search(artist,title,barcode)

def lookup_musicbrainz_combined_search(artist='', title='', barcode=''):
    return lookup_musicbrainz_broad_search(artist,title,barcode)

def lookup_discogs_combined_search(artist='', title='', barcode=''):
    return lookup_discogs_broad_search(artist,title,barcode)

def score_release_match(result, artist='', title=''):
    artist=safe(artist).lower()
    title=safe(title).lower()
    result_artist=safe(result.get('artist')).lower()
    result_title=safe(result.get('title')).lower()
    hay=f"{result_artist} {result_title}".lower()
    score=0
    artist_overlap=token_overlap_score(artist,result_artist)
    title_overlap=token_overlap_score(title,result_title)
    combined_overlap=token_overlap_score(' '.join([artist,title]).strip(),hay)
    if artist:
        score+=artist_overlap // 5
    if title:
        score+=title_overlap // 4
    if artist and title:
        score+=combined_overlap // 3
        if artist_overlap and title_overlap:
            score+=35
        elif artist_overlap and not title_overlap:
            score-=30
        elif title_overlap and not artist_overlap:
            score-=15
        else:
            score-=40
    elif title and not title_overlap:
        score-=20
    if title and artist and artist_overlap and not title_overlap:
        score-=20
    if artist and artist in result_artist:
        score+=12
    if title and title in result_title:
        score+=18
    if safe(result.get('image_url')):
        score+=5
    if safe(result.get('release_year')):
        score+=3
    if safe(result.get('source')).startswith('Discogs'):
        score+=4
    if safe(result.get('source')).startswith('Apple'):
        score+=6
    return score

def dedupe_and_rank_results(results, artist='', title=''):
    seen=set()
    unique=[]
    for r in results:
        key=(safe(r.get('source')),safe(r.get('external_id')),safe(r.get('artist')).lower(),safe(r.get('title')).lower())
        if key not in seen:
            seen.add(key)
            r=dict(r)
            r['_match_score']=score_release_match(r,artist,title)
            unique.append(r)
    unique.sort(key=lambda x:x.get('_match_score',0),reverse=True)
    return unique[:25]


def lookup_by_artist_title_with_diagnostics(artist='', title='', barcode=''):
    diagnostics=[]
    artist=safe(artist)
    title=safe(title)
    code=normalize_barcode(barcode)
    terms=combined_search_terms(artist,title,code)
    diagnostics.append({'Step':'Combined search terms','Status':f'Artist: {artist or "blank"} | Title: {title or "blank"} | Barcode: {code or "blank"}','Details':'Artist and title are searched together first: '+(terms[0] if terms else 'no search term')})
    results=[]

    # Discogs combined search first for physical music culture/collector data.
    try:
        dres=lookup_discogs_combined_search(artist,title,code)
        if dres:
            diagnostics.append({'Step':'Discogs combined search','Status':f'{len(dres)} match(es)','Details':'Discogs returned release candidates using artist and title together. Works best when DISCOGS_TOKEN is connected.'})
            results.extend(dres)
        else:
            token_msg='connected' if discogs_token_status() else 'not connected'
            diagnostics.append({'Step':'Discogs combined search','Status':'No match','Details':f'Discogs returned no combined result. Discogs token status: {token_msg}.'})
    except Exception as e:
        diagnostics.append({'Step':'Discogs combined search','Status':'Error','Details':safe(e)})

    # Apple/iTunes album search is reliable for popular mainstream artists and gives good cover art.
    try:
        ares=lookup_itunes_combined_search(artist,title,code)
        if ares:
            diagnostics.append({'Step':'Apple/iTunes combined search','Status':f'{len(ares)} match(es)','Details':'Apple/iTunes returned album candidates and artwork using artist and title together.'})
            results.extend(ares)
        else:
            diagnostics.append({'Step':'Apple/iTunes combined search','Status':'No match','Details':'Apple/iTunes returned no album candidate for these combined terms.'})
    except Exception as e:
        diagnostics.append({'Step':'Apple/iTunes combined search','Status':'Error','Details':safe(e)})

    # MusicBrainz combined search uses multiple query styles because strict Lucene queries can miss results.
    try:
        mbres=lookup_musicbrainz_combined_search(artist,title,code)
        if mbres:
            diagnostics.append({'Step':'MusicBrainz combined search','Status':f'{len(mbres)} match(es)','Details':'MusicBrainz returned release candidates using combined query attempts.'})
            results.extend(mbres)
        else:
            diagnostics.append({'Step':'MusicBrainz combined search','Status':'No match','Details':'MusicBrainz returned no result after combined query attempts.'})
    except Exception as e:
        diagnostics.append({'Step':'MusicBrainz combined search','Status':'Error','Details':safe(e)})

    unique=dedupe_and_rank_results(results,artist,title)

    # Save only if barcode exists; otherwise it can be selected and saved when listing is made.
    if code:
        for res in unique:
            try:
                cache_lookup_result(code,res)
                create_or_update_how_release(code,res)
            except Exception:
                pass

    if unique:
        diagnostics.append({'Step':'Final result','Status':f'{len(unique)} possible match(es)','Details':'Review the candidates and choose the closest release. If there are digital-only matches, use them as a starting point and correct format/details manually.'})
    else:
        diagnostics.append({'Step':'Final result','Status':'Manual entry needed','Details':'No source returned a match. You can still create the item manually and House Of Wax will store the data over time.'})
    return unique, diagnostics


def lookup_barcode_with_diagnostics(barcode):
    code=normalize_barcode(barcode)
    diagnostics=[]
    diagnostics.append({'Step':'Barcode entered','Status':safe(barcode),'Details':f'Cleaned value: {code}'})
    diagnostics.append({'Step':'Barcode format','Status':barcode_length_status(code),'Details':'Common product barcode lengths are 8, 12, 13, or 14 digits.'})

    if not code:
        diagnostics.append({'Step':'Result','Status':'Stopped','Details':'No barcode was entered.'})
        return [], diagnostics
    if len(code)<5:
        diagnostics.append({'Step':'Partial barcode search','Status':'Stopped','Details':'Enter at least 5 digits to search possible partial barcode matches, or use artist/title search or manual entry.'})
        return [], diagnostics

    # 1. House Of Wax internal release database
    try:
        internal=get_best_how_release(code)
        if internal:
            diagnostics.append({'Step':'House Of Wax release database','Status':'Match found','Details':'Using internal House Of Wax release record first.'})
            return mark_barcode_results([how_release_to_autofill(internal)],'exact',code), diagnostics
        diagnostics.append({'Step':'House Of Wax release database','Status':'No match','Details':'No internal House Of Wax release record exists for this barcode yet.'})
    except Exception as e:
        diagnostics.append({'Step':'House Of Wax release database','Status':'Error','Details':safe(e)})

    # 2. Local barcode cache
    try:
        cached=df("SELECT * FROM barcode_lookup_cache WHERE barcode=? ORDER BY id DESC LIMIT 10",(code,))
        if not cached.empty:
            results=[]
            for _,r in cached.iterrows():
                res=cache_row_to_autofill(r)
                results.append(res)
                try:
                    create_or_update_how_release(code,res)
                except Exception:
                    pass
            diagnostics.append({'Step':'Barcode lookup cache','Status':f'{len(results)} cached match(es)','Details':'Using prior lookup results saved by House Of Wax.'})
            return mark_barcode_results(results,'exact',code), diagnostics
        diagnostics.append({'Step':'Barcode lookup cache','Status':'No match','Details':'This barcode has not been cached from a prior lookup.'})
    except Exception as e:
        diagnostics.append({'Step':'Barcode lookup cache','Status':'Error','Details':safe(e)})

    # 3. Discogs
    if discogs_token_status():
        try:
            discogs_results=lookup_discogs_barcode(code)
            if discogs_results:
                for res in discogs_results:
                    try:
                        cache_lookup_result(code,res)
                        create_or_update_how_release(code,res)
                    except Exception:
                        pass
                diagnostics.append({'Step':'Discogs','Status':f'{len(discogs_results)} match(es)','Details':'Discogs token is connected and returned results.'})
                return mark_barcode_results(discogs_results,'exact',code), diagnostics
            diagnostics.append({'Step':'Discogs','Status':'No match','Details':'Discogs token is connected, but no results were returned for this barcode.'})
        except Exception as e:
            diagnostics.append({'Step':'Discogs','Status':'Error','Details':safe(e)})
    else:
        diagnostics.append({'Step':'Discogs','Status':'Not connected','Details':'No DISCOGS_TOKEN found in Streamlit secrets. Add one to enable Discogs lookup.'})

    # 4. MusicBrainz
    try:
        mb_results=lookup_musicbrainz_barcode(code)
        if mb_results:
            for res in mb_results:
                try:
                    cache_lookup_result(code,res)
                    create_or_update_how_release(code,res)
                except Exception:
                    pass
            diagnostics.append({'Step':'MusicBrainz','Status':f'{len(mb_results)} match(es)','Details':'MusicBrainz returned results for this barcode.'})
            return mark_barcode_results(mb_results,'exact',code), diagnostics
        diagnostics.append({'Step':'MusicBrainz','Status':'No match','Details':'MusicBrainz responded, but did not return a release for this barcode.'})
    except Exception as e:
        diagnostics.append({'Step':'MusicBrainz','Status':'Error','Details':safe(e)})

    # 5. Partial barcode matching against House Of Wax-owned local data only.
    if len(code)<5:
        diagnostics.append({'Step':'Partial barcode search','Status':'Skipped','Details':'Enter at least 5 digits to search possible partial barcode matches.'})
    else:
        try:
            partial_results=find_partial_barcode_matches(code)
            if partial_results:
                diagnostics.append({'Step':'Partial barcode search','Status':f'{len(partial_results)} possible match(es)','Details':'Possible matches from partial barcode. These are not exact barcode matches; review before using.'})
                return partial_results, diagnostics
            diagnostics.append({'Step':'Partial barcode search','Status':'No match','Details':'No House Of Wax cached or internal barcode records contain this fragment.'})
        except Exception as e:
            diagnostics.append({'Step':'Partial barcode search','Status':'Error','Details':safe(e)})

    diagnostics.append({'Step':'Final result','Status':'Manual entry needed','Details':'No exact or partial barcode matches found. Try artist/title search or enter the item manually.'})
    return [], diagnostics

def show_barcode_diagnostics(diagnostics):
    if diagnostics:
        st.markdown('### Lookup diagnostics')
        st.dataframe(pd.DataFrame(diagnostics),width='stretch')
        final=diagnostics[-1]
        if final.get('Status')=='Manual entry needed':
            st.warning('No match found. This does not always mean the barcode is bad. It may mean Discogs is not connected yet, MusicBrainz does not have the release, or the item is non-music/merch.')
        if any(d.get('Step')=='Discogs' and d.get('Status')=='Not connected' for d in diagnostics):
            st.info('Discogs is not connected. Add a DISCOGS_TOKEN in Streamlit secrets for stronger vinyl/CD/cassette lookup.')


def lookup_barcode(barcode):
    barcode=normalize_barcode(barcode)
    if not barcode:
        return []
    # First check House Of Wax internal verified/release database.
    internal=get_best_how_release(barcode)
    if internal:
        return mark_barcode_results([how_release_to_autofill(internal)],'exact',barcode)
    cached=df("SELECT * FROM barcode_lookup_cache WHERE barcode=? ORDER BY id DESC LIMIT 10",(barcode,))
    results=[]
    if not cached.empty:
        for _,r in cached.iterrows():
            res=cache_row_to_autofill(r)
            results.append(res)
            try:
                create_or_update_how_release(barcode,res)
            except Exception:
                pass
        return mark_barcode_results(results,'exact',barcode)
    results=lookup_discogs_barcode(barcode)
    if not results:
        results=lookup_musicbrainz_barcode(barcode)
    for res in results:
        try:
            cache_lookup_result(barcode,res)
            create_or_update_how_release(barcode,res)
        except Exception:
            pass
    if results:
        return mark_barcode_results(results,'exact',barcode)
    return find_partial_barcode_matches(barcode)

def render_barcode_lookup_widget(key_prefix='main'):
    seed_listing_media_policy()
    st.markdown('### Barcode / UPC lookup')
    st.write('For records, CDs, and cassettes, scan or type the barcode. House Of Wax checks its own release database first, then outside sources for release information and cover art. For shirts, dolls, memorabilia, merch, and accessories, sellers should use a photo of the exact item or an official product image.')
    st.caption('Enter the full barcode when available. You may also enter at least 5-6 digits to look for possible matches.')
    with st.expander('Scanning with your phone? Here\'s the fastest way',expanded=False):
        st.write("On Android, point Google Lens (already on your phone) at the barcode and copy the number it reads.")
        st.write("On iPhone, search your App Store for a free barcode or UPC scanner app, scan the item, then copy the number it shows.")
        st.write("Either way, switch back to House Of Wax and paste the number into the field below.")
    render_source_health_panel(key_prefix)
    c1,c2=st.columns([2,1])
    barcode=c1.text_input('Scan or enter barcode / UPC',key=f'v24_lookup_barcode_{key_prefix}',placeholder='Click here, scan, or type at least 5-6 digits',help='Enter the full barcode when available. You may also enter at least 5-6 digits to look for possible matches.')
    lookup_clicked=c2.button('Lookup barcode',key=f'v24_lookup_button_{key_prefix}')

    with st.expander('No barcode match? Broad search by artist and album title'):
        a1,a2=st.columns(2)
        search_artist=a1.text_input('Artist',key=f'v25_search_artist_{key_prefix}',placeholder='Example: Lady Gaga')
        search_title=a2.text_input('Album / release title',key=f'v25_search_title_{key_prefix}',placeholder='Example: The Fame, Born This Way, Chromatica')
        text_search_clicked=st.button('Search all music sources',key=f'v25_text_search_button_{key_prefix}')
    if lookup_clicked:
        code=normalize_barcode(barcode)
        if not code:
            st.error('Enter or scan a barcode first.')
        elif len(code)<5:
            st.error('Enter at least 5 digits for partial barcode search, or use artist/title search or manual entry.')
        else:
            with st.spinner('Looking up barcode...'):
                matches,diagnostics=lookup_barcode_with_diagnostics(code)
            st.session_state[f'v25_lookup_diagnostics_{key_prefix}']=diagnostics
            if matches:
                st.session_state[f'v24_barcode_matches_{key_prefix}']=matches
                st.session_state[f'v24_lookup_barcode_clean_{key_prefix}']=code
                st.success(f'Found {len(matches)} possible match(es). Choose one below to auto-fill the listing draft.')
            else:
                st.warning('No exact or partial barcode matches found. Try artist/title search or enter the item manually.')

    if text_search_clicked:
        with st.spinner('Searching Discogs, Apple/iTunes, and MusicBrainz...'):
            matches,diagnostics=lookup_by_artist_title_with_diagnostics(search_artist,search_title,barcode)
        st.session_state[f'v25_lookup_diagnostics_{key_prefix}']=diagnostics
        if matches:
            st.session_state[f'v24_barcode_matches_{key_prefix}']=matches
            st.session_state[f'v24_lookup_barcode_clean_{key_prefix}']=normalize_barcode(barcode)
            best=choose_best_search_result(matches,search_artist,search_title,barcode)
            st.session_state[f'v25_best_match_{key_prefix}']=best
            st.success(f'Found {len(matches)} possible match(es). A recommended best match was selected below.')
        else:
            st.warning('No artist/title match found. Review diagnostics below, then manually enter the product if needed.')

    st.markdown('### Smart best-match search')
    st.caption('This searches all connected sources inside the app, ranks the candidates, and presents one recommended match.')
    if st.button('Smart Search: Find Best Match',key=f'v25_smart_search_button_{key_prefix}'):
        with st.spinner('Searching all connected sources and choosing the best match...'):
            best,ranked,diagnostics=run_smart_best_match_search(
                st.session_state.get(f'v25_search_artist_{key_prefix}',''),
                st.session_state.get(f'v25_search_title_{key_prefix}',''),
                barcode
            )
        st.session_state[f'v25_lookup_diagnostics_{key_prefix}']=diagnostics
        st.session_state[f'v25_best_match_{key_prefix}']=best
        st.session_state[f'v24_barcode_matches_{key_prefix}']=ranked
        st.session_state[f'v24_lookup_barcode_clean_{key_prefix}']=normalize_barcode(barcode)
        if best:
            st.success('Smart search selected a recommended best match.')
        else:
            st.warning('Smart search could not find a strong match. Use manual seed or backup links.')

    current_artist=st.session_state.get(f'v25_search_artist_{key_prefix}','')
    current_title=st.session_state.get(f'v25_search_title_{key_prefix}','')
    render_best_match_card(
        st.session_state.get(f'v25_best_match_{key_prefix}'),
        key_prefix,
        st.session_state.get(f'v24_barcode_matches_{key_prefix}',[]),
        current_artist,
        current_title,
        barcode
    )

    show_barcode_diagnostics(st.session_state.get(f'v25_lookup_diagnostics_{key_prefix}',[]))
    show_universal_search_links(current_artist,current_title,barcode)
    manual_release_seed_form(current_artist,current_title,barcode,key_prefix)



    matches=st.session_state.get(f'v24_barcode_matches_{key_prefix}',[])
    if matches:
        partial_count=sum(1 for m in matches if safe(m.get('_barcode_match_type'))=='partial')
        if partial_count:
            st.markdown('### Possible matches from partial barcode')
            st.caption('These are possible or broad matches, not exact barcode matches. Review full barcode and release details before using one.')
        labels=[f"{i+1}. {safe(m.get('artist'))} - {safe(m.get('title'))} ({barcode_match_label(m,current_artist,current_title)}, {safe(m.get('source'))}, {safe(m.get('release_year'))})" for i,m in enumerate(matches)]
        pick=st.selectbox('Possible barcode matches',labels,key=f'v24_match_select_{key_prefix}')
        idx=int(pick.split('.',1)[0])-1
        selected=matches[idx]
        colA,colB=st.columns([1,2])
        with colA:
            if safe(selected.get('image_url')):
                safe_image(safe(selected.get('image_url')),width='stretch',fallback_text='Release image unavailable.')
            else:
                st.info('No image returned.')
        with colB:
            st.write(f"**Match type:** {barcode_match_label(selected,current_artist,current_title)}")
            st.write(f"**Full barcode:** {safe(selected.get('barcode'),'Not listed')}")
            st.write(f"**Artist:** {safe(selected.get('artist'))}")
            st.write(f"**Title:** {safe(selected.get('title'))}")
            st.write(f"**Format:** {safe(selected.get('format'))}")
            st.write(f"**Label:** {safe(selected.get('label'))}")
            st.write(f"**Year:** {safe(selected.get('release_year'))}")
            st.write(f"**Country:** {safe(selected.get('country'),'Not listed')}")
            st.write(f"**Catalog number:** {safe(selected.get('catalog_number'),'Not listed')}")
            st.write(f"**Source:** {safe(selected.get('source'))}")
            if safe(selected.get('external_url')):
                st.write(f"External release URL: {safe(selected.get('external_url'))}")
        a,b,c=st.columns(3)
        if a.button('Use this release',key=f'v24_use_match_{key_prefix}'):
            st.session_state['v24_autofill_listing']=selected
            st.session_state['v24_autofill_barcode']=normalize_barcode(selected.get('barcode')) or st.session_state.get(f'v24_lookup_barcode_clean_{key_prefix}',normalize_barcode(barcode))
            try:
                rid=create_or_update_how_release(st.session_state['v24_autofill_barcode'],selected)
                st.session_state['v25_release_id']=rid
            except Exception:
                pass
            st.success('Listing draft filled and saved to the House Of Wax release database. Scroll to the Add Product form and review before saving.')
        if b.button('None of these - search another way',key=f'v42_none_of_these_{key_prefix}'):
            st.session_state[f'v24_barcode_matches_{key_prefix}']=[]
            st.info('Use artist/title search above or try a longer barcode fragment.')
            st.rerun()
        if c.button('Enter manually',key=f'v42_enter_manually_{key_prefix}'):
            st.session_state['v24_autofill_listing']={}
            st.session_state['v24_autofill_barcode']=normalize_barcode(barcode)
            st.info('Scroll to Add Inventory and enter the item details manually.')

def v24_listing_defaults():
    selected=st.session_state.get('v24_autofill_listing',{})
    barcode=st.session_state.get('v24_autofill_barcode','')
    return {
        'barcode':barcode,
        'artist':safe(selected.get('artist')),
        'title':safe(selected.get('title')),
        'format':safe(selected.get('format')),
        'label':safe(selected.get('label')),
        'release_year':safe(selected.get('release_year')),
        'genre':safe(selected.get('genre')) or safe(selected.get('style')),
        'catalog_number':safe(selected.get('catalog_number')),
        'image_url':safe(selected.get('image_url')),
        'external_url':safe(selected.get('external_url')),
    }



# ---------- V25 House Of Wax Release Database ----------
def gs1_basic_validation(barcode):
    code=normalize_barcode(barcode)
    if not code or not code.isdigit():
        return 'Not checked'
    if len(code) in [8,12,13,14]:
        return 'Valid format'
    return 'Invalid length'

def release_confidence_from_result(result):
    score=40
    if safe(result.get('source'))=='Discogs':
        score+=25
    if safe(result.get('source'))=='MusicBrainz':
        score+=15
    for field in ['artist','title','format','label','release_year','image_url','external_url']:
        if safe(result.get(field)):
            score+=5
    return min(score,100)

def find_how_release_by_barcode(barcode):
    code=normalize_barcode(barcode)
    if not code:
        return pd.DataFrame()
    return df("SELECT * FROM how_releases WHERE barcode=? ORDER BY source_confidence DESC, id DESC",(code,))

def create_or_update_how_release(barcode, result, seller_note=''):
    code=normalize_barcode(barcode)
    if not code:
        return None
    source=safe(result.get('source'))
    ext_id=safe(result.get('external_id'))
    discogs_id=ext_id if source=='Discogs' else ''
    mb_id=ext_id if source=='MusicBrainz' else ''
    confidence=release_confidence_from_result(result)
    existing=find_how_release_by_barcode(code)
    if not existing.empty:
        rid=int(existing.iloc[0]['id'])
        # Update only if current result has stronger confidence or fills empty fields.
        current=int(existing.iloc[0].get('source_confidence') or 0)
        if confidence >= current:
            run("""UPDATE how_releases SET artist=?,title=?,format=?,label=?,release_year=?,country=?,genre=?,style=?,catalog_number=?,image_url=?,external_release_url=?,discogs_id=COALESCE(NULLIF(?,''),discogs_id),musicbrainz_id=COALESCE(NULLIF(?,''),musicbrainz_id),gs1_status=?,source_confidence=?,seller_correction_notes=?,updated_at=? WHERE id=?""",
                (safe(result.get('artist')),safe(result.get('title')),safe(result.get('format')),safe(result.get('label')),safe(result.get('release_year')),safe(result.get('country')),safe(result.get('genre')),safe(result.get('style')),safe(result.get('catalog_number')),safe(result.get('image_url')),safe(result.get('external_url')),discogs_id,mb_id,gs1_basic_validation(code),confidence,seller_note,now(),rid))
    else:
        run("""INSERT INTO how_releases(barcode,artist,title,format,label,release_year,country,genre,style,catalog_number,image_url,external_release_url,discogs_id,musicbrainz_id,gs1_status,source_confidence,verification_status,admin_notes,seller_correction_notes,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (code,safe(result.get('artist')),safe(result.get('title')),safe(result.get('format')),safe(result.get('label')),safe(result.get('release_year')),safe(result.get('country')),safe(result.get('genre')),safe(result.get('style')),safe(result.get('catalog_number')),safe(result.get('image_url')),safe(result.get('external_url')),discogs_id,mb_id,gs1_basic_validation(code),confidence,'Unverified','',seller_note,now(),now()))
        rid=int(df("SELECT id FROM how_releases WHERE barcode=? ORDER BY id DESC LIMIT 1",(code,)).iloc[0]['id'])
    # Add source row if not already present
    if source:
        exists=df("SELECT id FROM how_release_sources WHERE release_id=? AND source_name=? AND source_external_id=?",(rid,source,ext_id))
        if exists.empty:
            run("""INSERT INTO how_release_sources(release_id,source_name,source_external_id,source_url,source_confidence,raw_summary,created_at) VALUES(?,?,?,?,?,?,?)""",
                (rid,source,ext_id,safe(result.get('external_url')),confidence,safe(result.get('raw_summary')),now()))
    return rid

def get_best_how_release(barcode):
    code=normalize_barcode(barcode)
    if not code:
        return None
    r=df("SELECT * FROM how_releases WHERE barcode=? ORDER BY CASE verification_status WHEN 'Approved' THEN 1 WHEN 'Needs Review' THEN 2 ELSE 3 END, source_confidence DESC, id DESC LIMIT 1",(code,))
    if r.empty:
        return None
    return r.iloc[0].to_dict()

def how_release_to_autofill(release):
    if not release:
        return {}
    return {
        'source':'House Of Wax',
        'external_id':safe(release.get('id')),
        'barcode':normalize_barcode(release.get('barcode')),
        'artist':safe(release.get('artist')),
        'title':safe(release.get('title')),
        'format':safe(release.get('format')),
        'label':safe(release.get('label')),
        'release_year':safe(release.get('release_year')),
        'country':safe(release.get('country')),
        'genre':safe(release.get('genre')),
        'style':safe(release.get('style')),
        'catalog_number':safe(release.get('catalog_number')),
        'image_url':safe(release.get('image_url')),
        'external_url':safe(release.get('external_release_url')),
        'raw_summary':'House Of Wax internal release database match'
    }

def cache_row_to_autofill(row):
    return {k:row.get(k,'') for k in ['barcode','source','external_id','artist','title','format','label','release_year','country','genre','style','catalog_number','image_url','external_url','raw_summary']}

def find_partial_barcode_matches(fragment, limit=12):
    code=normalize_barcode(fragment)
    if len(code)<5:
        return []
    results=[]
    seen=set()
    releases=df("""SELECT * FROM how_releases
        WHERE barcode LIKE ?
        ORDER BY source_confidence DESC, id DESC
        LIMIT ?""",(f'%{code}%',int(limit)))
    for _,release in releases.iterrows():
        res=how_release_to_autofill(release.to_dict())
        key=('how',normalize_barcode(res.get('barcode')),safe(res.get('artist')).lower(),safe(res.get('title')).lower())
        if key not in seen:
            seen.add(key)
            results.append(res)
    remaining=max(int(limit)-len(results),0)
    if remaining:
        cached=df("""SELECT * FROM barcode_lookup_cache
            WHERE barcode LIKE ?
            ORDER BY id DESC
            LIMIT ?""",(f'%{code}%',remaining))
        for _,row in cached.iterrows():
            res=cache_row_to_autofill(row)
            key=('cache',normalize_barcode(res.get('barcode')),safe(res.get('source')).lower(),safe(res.get('external_id')).lower(),safe(res.get('artist')).lower(),safe(res.get('title')).lower())
            if key not in seen:
                seen.add(key)
                results.append(res)
    return mark_barcode_results(results,'partial',code)

def submit_release_correction(release_id, seller_id, field_name, old_value, suggested_value, note):
    run("""INSERT INTO how_release_corrections(release_id,seller_id,field_name,old_value,suggested_value,correction_note,status,created_at) VALUES(?,?,?,?,?,?,?,?)""",
        (release_id,seller_id,field_name,old_value,suggested_value,note,'Pending',now()))

def release_database_admin():
    st.subheader('House Of Wax Release Database')
    st.write('This is the internal House Of Wax reference library built from barcode scans, Discogs/MusicBrainz results, seller corrections, and admin approval.')
    q=st.text_input('Search release database',placeholder='barcode, artist, title, label, catalog number')
    where=''
    params=()
    if q:
        like=f"%{q}%"
        where="WHERE barcode LIKE ? OR artist LIKE ? OR title LIKE ? OR label LIKE ? OR catalog_number LIKE ?"
        params=(like,like,like,like,like)
    releases=df(f"SELECT * FROM how_releases {where} ORDER BY id DESC LIMIT 200",params)
    st.dataframe(releases,width='stretch')
    if not releases.empty:
        labels=[f"{int(r.id)} - {safe(r.artist)} - {safe(r.title)} [{safe(r.barcode)}]" for _,r in releases.iterrows()]
        pick=st.selectbox('Review release',labels,key='v25_release_admin_pick')
        rid=int(pick.split(' - ')[0])
        row=df("SELECT * FROM how_releases WHERE id=?",(rid,)).iloc[0]
        with st.form('release_review_form'):
            c1,c2=st.columns(2)
            artist=c1.text_input('Artist',value=safe(row.get('artist')))
            title=c2.text_input('Title',value=safe(row.get('title')))
            c3,c4,c5=st.columns(3)
            fmt=c3.text_input('Format',value=safe(row.get('format')))
            label=c4.text_input('Label',value=safe(row.get('label')))
            year=c5.text_input('Release year',value=safe(row.get('release_year')))
            c6,c7,c8=st.columns(3)
            genre=c6.text_input('Genre',value=safe(row.get('genre')))
            cat=c7.text_input('Catalog number',value=safe(row.get('catalog_number')))
            confidence=c8.number_input('Confidence',min_value=0,max_value=100,value=int(row.get('source_confidence') or 50))
            image=st.text_input('Image URL',value=safe(row.get('image_url')))
            external=st.text_input('External release URL',value=safe(row.get('external_release_url')))
            status=st.selectbox('Verification status',['Unverified','Needs Review','Approved','Rejected'],index=['Unverified','Needs Review','Approved','Rejected'].index(safe(row.get('verification_status'),'Unverified') if safe(row.get('verification_status')) in ['Unverified','Needs Review','Approved','Rejected'] else 'Unverified'))
            notes=st.text_area('Admin notes',value=safe(row.get('admin_notes')))
            save=st.form_submit_button('Save release review')
            if save:
                run("""UPDATE how_releases SET artist=?,title=?,format=?,label=?,release_year=?,genre=?,catalog_number=?,source_confidence=?,image_url=?,external_release_url=?,verification_status=?,admin_notes=?,updated_at=? WHERE id=?""",
                    (artist,title,fmt,label,year,genre,cat,int(confidence),image,external,status,notes,now(),rid))
                st.success('Release review saved.')
        sources=df("SELECT * FROM how_release_sources WHERE release_id=? ORDER BY id DESC",(rid,))
        corrections=df("SELECT * FROM how_release_corrections WHERE release_id=? ORDER BY id DESC",(rid,))
        st.markdown('### Sources')
        st.dataframe(sources,width='stretch')
        st.markdown('### Seller corrections')
        st.dataframe(corrections,width='stretch')

def listing_quality_assessment(category='', artist='', title='', price=0, description='', mg='', sg='', image='', has_uploaded_photo=False, smart_confidence=''):
    try:
        priced=float(price or 0)>0
    except Exception:
        priced=False
    condition_ok=(bool(safe(mg)) and safe(mg)!='N/A') or (bool(safe(sg)) and safe(sg)!='N/A')
    checks=[
        ('Category selected',bool(safe(category)),1),
        ('Artist / brand added',bool(safe(artist)),1),
        ('Title added',bool(safe(title)),1),
        ('Price added',priced,1),
        ('Quantity added',True,1),
        ('Condition selected',condition_ok,1),
        ('Photo added',bool(safe(image)) or bool(has_uploaded_photo),1),
        ('Seller notes added, optional',bool(safe(description)),0),
    ]
    possible=sum(weight for _,_,weight in checks if weight)
    earned=sum(weight for _,ok,weight in checks if ok and weight)
    score=int(round((earned / possible) * 100)) if possible else 0
    if earned>=possible:
        label='Ready to submit'
    elif earned>=max(possible-2,1):
        label='Almost ready'
    else:
        label='Needs basics'
    return score,label,checks

def render_listing_quality(score, label, checks, context='seller'):
    st.markdown('#### Listing readiness checklist')
    if context=='admin':
        st.caption(f'Readiness: {label} ({score}/100). This is a practical completeness check, not a grade of the seller writing.')
    else:
        st.caption('This is a simple checklist for the basics. It does not grade how you write.')
    with st.expander('Listing readiness checklist',expanded=(context!='seller')):
        for text,ok,weight in checks:
            prefix='✓ ' if ok else ('• Optional: ' if not weight else '• Add: ')
            st.write(prefix+text)
    if label=='Ready to submit':
        st.success('Ready to submit.')
    elif context=='admin':
        st.info('Review the missing basics before approving.')

def listing_preview_card(category, artist, title, fmt, label, year, genre, mg, sg, price, qty, ship, image, description, has_uploaded_photo=False, smart_confidence='', quality_context='seller', photo_previews=None):
    st.markdown('#### Listing preview')
    photo_previews=photo_previews or []
    with st.container(border=True):
        c1,c2=st.columns([1,1.6])
        with c1:
            if photo_previews:
                st.caption(photo_previews[0][0])
                safe_image(photo_previews[0][1],width='stretch',fallback_text='Preview image unavailable.')
            elif safe(image):
                st.caption('Search/database image or supporting product image')
                safe_image(safe(image),width='stretch',fallback_text='Preview image unavailable.')
            else:
                st.info('No image selected yet.')
            if len(photo_previews)>1:
                st.caption('Supporting / condition photo previews')
                cols=st.columns(2)
                for i,(caption,img) in enumerate(photo_previews[1:5]):
                    with cols[i%2]:
                        safe_image(img,caption=caption,width='stretch',fallback_text='Preview image unavailable.')
        with c2:
            heading=' - '.join([p for p in [safe(artist),safe(title)] if p]) or 'Untitled listing'
            st.subheader(heading)
            st.caption(f"{safe(category)} • {safe(fmt) or 'Format not set'} • {safe(year) or 'Year not set'}")
            if safe(label):
                st.write(f"**Label / Brand:** {safe(label)}")
            if safe(genre):
                st.write(f"**Genre / style:** {safe(genre)}")
            st.write(f"**Condition:** Media/Product {safe(mg)} • Sleeve/Packaging {safe(sg)}")
            st.write(f"**Price:** {money(price)} • **Qty:** {int(qty)} • **Shipping:** {money(ship)}")
            st.write(safe(description,'No description yet.'))
            score,quality_label,checks=listing_quality_assessment(category,artist,title,price,description,mg,sg,image,has_uploaded_photo,smart_confidence)
            render_listing_quality(score,quality_label,checks,quality_context)


def upload_product(sid,key):
    defaults=v24_listing_defaults()
    selected_match=st.session_state.get('v24_autofill_listing',{})
    discogs_release_id=safe(selected_match.get('external_id')) if safe(selected_match.get('source'))=='Discogs' else ''
    seller=get_seller(int(sid))
    seller_status=normalize_seller_status(seller.get('status') if seller is not None else '')
    is_approved=seller_can_publish(seller)
    rules_ok=seller_rules_accepted(seller)
    can_publish=seller_can_publish_live(seller)
    st.markdown('### Add Inventory')
    st.write('Create one item at a time. You can save as draft, or publish directly once your seller account is approved and seller rules are accepted.')
    seller_status_notice(seller)
    listing_status_help()
    if defaults:
        source_bits=[v for v in [defaults.get('artist'),defaults.get('title'),defaults.get('label'),defaults.get('release_year')] if safe(v)]
        if source_bits:
            st.info('House Of Wax search/database fields are prefilled below. Review them before submitting.')
    st.markdown('#### Condition')
    st.caption('Set this first so House Of Wax can suggest a price range for your specific condition -- better condition supports a higher price.')
    cg1,cg2=st.columns(2)
    mg=cg1.selectbox('Condition - required',GRADE_SCALE,key=f'upload_mg_{key}',help='Tell buyers the condition of the copy you are selling.')
    sg=cg2.selectbox('Sleeve/packaging condition - optional',GRADE_SCALE,key=f'upload_sg_{key}')
    price_suggestion=suggest_seller_price_range(defaults.get('artist'),discogs_release_id,mg,sg) if defaults.get('artist') else None
    if price_suggestion:
        grade_note=f" for {price_suggestion['grade_used']} condition" if price_suggestion.get('grade_used') else ''
        st.info(f"Suggested price range{grade_note}: {money(price_suggestion['low'])}–{money(price_suggestion['high'])}, based on {price_suggestion['source']}. You set the final price.")
    with st.form(key):
        st.markdown('#### Step 1: Find the item')
        st.caption('Search by barcode, artist/title, or item name. If this is a record, CD, or cassette, House Of Wax will try to find the album information for you.')
        c1,c2,c3=st.columns(3)
        barcode=c1.text_input('Barcode / UPC / EAN - optional search field',value=defaults.get('barcode',''),help='Enter the full barcode when available. You may also enter at least 5-6 digits to look for possible matches.')
        catalog=c2.text_input('Catalog number - auto-filled if found',value=defaults.get('catalog_number',''))
        matrix=c3.text_input('Matrix / runout - optional')

        st.markdown('#### Step 2: Confirm item details')
        st.caption('Check the artist, title, format, label, year, and category. These may be filled automatically if the item is found.')
        c4,c5,c6=st.columns(3)
        category=c4.selectbox('Category - required',['Vinyl Records','CDs','Cassettes','Albums','Music Releases','Clothing','Music Memorabilia','Culture Goods','House Of Wax Merch','Official Drops','Slipmats & Accessories'])
        artist=c5.text_input('Artist / Brand - usually auto-filled',value=defaults.get('artist',''),help='Usually filled automatically after search.')
        title=c6.text_input('Title / Product - required',value=defaults.get('title',''),help='Usually filled automatically after search.')
        c7,c8,c9=st.columns(3)
        fmt_default=defaults.get('format','') or ('Vinyl' if category=='Vinyl Records' else '')
        fmt=c7.text_input('Format - auto-filled if found',value=fmt_default,help='Filled automatically if found.')
        label=c8.text_input('Label / Brand - auto-filled if found',value=defaults.get('label',''),help='Filled automatically if found.')
        year=c9.text_input('Release year - auto-filled if found',value=defaults.get('release_year',''),help='Filled automatically if found.')
        genre=st.text_input('Genre / style - auto-filled if found',value=defaults.get('genre',''))
        external_release_url=st.text_input('External release URL - optional',value=defaults.get('external_url',''))

        st.markdown('#### Step 3: Add your selling details')
        st.caption('Now add the details that are specific to the copy you are selling.')
        sku=st.text_input('SKU - optional')
        if is_music_category(category):
            st.info('For most music listings, the album cover image is enough to get started. Your own photos are optional.')
        else:
            st.info('For unique or non-music items, adding your own photo is recommended.')
        st.caption(f"Condition: {safe(mg)} • Sleeve/packaging: {safe(sg)} (set above)")
        notes=st.text_area('Seller notes - optional',help='Optional. Add anything buyers should know.')
        desc=st.text_area('Extra description - optional',help='Optional. Add anything buyers should know.')
        c10,c11,c12=st.columns(3)
        price_text=c10.text_input('Price - required',help='Type your asking price. Examples: 10, 10.00, or $10.00.',placeholder='10.00')
        qty_text=c11.text_input('Quantity - required',value='1',help='Type the number of copies/items you have.')
        ship_text=c12.text_input('Shipping price - optional',help='Type shipping price if needed. Examples: 5, 5.00, or $5.00.',placeholder='0.00')
        if is_music_category(category):
            st.caption('Shipping tip: records, CDs, cassettes, and printed music qualify for USPS Media Mail — usually the cheapest way to ship them (typically ~$5-6 for a single record, a few dollars more per extra pound). It ships slower than Priority (about 2-8 business days) and the package can only contain qualifying media, no extras like stickers, merch, or a handwritten note longer than a few lines. Confirm the current rate at usps.com before setting your price.')
        else:
            st.caption('Shipping tip: USPS Media Mail does not apply to clothing, memorabilia, or merch — use USPS Ground Advantage or a similar standard parcel rate instead. Check usps.com for current pricing.')
        price,price_error=parse_money_input(price_text,'Price')
        qty,qty_error=parse_quantity_input(qty_text)
        ship,ship_error=parse_money_input(ship_text,'Shipping price')
        if price_error:
            st.warning(price_error)
        if qty_error:
            st.warning(qty_error)
        if ship_error:
            st.warning(ship_error)

        st.markdown('#### Step 4: Photos')
        st.caption('Prototype storage: uploaded images are saved locally under house_of_wax_uploads/product_images. Production launch should use hosted storage.')
        refimgurl=st.text_input('Reference image - official release art, auto-filled if found',value=defaults.get('image_url',''),help='This is official release art from the House Of Wax database or outside sources (Discogs/MusicBrainz), not a photo of your exact copy. It is shown to buyers labeled as reference art.')
        if safe(refimgurl):
            st.success('Reference image found automatically. No action needed.')
        else:
            st.info('No reference image found yet. You can still save the listing, or add a photo below.')
        st.caption('Adding your own photos below is optional. Listings with real seller photos get a "Seller photos included" badge buyers can see.')
        main_img=st.file_uploader('Your own main photo - optional',type=['png','jpg','jpeg','webp'],key=f'main_photo_{key}')
        supporting_imgs=st.file_uploader('Extra photos - optional',type=['png','jpg','jpeg','webp'],accept_multiple_files=True,key=f'supporting_photos_{key}')
        condition_imgs=st.file_uploader('Condition photos - optional',type=['png','jpg','jpeg','webp'],accept_multiple_files=True,key=f'condition_photos_{key}')
        video_url_input=st.text_input('Video URL - optional (YouTube link or other video link)',value=defaults.get('video_url',''),help='Shows a playable video on your listing, e.g. a needle-drop or item walkthrough.',key=f'video_url_{key}')
        uploaded_previews=[]
        if main_img is not None:
            uploaded_previews.append(('Main listing photo',main_img))
        for i,up in enumerate(supporting_imgs or [],1):
            uploaded_previews.append((f'Supporting photo {i}',up))
        for i,up in enumerate(condition_imgs or [],1):
            uploaded_previews.append((f'Condition photo {i}',up))
        has_uploaded_photos=bool(uploaded_previews)
        imgurl=refimgurl

        st.markdown('#### Preview')
        preview_description=desc or f'{artist} - {title}. {notes}'
        search_key='upload_product' if key=='normal_upload' else key
        smart_match=st.session_state.get(f'v25_best_match_{search_key}',{})
        smart_confidence=match_confidence_label(smart_match,artist,title) if smart_match else ''
        preview_image=main_img if main_img is not None else imgurl
        listing_preview_card(category,artist,title,fmt,label,year,genre,mg,sg,price,qty,ship,preview_image,preview_description,has_uploaded_photos,smart_confidence,'seller',uploaded_previews)

        st.markdown('#### Step 5: Save or publish')
        st.caption('Save as Draft if you are not ready. Approved sellers can Publish to My Store after accepting House Of Wax seller rules.')
        st.info('Before publishing, confirm the item details, condition, price, and seller notes are accurate. You are responsible for your listing under House Of Wax rules.')
        if not is_approved:
            if seller_status=='Suspended Seller':
                st.error('Your seller account is suspended. Contact House Of Wax for review.')
            else:
                st.warning('Your seller account must be approved before you can publish listings.')
        elif not rules_ok:
            st.warning('Accept seller rules before publishing.')
        c13,c14=st.columns(2)
        save_draft=c13.form_submit_button('Save as Draft')
        publish_listing=c14.form_submit_button('Publish to My Store')
    release_id=st.session_state.get('v25_release_id')
    if release_id:
        with st.expander('Suggest a correction to the House Of Wax release database'):
            st.write('If the auto-filled release data is wrong or incomplete, suggest a correction. Admin can review it later.')
            field_name=st.selectbox('Field to correct',['artist','title','format','label','release_year','genre','catalog_number','image_url','external_release_url'],key=f'corr_field_{key}')
            suggested=st.text_input('Suggested value',key=f'corr_value_{key}')
            note=st.text_area('Correction note',key=f'corr_note_{key}')
            if st.button('Submit correction',key=f'corr_submit_{key}'):
                old_val=defaults.get(field_name,'')
                submit_release_correction(int(release_id),sid,field_name,old_val,suggested,note)
                st.success('Correction submitted for review.')
    if save_draft or publish_listing:
        if not safe(price_text):
            st.error('Price is required. Type your asking price, like 10, 10.00, or $10.00.')
            return
        if price_error or qty_error or ship_error:
            st.error('Fix the price, quantity, or shipping field before saving.')
            return
        if publish_listing and not is_approved:
            st.error('Your seller account must be approved before you can publish listings.')
            return
        if publish_listing and not rules_ok:
            st.error('Accept seller rules before publishing.')
            return
        saved_main=save_file(main_img,'product_images')
        saved_supporting=save_files(supporting_imgs,'product_images')
        saved_condition=save_files(condition_imgs,'product_images')
        image=saved_main or imgurl
        description=desc or f'{artist} — {title}. {notes}'
        listing_status='Live' if publish_listing else 'Draft'
        has_saved_seller_photos=bool(saved_main or saved_supporting or saved_condition)
        score,quality_label,_=listing_quality_assessment(category,artist,title,price,description,mg,sg,image,has_saved_seller_photos,smart_confidence)
        product_data={'seller_id':int(sid),'sku':sku,'barcode':barcode,'catalog_number':catalog,'matrix_runout':matrix,'category':category,'artist':artist,'title':title,'format':fmt,'label':label,'release_year':year,'genre':genre,'media_grade':mg,'sleeve_grade':sg,'condition_notes':notes,'description':description,'price':float(price),'quantity':int(qty),'shipping_price':float(ship),'image_url':image,'reference_image_url':safe(refimgurl).strip(),'video_url':safe(video_url_input).strip(),'audio_url':'','external_release_url':external_release_url,'listing_status':listing_status,'listing_type':'Fixed Price','created_at':now(),'updated_at':now()}
        product_keys=['seller_id','sku','barcode','catalog_number','matrix_runout','category','artist','title','format','label','release_year','genre','media_grade','sleeve_grade','condition_notes','description','price','quantity','shipping_price','image_url','reference_image_url','video_url','audio_url','external_release_url','listing_status','listing_type','created_at','updated_at']
        pid=core_insert('products',product_data,"""INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,reference_image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",tuple(product_data[k] for k in product_keys))
        if not pid and hosted_enabled():
            st.error('This listing could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error')+' Nothing was published -- please try again.')
            return
        if listing_status=='Live':
            notify_want_list_matches(product_data)
        if saved_main:
            core_insert('product_gallery',{'product_id':int(pid),'image_url':saved_main,'caption':'Main listing photo - seller uploaded exact item photo','created_at':now()},'INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)',(int(pid),saved_main,'Main listing photo - seller uploaded exact item photo',now()))
        for i,path in enumerate(saved_supporting,1):
            core_insert('product_gallery',{'product_id':int(pid),'image_url':path,'caption':f'Supporting photo {i}','created_at':now()},'INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)',(int(pid),path,f'Supporting photo {i}',now()))
        for i,path in enumerate(saved_condition,1):
            core_insert('product_gallery',{'product_id':int(pid),'image_url':path,'caption':f'Condition photo {i}','created_at':now()},'INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)',(int(pid),path,f'Condition photo {i}',now()))
        if listing_status=='Live':
            st.success('Published. This item is now live in your store.')
        if is_music_category(category) and imgurl and not has_saved_seller_photos:
            st.success(f'Inventory saved as {listing_status} using the album cover image.')
        elif is_music_category(category) and not image:
            st.info(f'Inventory saved as {listing_status}. No cover image found, and no personal photo is required to save.')
        elif not is_music_category(category) and not image:
            st.warning(f'Listing saved as {listing_status}, but this non-music item should have an exact item or official product image before review.')
        elif not has_saved_seller_photos:
            st.info(f'Inventory saved as {listing_status}. You can add optional photos later.')
        else:
            st.success(f'Inventory saved as {listing_status}.')
        st.session_state['last_saved_listing_id']=int(pid or 0)
        st.session_state['last_saved_listing_seller_id']=int(sid)
        st.session_state['last_saved_listing_status']=listing_status
        st.session_state['pending_seller_tools_primary_section']='My Inventory'
        st.success('Inventory saved.')
        st.success('Saved. You can find this item in My Inventory.')
        c_view,c_market,c_add=st.columns(3)
        if c_view.button('View in My Inventory',key=f'view_inventory_after_save_{key}_{int(pid or 0)}'):
            st.session_state['pending_seller_tools_primary_section']='My Inventory'
            st.rerun()
        if listing_status=='Live' and c_market.button('View in Marketplace',key=f'view_marketplace_after_save_{key}_{int(pid or 0)}'):
            st.session_state['product_id']=int(pid or 0)
            product_detail(int(pid or 0))
        elif listing_status=='Draft':
            c_market.info('Publish to show this item in Marketplace.')
        if c_add.button('Add Another Item',key=f'add_another_after_save_{key}_{int(pid or 0)}'):
            st.session_state['pending_seller_tools_primary_section']='Add Inventory'
            st.rerun()
        if listing_status=='Draft':
            c_publish=st.columns(1)[0]
            if can_publish and c_publish.button('Publish to My Store',key=f'publish_after_save_{key}_{int(pid or 0)}'):
                core_update('products',{'listing_status':'Live','updated_at':now()},{'id':int(pid),'seller_id':int(sid)},'UPDATE products SET listing_status=?,updated_at=? WHERE id=? AND seller_id=?',('Live',now(),int(pid),int(sid)))
                st.success('Published. This item is now live in your store.')
                st.session_state['pending_seller_tools_primary_section']='My Inventory'
                st.rerun()
            elif not is_approved:
                c_publish.info('Seller approval required before publishing.')
            elif not rules_ok:
                c_publish.info('Accept seller rules before publishing.')
    last_id=int(st.session_state.get('last_saved_listing_id') or 0)
    last_sid=int(st.session_state.get('last_saved_listing_seller_id') or 0)
    if last_id and last_sid==int(sid):
        last_row=hosted_select('products',{'id':last_id,'seller_id':int(sid)},limit=1) if hosted_enabled() else df('SELECT * FROM products WHERE id=? AND seller_id=?',(last_id,int(sid)))
        if not last_row.empty:
            current_status=safe(last_row.iloc[0].get('listing_status'))
            with st.container(border=True):
                st.write(f"**Last saved item:** {safe(last_row.iloc[0].get('artist'))} - {safe(last_row.iloc[0].get('title'))}")
                st.write(f"**Status:** {current_status}")
                a,b,c=st.columns(3)
                if current_status=='Live' and a.button('View in Marketplace',key=f'persistent_view_marketplace_{last_id}'):
                    st.session_state['product_id']=last_id
                    product_detail(last_id)
                elif current_status!='Live':
                    a.info('Publish to show this item in Marketplace.')
                if current_status=='Draft':
                    if can_publish and b.button('Publish to My Store',key=f'persistent_publish_listing_{last_id}'):
                        core_update('products',{'listing_status':'Live','updated_at':now()},{'id':last_id,'seller_id':int(sid)},'UPDATE products SET listing_status=?,updated_at=? WHERE id=? AND seller_id=?',('Live',now(),last_id,int(sid)))
                        st.success('Published. This item is now live in your store.')
                        st.rerun()
                    elif not is_approved:
                        b.info('Seller approval required before publishing.')
                    elif not rules_ok:
                        b.info('Accept seller rules before publishing.')
                if c.button('Clear last saved item',key=f'clear_last_saved_listing_{last_id}'):
                    st.session_state.pop('last_saved_listing_id',None)
                    st.session_state.pop('last_saved_listing_seller_id',None)
                    st.session_state.pop('last_saved_listing_status',None)
                    st.rerun()

def seller_inquiry_view(sid):
    st.subheader('Buyer inquiries')
    st.info('House Of Wax keeps seller contact details controlled. Respond using the buyer-provided contact method and avoid sharing sensitive information publicly.')
    inquiries=enrich_activity_rows(hosted_select('listing_inquiries',{'seller_id':int(sid)},order='created_at.desc')) if hosted_enabled() else df("""SELECT i.*,p.artist,p.title,p.category,p.listing_status FROM listing_inquiries i LEFT JOIN products p ON i.product_id=p.id WHERE i.seller_id=? ORDER BY i.created_at DESC""",(sid,))
    if inquiries.empty:
        st.info('No buyer inquiries yet.')
        return
    status_filter=st.selectbox('Inquiry status filter',['All']+INQUIRY_STATUSES,key='seller_inquiry_status_filter')
    shown=inquiries if status_filter=='All' else inquiries[inquiries['status']==status_filter]
    cols=[c for c in ['id','artist','title','buyer_name','buyer_contact','preferred_contact_method','message','status','created_at'] if c in shown.columns]
    st.dataframe(shown[cols],width='stretch')
    if shown.empty:
        st.info('No inquiries match that status.')
        return
    labels=[f"{int(r.id)} | {safe(r.artist)} - {safe(r.title)} | {safe(r.buyer_name)} | {safe(r.status)}" for _,r in shown.iterrows()]
    pick=st.selectbox('Open inquiry',labels,key='seller_inquiry_pick')
    iid=int(pick.split('|')[0].strip())
    row=shown[shown['id']==iid].iloc[0]
    with st.container(border=True):
        st.write(f"**Listing:** {safe(row.get('artist'))} - {safe(row.get('title'))}")
        st.write(f"**Buyer:** {safe(row.get('buyer_name'))}")
        st.write(f"**Buyer contact:** {safe(row.get('buyer_contact'))}")
        st.write(f"**Preferred contact method:** {safe(row.get('preferred_contact_method'))}")
        st.write(f"**Message:** {safe(row.get('message'))}")
        st.caption(f"Status: {safe(row.get('status'))} • Received {safe(row.get('created_at'))}")
        st.caption('Direct chat is not built yet. Respond using the buyer-provided contact method.')
    c1,c2=st.columns(2)
    if c1.button('Mark Seller Responded',key=f'seller_inquiry_responded_{iid}'):
        core_update('listing_inquiries',{'status':'Seller Responded','updated_at':now()},{'id':iid,'seller_id':int(sid)},"UPDATE listing_inquiries SET status='Seller Responded',updated_at=? WHERE id=? AND seller_id=?",(now(),iid,sid)); st.success('Inquiry marked Seller Responded.')
    if c2.button('Mark Closed',key=f'seller_inquiry_closed_{iid}'):
        core_update('listing_inquiries',{'status':'Closed','updated_at':now()},{'id':iid,'seller_id':int(sid)},"UPDATE listing_inquiries SET status='Closed',updated_at=? WHERE id=? AND seller_id=?",(now(),iid,sid)); st.success('Inquiry closed.')

def admin_inquiry_view():
    st.subheader('Buyer Inquiry Review')
    st.info('House Of Wax can monitor inquiries without exposing seller private contact details publicly. Do not share sensitive info in public areas.')
    inquiries=enrich_activity_rows(hosted_select('listing_inquiries',order='created_at.desc')) if hosted_enabled() else df("""SELECT i.*,p.artist,p.title,p.listing_status,s.store_name FROM listing_inquiries i LEFT JOIN products p ON i.product_id=p.id LEFT JOIN sellers s ON i.seller_id=s.id ORDER BY i.created_at DESC""")
    if inquiries.empty:
        st.info('No inquiries yet.')
        return
    status_filter=st.selectbox('Inquiry status filter',['All']+INQUIRY_STATUSES,key='admin_inquiry_status_filter')
    shown=inquiries if status_filter=='All' else inquiries[inquiries['status']==status_filter]
    cols=[c for c in ['id','store_name','artist','title','buyer_name','buyer_contact','preferred_contact_method','message','status','created_at'] if c in shown.columns]
    st.dataframe(shown[cols],width='stretch')
    if shown.empty:
        st.info('No inquiries match that status.')
        return
    labels=[f"{int(r.id)} | {safe(r.store_name)} | {safe(r.artist)} - {safe(r.title)} | {safe(r.status)}" for _,r in shown.iterrows()]
    pick=st.selectbox('Open inquiry',labels,key='admin_inquiry_pick')
    iid=int(pick.split('|')[0].strip())
    row=shown[shown['id']==iid].iloc[0]
    with st.container(border=True):
        st.write(f"**Seller:** {safe(row.get('store_name'))}")
        st.write(f"**Listing:** {safe(row.get('artist'))} - {safe(row.get('title'))}")
        st.write(f"**Buyer:** {safe(row.get('buyer_name'))} • {safe(row.get('buyer_contact'))}")
        st.write(f"**Preferred contact method:** {safe(row.get('preferred_contact_method'))}")
        st.write(f"**Message:** {safe(row.get('message'))}")
        st.caption(f"Status: {safe(row.get('status'))} • Received {safe(row.get('created_at'))}")
    if st.button('Mark Inquiry Closed',key=f'admin_inquiry_closed_{iid}'):
        core_update('listing_inquiries',{'status':'Closed','updated_at':now()},{'id':iid},"UPDATE listing_inquiries SET status='Closed',updated_at=? WHERE id=?",(now(),iid)); st.success('Inquiry closed.')

def update_purchase_request_status(request_id, status, seller_id=None):
    if seller_id is None:
        req=hosted_select('purchase_requests',{'id':int(request_id)},limit=1) if hosted_enabled() else df('SELECT product_id FROM purchase_requests WHERE id=?',(int(request_id),))
        core_update('purchase_requests',{'status':status,'updated_at':now()},{'id':int(request_id)},'UPDATE purchase_requests SET status=?,updated_at=? WHERE id=?',(status,now(),int(request_id)))
    else:
        req=hosted_select('purchase_requests',{'id':int(request_id),'seller_id':int(seller_id)},limit=1) if hosted_enabled() else df('SELECT product_id FROM purchase_requests WHERE id=? AND seller_id=?',(int(request_id),int(seller_id)))
        core_update('purchase_requests',{'status':status,'updated_at':now()},{'id':int(request_id),'seller_id':int(seller_id)},'UPDATE purchase_requests SET status=?,updated_at=? WHERE id=? AND seller_id=?',(status,now(),int(request_id),int(seller_id)))
    if not req.empty:
        pid=int(req.iloc[0]['product_id'])
        if status=='Pending Pickup/Payment':
            core_update('products',{'listing_status':'Pending Pickup/Payment','updated_at':now()},{'id':pid},"UPDATE products SET listing_status='Pending Pickup/Payment',updated_at=? WHERE id=?",(now(),pid))
        elif status=='Sold':
            core_update('products',{'listing_status':'Sold','updated_at':now()},{'id':pid},"UPDATE products SET listing_status='Sold',updated_at=? WHERE id=?",(now(),pid))
        elif status in ('Seller Declined','Closed'):
            # A deal that fell through used to leave the listing stuck at
            # Pending Pickup/Payment forever, permanently hiding it from
            # buyers even though nothing was ever sold. Return it to Live,
            # but only if no *other* purchase request for the same listing
            # is still actively in progress (handles quantity>1 / multiple
            # concurrent offers correctly).
            prod=hosted_select('products',{'id':pid},limit=1) if hosted_enabled() else df('SELECT listing_status FROM products WHERE id=?',(pid,))
            if not prod.empty and safe(prod.iloc[0].get('listing_status'))=='Pending Pickup/Payment':
                siblings=hosted_select('purchase_requests',{'product_id':pid}) if hosted_enabled() else df('SELECT id,status FROM purchase_requests WHERE product_id=?',(pid,))
                still_active=siblings[siblings['status'].isin(['Pending Pickup/Payment','Seller Accepted','Offer Pending','Seller Countered']) & (siblings['id'].astype(int)!=int(request_id))] if not siblings.empty else siblings
                if still_active.empty:
                    core_update('products',{'listing_status':'Live','updated_at':now()},{'id':pid},"UPDATE products SET listing_status='Live',updated_at=? WHERE id=?",(now(),pid))

def seller_purchase_request_view(sid):
    st.subheader('Purchase requests')
    st.info('Purchase requests are separate from general buyer inquiries. Use these statuses to manage availability before payment/pickup/shipping is finalized.')
    requests=enrich_activity_rows(hosted_select('purchase_requests',{'seller_id':int(sid)},order='created_at.desc')) if hosted_enabled() else df("""SELECT pr.*,p.artist,p.title,p.category,p.listing_status,p.price FROM purchase_requests pr LEFT JOIN products p ON pr.product_id=p.id WHERE pr.seller_id=? ORDER BY pr.created_at DESC""",(sid,))
    if requests.empty:
        st.info('No purchase requests yet.')
        return
    status_filter=st.selectbox('Purchase request status filter',['All']+PURCHASE_REQUEST_STATUSES,key='seller_purchase_status_filter')
    shown=requests if status_filter=='All' else requests[requests['status']==status_filter]
    cols=[c for c in ['id','artist','title','buyer_name','buyer_contact','fulfillment_preference','offer_price','buyer_message','status','listing_status','created_at'] if c in shown.columns]
    st.dataframe(shown[cols],width='stretch')
    if shown.empty:
        st.info('No purchase requests match that status.')
        return
    labels=[f"{int(r.id)} | {safe(r.artist)} - {safe(r.title)} | {safe(r.buyer_name)} | {safe(r.status)}" for _,r in shown.iterrows()]
    pick=st.selectbox('Open purchase request',labels,key='seller_purchase_pick')
    rid=int(pick.split('|')[0].strip())
    row=shown[shown['id']==rid].iloc[0]
    with st.container(border=True):
        st.write(f"**Listing:** {safe(row.get('artist'))} - {safe(row.get('title'))}")
        st.write(f"**Listing status:** {safe(row.get('listing_status'))}")
        st.write(f"**Buyer:** {safe(row.get('buyer_name'))}")
        st.write(f"**Buyer contact:** {safe(row.get('buyer_contact'))}")
        st.write(f"**Preferred contact method:** {safe(row.get('preferred_contact_method'))}")
        st.write(f"**Pickup/shipping:** {safe(row.get('fulfillment_preference'))}")
        st.write(f"**Offer:** {money(row.get('offer_price')) if float(row.get('offer_price') or 0)>0 else 'No offer entered'}")
        st.write(f"**Message:** {safe(row.get('buyer_message'),'No message.')}")
        if float(row.get('counter_price') or 0)>0:
            st.write(f"**Your counter:** {money(row.get('counter_price'))} — {safe(row.get('counter_message'),'No message.')}")
        st.caption(f"Request status: {safe(row.get('status'))} • Received {safe(row.get('created_at'))}")
    c1,c2,c3,c4,c5=st.columns(5)
    if c1.button('Mark Seller Accepted',key=f'seller_purchase_accept_{rid}'):
        update_purchase_request_status(rid,'Seller Accepted',sid); st.success('Purchase request accepted.')
    if c2.button('Mark Seller Declined',key=f'seller_purchase_decline_{rid}'):
        update_purchase_request_status(rid,'Seller Declined',sid); st.warning('Purchase request declined.')
    if c3.button('Mark Pending Pickup/Payment',key=f'seller_purchase_pending_{rid}'):
        update_purchase_request_status(rid,'Pending Pickup/Payment',sid); st.warning('Listing marked Pending.')
    if c4.button('Mark Sold',key=f'seller_purchase_sold_{rid}'):
        update_purchase_request_status(rid,'Sold',sid); st.success('Listing marked Sold.')
    if c5.button('Mark Closed',key=f'seller_purchase_closed_{rid}'):
        update_purchase_request_status(rid,'Closed',sid); st.success('Purchase request closed.')
    if float(row.get('offer_price') or 0)>0 and safe(row.get('status')) in ('Offer Pending','Seller Countered'):
        with st.form(f'seller_counter_form_{rid}'):
            st.caption('Propose a different price back to the buyer.')
            counter_price=st.number_input('Counter price',min_value=0.01,step=1.0,value=float(row.get('offer_price') or 1),key=f'counter_price_{rid}')
            counter_message=st.text_input('Message to buyer - optional',key=f'counter_message_{rid}')
            send_counter=st.form_submit_button('Send Counter Offer')
        if send_counter:
            core_update('purchase_requests',{'status':'Seller Countered','counter_price':float(counter_price),'counter_message':counter_message,'updated_at':now()},{'id':rid,'seller_id':int(sid)},'UPDATE purchase_requests SET status=?,counter_price=?,counter_message=?,updated_at=? WHERE id=? AND seller_id=?',('Seller Countered',float(counter_price),counter_message,now(),rid,sid))
            st.success('Counter offer sent to the buyer.')

def admin_purchase_request_view():
    st.subheader('Purchase Request Review')
    requests=enrich_activity_rows(hosted_select('purchase_requests',order='created_at.desc')) if hosted_enabled() else df("""SELECT pr.*,p.artist,p.title,p.listing_status,s.store_name FROM purchase_requests pr LEFT JOIN products p ON pr.product_id=p.id LEFT JOIN sellers s ON pr.seller_id=s.id ORDER BY pr.created_at DESC""")
    if requests.empty:
        st.info('No purchase requests yet.')
        return
    status_filter=st.selectbox('Purchase request status filter',['All']+PURCHASE_REQUEST_STATUSES,key='admin_purchase_status_filter')
    shown=requests if status_filter=='All' else requests[requests['status']==status_filter]
    cols=[c for c in ['id','store_name','artist','title','buyer_name','buyer_contact','fulfillment_preference','offer_price','status','listing_status','created_at'] if c in shown.columns]
    st.dataframe(shown[cols],width='stretch')
    c1,c2=st.columns(2)
    all_products=table('products')
    c1.metric('Pending listings',0 if all_products.empty else int(all_products['listing_status'].isin(['Pending Pickup/Payment','Pending']).sum()))
    c2.metric('Sold listings',0 if all_products.empty else int((all_products['listing_status']=='Sold').sum()))
    if shown.empty:
        st.info('No purchase requests match that status.')
        return
    labels=[f"{int(r.id)} | {safe(r.store_name)} | {safe(r.artist)} - {safe(r.title)} | {safe(r.status)}" for _,r in shown.iterrows()]
    pick=st.selectbox('Open purchase request',labels,key='admin_purchase_pick')
    rid=int(pick.split('|')[0].strip())
    row=shown[shown['id']==rid].iloc[0]
    with st.container(border=True):
        st.write(f"**Seller:** {safe(row.get('store_name'))}")
        st.write(f"**Listing:** {safe(row.get('artist'))} - {safe(row.get('title'))}")
        st.write(f"**Listing status:** {safe(row.get('listing_status'))}")
        st.write(f"**Buyer:** {safe(row.get('buyer_name'))} • {safe(row.get('buyer_contact'))}")
        st.write(f"**Pickup/shipping:** {safe(row.get('fulfillment_preference'))}")
        st.write(f"**Offer:** {money(row.get('offer_price')) if float(row.get('offer_price') or 0)>0 else 'No offer entered'}")
        st.write(f"**Message:** {safe(row.get('buyer_message'),'No message.')}")
        if float(row.get('counter_price') or 0)>0:
            st.write(f"**Seller counter:** {money(row.get('counter_price'))} — {safe(row.get('counter_message'),'No message.')}")
        st.caption(f"Request status: {safe(row.get('status'))} • Received {safe(row.get('created_at'))}")
    if st.button('Mark Purchase Request Closed',key=f'admin_purchase_closed_{rid}'):
        update_purchase_request_status(rid,'Closed'); st.success('Purchase request closed.')


def seller_inventory_visibility_summary(sid):
    listings=hosted_select('products',{'seller_id':int(sid)},order='created_at.desc',select='*') if hosted_enabled() else df('SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC',(sid,))
    st.subheader('Inventory and store visibility')
    st.info('Add inventory in the Add Inventory / Upload Product tab. Approved sellers can publish listings directly to their store. Draft, Hidden, Under Review, and Removed listings are not public.')
    counts=listings['listing_status'].fillna('Blank').value_counts().to_dict() if not listings.empty else {}
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Total listings',len(listings))
    c2.metric('Live/public',sum(int(counts.get(s,0)) for s in PUBLIC_LISTING_STATUSES))
    c3.metric('Private/moderation',sum(int(counts.get(s,0)) for s in ['Draft','Hidden','Reported','Under Review','Removed by House Of Wax','Submitted for Review','Needs Changes','Rejected']))
    c4.metric('Pending/sold',sum(int(counts.get(s,0)) for s in UNAVAILABLE_LISTING_STATUSES))
    if listings.empty:
        st.warning('No listings are connected to this seller profile yet. Open Add Inventory / Upload Product to create the first listing.')
        return listings
    st.caption('These listings are connected to the currently loaded seller profile by seller ID.')
    visible=listings[listings['listing_status'].isin(public_listing_query_statuses())]
    if visible.empty:
        st.warning('This seller profile exists, but buyers will not clearly see its inventory yet because no listings are Live/Public/Active, Pending, or Sold.')
    else:
        st.success('This seller has listings that can appear publicly. Buyer action buttons only show on Live/Public/Active available listings.')
    preview_cols=[c for c in ['id','artist','title','category','price','quantity','listing_status','reviewer_notes','created_at','updated_at'] if c in listings.columns]
    st.dataframe(listings[preview_cols],width='stretch')
    return listings

def seller_store_profile_editor(sid, s, key_prefix='seller_profile'):
    st.subheader('My Store / Seller Profile')
    st.write('These saved details help buyers understand who they are buying from. Private email and phone are not shown publicly.')
    st.caption('My Store Preview: this profile remains saved even when there are no public listings. Public buyers may only see live/public listings.')
    render_seller_trust_badges(sid,'seller')
    own_listings=hosted_select('products',{'seller_id':int(sid)}) if hosted_enabled() else df('SELECT * FROM products WHERE seller_id=?',(sid,))
    public_count=0 if own_listings.empty else int(own_listings['listing_status'].isin(['Live','Active','Approved','Public']).sum())
    unavailable_count=0 if own_listings.empty else int(own_listings['listing_status'].isin(['Pending Pickup/Payment','Pending','Sold']).sum())
    if public_count:
        st.success(f'Your store is live — {public_count} listing(s) are ready for buyers to find.')
    elif unavailable_count:
        st.warning('Your store profile is saved, but everything in it is pending or sold — nothing available for buyers to act on right now.')
    else:
        st.warning('Your store profile is saved. Add inventory and publish it live before buyers can see anything for sale.')
    with st.form(f'seller_profile_form_{key_prefix}'):
        store=st.text_input('Seller/display name',value=safe(s['store_name']))
        city=st.text_input('City',value=safe(s.get('city')))
        state=st.text_input('State',value=safe(s.get('state')))
        bio=st.text_area('Short bio / about section',value=safe(s['store_bio']))
        story=st.text_area('Longer seller story',value=safe(s['seller_story']))
        spec=st.text_area('Favorite music genres or product categories',value=safe(s['specialties']))
        contact_pref=st.text_input('Contact preference',value=safe(s.get('contact_preference')),placeholder='Example: House Of Wax messages, Instagram DM, local pickup questions')
        logo=st.file_uploader('Logo',type=['png','jpg','jpeg','webp'])
        banner=st.file_uploader('Banner',type=['png','jpg','jpeg','webp'])
        logo_url=st.text_input('Logo URL/path',value=safe(s['logo_url']))
        banner_url=st.text_input('Banner URL/path',value=safe(s['banner_url']))
        sub=st.form_submit_button('Save profile')
    if sub:
        data={'store_name':store,'city':city,'state':state,'store_bio':bio,'seller_story':story,'specialties':spec,'contact_preference':contact_pref,'logo_url':save_file(logo,'seller_logos') or logo_url,'banner_url':save_file(banner,'seller_banners') or banner_url,'seller_level':safe(s.get('seller_level'),'Verified Seller'),'auction_override':'Yes'}
        AUTH_STATUS['last_seller_save_error']=''
        ok=core_update('sellers',data,{'id':sid},"UPDATE sellers SET store_name=?,city=?,state=?,store_bio=?,seller_story=?,specialties=?,contact_preference=?,logo_url=?,banner_url=?,seller_level=?,auction_override='Yes' WHERE id=?",(store,city,state,bio,story,spec,contact_pref,data['logo_url'],data['banner_url'],data['seller_level'],sid))
        reloaded=get_seller(sid)
        if ok and reloaded is not None:
            st.success('Seller profile saved and reloaded.')
            st.write(f"Saved store: {safe(reloaded.get('store_name'))} | {safe(reloaded.get('email'))}")
        else:
            AUTH_STATUS['last_seller_save_error']=safe(SUPABASE_STATUS.get('last_error'),'Seller profile save failed.')
            st.error('Seller profile did not save. Supabase error: '+AUTH_STATUS['last_seller_save_error'])

def seller_listings_manager(sid, key_prefix='seller_listings'):
    st.subheader('My Inventory')
    st.caption('Everything you add for sale will appear here.')
    seller=get_seller(int(sid))
    is_approved=seller_can_publish(seller)
    rules_ok=seller_rules_accepted(seller)
    can_publish=seller_can_publish_live(seller)
    seller_status_notice(seller)
    if is_approved and not rules_ok:
        st.warning('Accept seller rules before publishing inventory live. Drafts can still be saved and managed.')
    listing_status_help()
    prods=hosted_select('products',{'seller_id':int(sid)},order='created_at.desc',select='*') if hosted_enabled() else df('SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC',(sid,))
    if prods.empty:
        st.warning('No inventory yet. Add your first item.')
        if st.button('Add Inventory',key=f'{key_prefix}_empty_add_inventory'):
            st.session_state['pending_seller_tools_primary_section']='Add Inventory'
            st.rerun()
        return
    cols=[c for c in ['id','title','artist','price','quantity','listing_status','created_at','reviewer_notes'] if c in prods.columns]
    st.dataframe(prods[cols],width='stretch')
    pid=st.selectbox('Listing ID',prods['id'].tolist(),key=f'{key_prefix}_listing_id')
    row=prods[prods['id']==pid].iloc[0]
    st.write(f"**Selected item:** {safe(row.get('title'),'Untitled')} • {safe(row.get('artist'),'No artist/brand')} • {money(row.get('price'))}")
    current_status=safe(row.get('listing_status'))
    st.write(f"**Current status:** {current_status}")
    listing_status_badge(current_status)
    if safe(row.get('reviewer_notes')):
        st.warning('House Of Wax notes: '+safe(row.get('reviewer_notes')))
    actions=['Draft','Live','Hidden','Sold']
    if current_status in ['Reported','Under Review','Removed by House Of Wax']:
        st.info('This listing has a House Of Wax moderation status. Some seller actions may be limited.')
        actions=['Draft','Hidden','Sold']
    status=st.selectbox('Seller action',actions,key=f'{key_prefix}_seller_action',help='Draft stays private. Live publishes to your store. Hidden removes it from public view. Sold marks it no longer available.')
    if st.button('Update listing status',key=f'{key_prefix}_update_{int(pid)}'):
        if status=='Live' and not is_approved:
            st.error('Your seller account must be approved before you can publish listings.')
            return
        if status=='Live' and not rules_ok:
            st.error('Accept seller rules before publishing.')
            return
        core_update('products',{'listing_status':status,'updated_at':now()},{'id':int(pid),'seller_id':int(sid)},'UPDATE products SET listing_status=?,updated_at=? WHERE id=? AND seller_id=?',(status,now(),int(pid),sid))
        st.success('Listing status updated.')


def seller_dashboard():
    header(); marketplace_context('House Of Wax Marketplace → Seller Dashboard'); st.header('Seller Dashboard')
    prototype_role_notice()
    pending_section=st.session_state.pop('pending_seller_tools_primary_section',None)
    if pending_section:
        st.session_state['seller_tools_primary_section']=pending_section
    if is_admin_unlocked():
        st.caption(f'Active storage mode: {active_storage_label()}')
    if not is_admin_unlocked():
        if not is_authenticated():
            st.warning('Sign in as a Seller to use Seller Dashboard.')
            account_page()
            return
        if not has_seller_capability():
            st.error('This account has not applied to become a seller yet. Open My Account and use Apply to Become a Seller.')
            return
        sid=ensure_linked_seller_profile()
        if not sid:
            st.error('No seller store is linked to this account. Use Account to claim or create a seller store.')
            claim_existing_profile_section()
            return
        st.session_state['seller_tool_seller_id']=sid
        s=get_seller(sid)
        if s is None:
            st.error('Linked seller store was not found.')
            return
        with st.container(border=True):
            st.subheader(safe(s['store_name'],'Seller Store'))
            st.write(f"**Store email:** {safe(s['email'])}")
            seller_status_notice(s)
            st.caption('Seller account status controls whether this store can publish live inventory.')
            st.success('You are managing your signed-in seller store.')
        seller_onboarding_checklist(sid,s)
        if not hosted_enabled():
            st.warning('For real tester data persistence, connect Supabase before collecting tester data. Local SQLite is for development and can reset on Streamlit Cloud.')
        st.info('Use My Inventory to find everything you added. Use Add Inventory to create one new item.')
        primary_section=st.radio('Seller Tools section',['My Inventory','Add Inventory','My Store Profile','Buyer Requests','Seller Messages/Inquiries','All Seller Tools'],horizontal=True,key='seller_tools_primary_section_auth')
        if primary_section=='My Inventory':
            seller_listings_manager(sid,'primary_my_inventory')
            return
        if primary_section=='Add Inventory':
            st.subheader('Add Inventory')
            st.info('Create one item at a time. Approved sellers can publish directly after accepting seller rules. Pending sellers can save drafts.')
            render_barcode_lookup_widget('primary_add_inventory')
            upload_product(sid,'primary_add_inventory')
            return
        if primary_section=='My Store Profile':
            seller_store_profile_editor(sid,s,'primary_my_store')
            return
        if primary_section=='Buyer Requests':
            seller_purchase_request_view(sid)
            return
        if primary_section=='Seller Messages/Inquiries':
            seller_inquiry_view(sid)
            return
        seller_inventory_visibility_summary(sid)
        return
    st.caption('Admin/testing seller store inspection is enabled.')
    sellers=table('sellers')
    if sellers.empty:
        st.warning('No seller store/profile found yet. Create one from Sell on House Of Wax, then return here.')
    else:
        latest=sellers.sort_values('id',ascending=False).head(8)
        st.success('Saved seller stores found.')
        st.dataframe(latest[[c for c in ['id','store_name','email','status','rules_accepted','rules_accepted_at','created_at'] if c in latest.columns]],width='stretch')
        active_id=st.session_state.get('seller_tool_seller_id')
        if active_id:
            active=get_seller(int(active_id))
            if active is not None:
                st.info(f"Currently active seller store: {safe(active.get('store_name'))} | {safe(active.get('email'))}")
    preferred_seller=st.session_state.get('seller_tool_seller_id')
    sid=seller_pick('sellerdb',preferred_id=preferred_seller)
    st.session_state['seller_tool_seller_id']=sid
    if not sid:
        st.info('Choose an existing seller above, or create a seller store first.')
        return
    s=get_seller(sid)
    if s is None:
        st.warning('The selected seller profile was not found in the database. Choose an existing seller or create a seller store first.')
        st.session_state.pop('seller_tool_seller_id',None)
        return
    with st.container(border=True):
        st.subheader(safe(s['store_name'],'Seller Store'))
        st.write(f"**Store email:** {safe(s['email'])}")
        status=seller_status_notice(s)
        st.caption('Seller account status controls whether this store can publish live inventory.')
        st.success('You are managing this store.')
        st.caption('Start here if you are selling records, merch, or collectibles.')
    seller_onboarding_checklist(sid,s)
    if not hosted_enabled():
        st.warning('For real tester data persistence, connect Supabase before collecting tester data. Local SQLite is for development and can reset on Streamlit Cloud.')
    st.info('Use My Inventory to find everything you added. Use Add Inventory to create one new item.')
    primary_section=st.radio('Seller Tools section',['My Inventory','Add Inventory','My Store Profile','Buyer Requests','Seller Messages/Inquiries','All Seller Tools'],horizontal=True,key='seller_tools_primary_section')
    if primary_section=='My Inventory':
        seller_listings_manager(sid,'primary_my_inventory')
        return
    if primary_section=='Add Inventory':
        st.subheader('Add Inventory')
        st.info('Create one item at a time. Approved sellers can publish directly after accepting seller rules. Pending sellers can save drafts.')
        render_barcode_lookup_widget('primary_add_inventory')
        upload_product(sid,'primary_add_inventory')
        return
    if primary_section=='My Store Profile':
        seller_store_profile_editor(sid,s,'primary_my_store')
        return
    if primary_section=='Buyer Requests':
        seller_purchase_request_view(sid)
        return
    if primary_section=='Seller Messages/Inquiries':
        seller_inquiry_view(sid)
        return
    seller_inventory_visibility_summary(sid)
    st.caption('My Store Profile, Add Inventory, My Inventory, and Seller Messages/Inquiries and Buyer Requests are in the radio above. The tabs below cover everything else.')
    tabs=st.tabs(['Policies','Barcode scanner','Bulk import','Gallery','Messages','Announcements','Events/drops','Badges'])
    with tabs[0]:
        p=hosted_select('seller_policies',{'seller_id':sid},limit=1) if hosted_enabled() else df('SELECT * FROM seller_policies WHERE seller_id=?',(sid,)); pol=p.iloc[0] if not p.empty else {}
        with st.form('policy'):
            shipping=st.text_area('Shipping policy',value=safe(pol.get('shipping_policy') if len(pol) else 'Ships within 3 business days.')); returns=st.text_area('Return policy',value=safe(pol.get('return_policy') if len(pol) else 'No buyer remorse returns unless seller approves.')); grading=st.text_area('Grading policy',value=safe(pol.get('grading_policy') if len(pol) else 'Collector grading standards.')); pickup=st.text_area('Pickup / meetup / local policy notes',value=safe(pol.get('local_pickup_policy') if len(pol) else '')); sub=st.form_submit_button('Save policies')
        if sub:
            ok=True
            if hosted_enabled():
                data={'seller_id':sid,'shipping_policy':shipping,'return_policy':returns,'grading_policy':grading,'local_pickup_policy':pickup}
                if not p.empty:
                    ok=hosted_update('seller_policies',data,{'seller_id':sid})
                else:
                    # seller_policies has no id column, so hosted_insert's
                    # id-based success signal is always 0 here even when the
                    # insert worked -- check the request outcome directly.
                    _,insert_detail=hosted_request('post','seller_policies',data=data)
                    show_hosted_error('insert','seller_policies',insert_detail)
                    ok=bool(insert_detail.get('ok'))
            else:
                run('INSERT OR REPLACE INTO seller_policies(seller_id,shipping_policy,return_policy,grading_policy,local_pickup_policy) VALUES(?,?,?,?,?)',(sid,shipping,returns,grading,pickup))
            if ok:
                st.success('Policies saved.')
            else:
                st.error('Policies could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[1]:
        st.subheader('Barcode scanner / inventory quick add')
        st.info('Click into the barcode field and scan with a USB/Bluetooth scanner, phone keyboard scanner, or type/paste the barcode.')
        render_barcode_lookup_widget('barcode_quick_add')
        upload_product(sid,'barcode_quick_add')
    with tabs[2]:
        csv=st.file_uploader('Upload CSV',type=['csv']); st.caption('Supports barcode,catalog_number,matrix_runout,artist,title,format,label,release_year,genre,price,quantity,image_url')
        if csv is not None:
            data=pd.read_csv(csv); st.dataframe(data,width='stretch')
            if st.button('Import CSV products'):
                n=0
                failed=0
                corrected=0
                imported_seller=get_seller(int(sid))
                imported_status='Live' if seller_can_publish_live(imported_seller) else 'Draft'
                for _,r in data.iterrows():
                    price,price_err=parse_money_input(r.get('price',0),'Price')
                    shipping_price,shipping_err=parse_money_input(r.get('shipping_price',0),'Shipping price')
                    quantity,qty_err=parse_quantity_input(r.get('quantity',1))
                    if price_err or shipping_err or qty_err: corrected+=1
                    row_data={'seller_id':sid,'sku':safe(r.get('sku')),'barcode':safe(r.get('barcode')),'catalog_number':safe(r.get('catalog_number')),'matrix_runout':safe(r.get('matrix_runout')),'category':safe(r.get('category'),'Vinyl Records'),'artist':safe(r.get('artist')),'title':safe(r.get('title')),'format':safe(r.get('format'),'Vinyl'),'label':safe(r.get('label')),'release_year':safe(r.get('release_year')),'genre':safe(r.get('genre')),'media_grade':safe(r.get('media_grade')),'sleeve_grade':safe(r.get('sleeve_grade')),'condition_notes':safe(r.get('condition_notes')),'description':safe(r.get('description')),'price':price,'quantity':quantity,'shipping_price':shipping_price,'image_url':safe(r.get('image_url')),'video_url':safe(r.get('video_url')),'audio_url':safe(r.get('audio_url')),'external_release_url':safe(r.get('external_release_url')),'listing_status':imported_status,'listing_type':'Fixed Price','created_at':now(),'updated_at':now()}
                    row_cols=['seller_id','sku','barcode','catalog_number','matrix_runout','category','artist','title','format','label','release_year','genre','media_grade','sleeve_grade','condition_notes','description','price','quantity','shipping_price','image_url','video_url','audio_url','external_release_url','listing_status','listing_type','created_at','updated_at']
                    row_id=core_insert('products',row_data,f"INSERT INTO products({','.join(row_cols)}) VALUES({','.join(['?']*len(row_cols))})",tuple(row_data[k] for k in row_cols))
                    if row_id or not hosted_enabled(): n+=1
                    else: failed+=1
                corrected_note=f' {corrected} row(s) had an invalid price/quantity and were imported with a corrected value (0 or 1) -- review before publishing.' if corrected else ''
                failed_note=f' {failed} row(s) failed to save and were skipped -- Supabase error: {safe(SUPABASE_STATUS.get("last_error"),"Unknown error")}' if failed else ''
                if failed and not n:
                    st.error('No rows could be imported.'+failed_note)
                elif imported_status=='Live':
                    st.success(f'Imported {n}. Published imported items as Live.'+corrected_note+failed_note)
                elif seller_can_publish(imported_seller) and not seller_rules_accepted(imported_seller):
                    st.warning(f'Imported {n} as Draft. Accept seller rules before publishing imported listings live.'+corrected_note+failed_note)
                else:
                    st.warning(f'Imported {n} as Draft. Seller approval is required before publishing live.'+corrected_note+failed_note)
    with tabs[3]:
        prods=hosted_select('products',{'seller_id':int(sid)}) if hosted_enabled() else df('SELECT * FROM products WHERE seller_id=?',(sid,)); st.dataframe(prods,width='stretch')
        if not prods.empty:
            pid=st.selectbox('Product for gallery',prods['id'].tolist()); img=st.file_uploader('Gallery image',type=['png','jpg','jpeg','webp']); url=st.text_input('Or image URL'); cap=st.text_input('Caption')
            if st.button('Add gallery image'):
                image=save_file(img,'product_gallery') or url
                if image:
                    data={'product_id':int(pid),'image_url':image,'caption':cap,'created_at':now()}
                    new_id=core_insert('product_gallery',data,'INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)',(int(pid),image,cap,now()))
                    if new_id or not hosted_enabled():
                        st.success('Gallery image added.')
                    else:
                        st.error('Gallery image could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[4]: st.dataframe(df('SELECT * FROM messages WHERE seller_id=? ORDER BY created_at DESC',(sid,)),width='stretch')
    with tabs[5]:
        with st.form('ann'): title=st.text_input('Announcement title'); body=st.text_area('Announcement body'); sub=st.form_submit_button('Post announcement')
        if sub:
            data={'seller_id':sid,'title':title,'body':body,'status':'Active','created_at':now()}
            new_id=core_insert('store_announcements',data,"INSERT INTO store_announcements(seller_id,title,body,status,created_at) VALUES(?,?,?,'Active',?)",(sid,title,body,now()))
            if new_id or not hosted_enabled():
                st.success('Posted.')
            else:
                st.error('Announcement could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
        st.dataframe(hosted_select('store_announcements',{'seller_id':sid}) if hosted_enabled() else df('SELECT * FROM store_announcements WHERE seller_id=?',(sid,)),width='stretch')
    with tabs[6]:
        with st.form('ev'): title=st.text_input('Drop/event title'); typ=st.selectbox('Type',['Record Drop','Auction Drop','Sale','Live Event','Other']); date=st.text_input('Date/time'); desc=st.text_area('Description'); sub=st.form_submit_button('Save event')
        if sub:
            data={'seller_id':sid,'event_title':title,'event_type':typ,'event_date':date,'description':desc,'status':'Active','created_at':now()}
            new_id=core_insert('seller_events',data,"INSERT INTO seller_events(seller_id,event_title,event_type,event_date,description,status,created_at) VALUES(?,?,?,?,?,'Active',?)",(sid,title,typ,date,desc,now()))
            if new_id or not hosted_enabled():
                st.success('Saved.')
            else:
                st.error('Event could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
    with tabs[7]: st.write(badges(sid) or 'No badges yet.'); st.dataframe(hosted_select('seller_badges',{'seller_id':sid}) if hosted_enabled() else df('SELECT * FROM seller_badges WHERE seller_id=?',(sid,)),width='stretch')
def auctions():
    header(); st.header('Auctions'); sid=seller_pick('auction_seller'); prods=df("SELECT * FROM products WHERE seller_id=? AND listing_status IN ('Active','Approved','Public')",(sid,))
    if not prods.empty:
        with st.form('auction'): pid=st.selectbox('Product',prods['id'].tolist()); title=st.text_input('Auction title'); start=st.number_input('Starting bid',min_value=0.0,step=1.0); end=st.text_input('End time'); sub=st.form_submit_button('Create live auction')
        if sub: run("INSERT INTO auctions(product_id,seller_id,auction_title,starting_bid,reserve_price,buy_now_price,bid_increment,start_time,end_time,status,notes,created_at) VALUES(?,?,?,?,?,?,1,?,?,'Live','',?)",(int(pid),sid,title,float(start),0,0,now(),end,now())); st.success('Auction created.')
    st.dataframe(table('auctions'),width='stretch')
def culture():
    header(); st.header('Knowledge Hub'); posts=df("SELECT * FROM culture_posts WHERE status='Published' ORDER BY created_at DESC")
    if posts.empty: st.info('No culture posts yet.')
    for _,p in posts.iterrows():
        with st.container(border=True):
            if safe(p['image_url']): safe_image(safe(p['image_url']),width='stretch',fallback_text='Image unavailable.')
            st.subheader(safe(p['title'])); st.caption(f"{safe(p['category'])} • {safe(p['author'])}"); st.write(safe(p['body']))
def listing_review_queue():
    admin_context('House Of Wax Admin → Moderation Center')
    st.subheader('Moderation Center')
    st.info('House Of Wax approves sellers, not every normal listing. Use this center to review reports, moderate listings, and manage seller approval.')
    admin_seller_applications()
    st.divider()
    st.markdown('#### Reports / Complaints')
    reports=table('listing_reports')
    if reports.empty:
        st.info('No listing or seller reports yet.')
        return
    enriched=reports.copy()
    for idx,row in enriched.iterrows():
        listing_id=int(row.get('listing_id') or 0)
        seller_id=int(row.get('seller_id') or 0)
        listing=hosted_select('products',{'id':listing_id},limit=1) if hosted_enabled() and listing_id else (df('SELECT * FROM products WHERE id=?',(listing_id,)) if listing_id else pd.DataFrame())
        seller=get_seller(seller_id) if seller_id else None
        if not listing.empty:
            enriched.at[idx,'listing_title']=' - '.join([safe(listing.iloc[0].get('artist')),safe(listing.iloc[0].get('title'))]).strip(' - ')
            enriched.at[idx,'listing_status']=safe(listing.iloc[0].get('listing_status'))
        if seller is not None:
            enriched.at[idx,'store_name']=safe(seller.get('store_name'))
            enriched.at[idx,'seller_status']=normalize_seller_status(seller.get('status'))
    cols=[c for c in ['id','listing_id','listing_title','seller_id','store_name','reason','details','status','listing_status','seller_status','created_at','updated_at'] if c in enriched.columns]
    st.dataframe(enriched[cols],width='stretch')
    labels=[f"{int(r.get('id'))} | Listing {int(r.get('listing_id') or 0)} | Seller {int(r.get('seller_id') or 0)} | {safe(r.get('reason'))} | {safe(r.get('status'))}" for _,r in reports.iterrows()]
    pick=st.selectbox('Open report',labels,key='moderation_report_pick')
    rid=int(pick.split('|')[0].strip())
    report=reports[reports['id']==rid].iloc[0]
    listing_id=int(report.get('listing_id') or 0)
    seller_id=int(report.get('seller_id') or 0)
    listing=hosted_select('products',{'id':listing_id},limit=1) if hosted_enabled() and listing_id else (df('SELECT * FROM products WHERE id=?',(listing_id,)) if listing_id else pd.DataFrame())
    seller=get_seller(seller_id) if seller_id else None
    with st.container(border=True):
        st.write(f"**Reason:** {safe(report.get('reason'))}")
        st.write(f"**Details:** {safe(report.get('details'))}")
        st.caption(f"Reporter: {safe(report.get('reporter_name'),'Anonymous')} • {safe(report.get('reporter_contact'),'No contact provided')}")
        st.caption(f"Report status: {safe(report.get('status'))}")
    if not listing.empty:
        row=listing.iloc[0]
        st.write('**Listing operational status:**')
        listing_status_badge(safe(row.get('listing_status')))
        primary_image=listing_primary_image(row)
        listing_preview_card(row.get('category'),row.get('artist'),row.get('title'),row.get('format'),row.get('label'),row.get('release_year'),row.get('genre'),row.get('media_grade'),row.get('sleeve_grade'),float(row.get('price') or 0),int(row.get('quantity') or 1),float(row.get('shipping_price') or 0),primary_image,row.get('description'),has_listing_photos(listing_id),'','admin')
    notes=st.text_area('Moderation notes',value=safe(report.get('details')),key='moderation_notes')
    c1,c2,c3,c4=st.columns(4)
    if c1.button('Mark Report Reviewed',key=f'report_reviewed_{rid}'):
        core_update('listing_reports',{'status':'Reviewed','updated_at':now()},{'id':rid},"UPDATE listing_reports SET status='Reviewed',updated_at=? WHERE id=?",(now(),rid))
        st.success('Report marked reviewed.')
        st.rerun()
    if listing_id and c2.button('Put Listing Under Review',key=f'listing_under_review_{rid}'):
        core_update('products',{'listing_status':'Under Review','reviewer_notes':notes,'updated_at':now()},{'id':listing_id},"UPDATE products SET listing_status='Under Review',reviewer_notes=?,updated_at=? WHERE id=?",(notes,now(),listing_id))
        core_update('listing_reports',{'status':'Under Review','updated_at':now()},{'id':rid},"UPDATE listing_reports SET status='Under Review',updated_at=? WHERE id=?",(now(),rid))
        st.warning('Listing placed under review.')
        st.rerun()
    if listing_id and c3.button('Hide Listing',key=f'hide_listing_{rid}'):
        core_update('products',{'listing_status':'Hidden','reviewer_notes':notes,'updated_at':now()},{'id':listing_id},"UPDATE products SET listing_status='Hidden',reviewer_notes=?,updated_at=? WHERE id=?",(notes,now(),listing_id))
        st.warning('Listing hidden from Marketplace.')
        st.rerun()
    if listing_id and c4.button('Remove Listing',key=f'remove_listing_{rid}'):
        core_update('products',{'listing_status':'Removed by House Of Wax','reviewer_notes':notes,'updated_at':now()},{'id':listing_id},"UPDATE products SET listing_status='Removed by House Of Wax',reviewer_notes=?,updated_at=? WHERE id=?",(notes,now(),listing_id))
        core_update('listing_reports',{'status':'Resolved','updated_at':now()},{'id':rid},"UPDATE listing_reports SET status='Resolved',updated_at=? WHERE id=?",(now(),rid))
        st.error('Listing removed by House Of Wax.')
        st.rerun()
    if seller is not None:
        c5,c6=st.columns(2)
        if c5.button('Suspend Seller',key=f'moderation_suspend_seller_{rid}_{seller_id}'):
            core_update('sellers',{'status':'Suspended Seller'},{'id':seller_id},"UPDATE sellers SET status='Suspended Seller' WHERE id=?",(seller_id,))
            st.warning('Seller suspended.')
            st.rerun()
        if c6.button('Reinstate Seller',key=f'moderation_reinstate_seller_{rid}_{seller_id}'):
            core_update('sellers',{'status':'Approved Seller'},{'id':seller_id},"UPDATE sellers SET status='Approved Seller' WHERE id=?",(seller_id,))
            st.success('Seller reinstated as approved.')
            st.rerun()

def redact_export_table(table_name):
    data=table(table_name)
    if data.empty:
        return data
    private_cols=[c for c in data.columns if any(token in c.lower() for token in ['email','phone','contact','access_code'])]
    return data.drop(columns=private_cols,errors='ignore')

def hosted_database_prep_section():
    st.markdown('### Hosted Database / Supabase Prep')
    mode=database_mode()
    config=mode['hosted_config']
    if config['hosted_config_detected']:
        st.success('Hosted database settings detected.')
        st.caption('Do not attempt risky migration unless the app has safe migration code and backups are ready. SQLite remains the active fallback in this prototype.')
    else:
        st.info('Hosted database not connected yet. Local prototype database is being used.')
    st.caption('Configuration checked: SUPABASE_URL, SUPABASE_ANON_KEY, DATABASE_URL.')
    st.dataframe(pd.DataFrame(config['rows']),width='stretch')
    st.caption('Secret values are masked. This app checks for configuration safely and does not require hosted database credentials to run.')

    st.markdown('### Current data model summary')
    data_groups=[
        ('Listings','products','Move to hosted database before launch. Protect status, price, quantity, review notes, and seller ownership.'),
        ('Seller profiles','sellers','Move to hosted database. Protect seller email, phone, access code, and private profile controls.'),
        ('Inquiries','listing_inquiries','Move to hosted database. Protect buyer contact info and message history.'),
        ('Purchase requests','purchase_requests','Move to hosted database. Protect buyer contact info, offer details, fulfillment preference, and status.'),
        ('Photos/photo references','product_gallery plus product image fields','Move references to hosted database and files to cloud storage.'),
        ('Review notes/statuses','products reviewer_notes and listing_status','Move to hosted database. Protect admin notes and moderation history.'),
        ('Roles/prototype user state','Streamlit session role selector','Replace with real auth roles and permission checks before public launch.')
    ]
    st.dataframe(pd.DataFrame(data_groups,columns=['Data group','Current area','Hosted database note']),width='stretch')
    st.warning('Privacy protection needed: buyer contact info, seller contact info, purchase requests, and admin notes should never be exposed publicly.')

    st.markdown('### Supabase migration checklist')
    checklist=[
        'Create Supabase project',
        'Create tables',
        'Add environment variables to Streamlit secrets',
        'Test read/write',
        'Migrate sample listings',
        'Test buyer inquiry',
        'Test purchase request',
        'Test seller/admin access',
        'Back up local data before migration'
    ]
    for item in checklist:
        st.write(f'- {item}')
    st.caption('This is a prep/checklist step, not a full migration. No Supabase package, Postgres driver, secret, or new dependency is required for V25.28.')

def supabase_diag_payload(table_name, marker):
    base_time=now()
    payloads={
        'buyers':({'name':marker,'email':f'{marker.lower()}@example.com','bio':marker,'status':'Diagnostic','created_at':base_time,'updated_at':base_time},'email',f'{marker.lower()}@example.com',{'bio':marker+' updated'},'bio'),
        'sellers':({'store_name':marker,'owner_name':'Diagnostic','email':f'{marker.lower()}@example.com','store_bio':marker,'status':'Approved','seller_level':'Diagnostic','access_code':marker,'created_at':base_time,'updated_at':base_time},'email',f'{marker.lower()}@example.com',{'store_bio':marker+' updated'},'store_bio'),
        'products':({'artist':'Diagnostic','title':marker,'category':'Vinyl Records','price':1,'condition_notes':marker,'description':marker,'listing_status':'Draft','created_at':base_time,'updated_at':base_time},'title',marker,{'listing_status':'Live','description':marker+' updated','updated_at':now()},'description'),
        'listing_inquiries':({'buyer_name':marker,'buyer_contact':f'{marker.lower()}@example.com','preferred_contact_method':'Email','message':marker,'status':'New','created_at':base_time,'updated_at':base_time},'buyer_name',marker,{'status':'Closed','updated_at':now()},'status'),
        'purchase_requests':({'buyer_name':marker,'buyer_contact':f'{marker.lower()}@example.com','preferred_contact_method':'Email','fulfillment_preference':'Shipping','offer_price':1,'buyer_message':marker,'status':'New','created_at':base_time,'updated_at':base_time},'buyer_name',marker,{'status':'Closed','updated_at':now()},'status'),
        'tester_feedback':({'tester_name':marker,'tester_type':'Other','page_flow':marker,'worked_well':marker,'confusing':'','felt_broken':'','missing':'','ease_rating':5,'would_use_again':'Maybe','open_notes':marker,'status':'New','created_at':base_time},'page_flow',marker,{'status':'Closed'},'status'),
        'listing_reports':({'listing_id':0,'seller_id':0,'reporter_name':marker,'reporter_contact':f'{marker.lower()}@example.com','reason':'Other','details':marker,'status':'Open','created_at':base_time,'updated_at':base_time},'reporter_name',marker,{'status':'Reviewed','updated_at':now()},'status')
    }
    return payloads[table_name]

def supabase_roundtrip_one(table_name, marker):
    if not hosted_enabled():
        return {'table':table_name,'passed':False,'stage':'config','status_code':0,'message':'Supabase settings are missing.'}
    data,marker_col,marker_value,update_data,update_col=supabase_diag_payload(table_name,marker)
    inserted,detail=hosted_request('post',table_name,data=data)
    if not detail.get('ok') or not inserted:
        return {'table':table_name,'passed':False,'stage':'insert','status_code':detail.get('status_code'),'message':detail.get('message')}
    inserted_id=inserted[0].get('id')
    read,detail=hosted_request('get',table_name,params={'select':'*',marker_col:f'eq.{marker_value}'},prefer='')
    if not detail.get('ok') or not read or safe(read[0].get(marker_col))!=safe(marker_value):
        return {'table':table_name,'passed':False,'stage':'read_after_insert','status_code':detail.get('status_code'),'message':detail.get('message') or 'Inserted row was not read back by marker.'}
    updated,detail=hosted_request('patch',table_name,params={'id':f'eq.{inserted_id}'},data=update_data)
    if not detail.get('ok'):
        return {'table':table_name,'passed':False,'stage':'update','status_code':detail.get('status_code'),'message':detail.get('message')}
    read2,detail=hosted_request('get',table_name,params={'select':'*','id':f'eq.{inserted_id}'},prefer='')
    expected=safe(update_data.get(update_col))
    actual=safe(read2[0].get(update_col)) if read2 else ''
    if not detail.get('ok') or not read2 or actual!=expected:
        return {'table':table_name,'passed':False,'stage':'read_after_update','status_code':detail.get('status_code'),'message':detail.get('message') or f'Update not verified. Expected {expected}, got {actual}.'}
    deleted,detail=hosted_request('delete',table_name,params={'id':f'eq.{inserted_id}'},prefer='')
    if not detail.get('ok'):
        return {'table':table_name,'passed':False,'stage':'delete','status_code':detail.get('status_code'),'message':detail.get('message')}
    read3,detail=hosted_request('get',table_name,params={'select':'id','id':f'eq.{inserted_id}'},prefer='')
    if not detail.get('ok'):
        return {'table':table_name,'passed':False,'stage':'confirm_delete','status_code':detail.get('status_code'),'message':detail.get('message')}
    if read3:
        return {'table':table_name,'passed':False,'stage':'confirm_delete','status_code':detail.get('status_code'),'message':'Deleted diagnostic row was still readable.'}
    return {'table':table_name,'passed':True,'stage':'complete','status_code':detail.get('status_code'),'message':'Insert/read/update/delete round trip passed.'}

def run_supabase_roundtrip_diagnostics():
    marker='DIAG-'+uuid4().hex[:10]+'-'+datetime.now().strftime('%Y%m%d%H%M%S')
    results=[]
    for table_name in ['buyers','sellers','products','listing_inquiries','purchase_requests','tester_feedback','listing_reports']:
        results.append(supabase_roundtrip_one(table_name,marker))
    return pd.DataFrame(results)

def admin_system_diagnostics():
    st.subheader('System Diagnostics')
    url,key=supabase_config()
    mode=database_mode()
    st.write('Backend mode currently active: **'+safe(mode.get('storage_mode'))+'**')
    c1,c2,c3=st.columns(3)
    c1.metric('SUPABASE_URL detected','Yes' if bool(url) else 'No')
    c2.metric('SUPABASE_ANON_KEY detected','Yes' if bool(key) else 'No')
    c3.metric('Key type',supabase_key_type())
    st.caption('Normalized Supabase base URL: '+safe(url,'Not configured'))
    st.caption('Last Supabase read result: '+safe(SUPABASE_STATUS.get('last_read')))
    st.caption('Last Supabase write result: '+safe(SUPABASE_STATUS.get('last_write')))
    if safe(SUPABASE_STATUS.get('last_error')):
        st.error('Last Supabase error: '+safe(SUPABASE_STATUS.get('last_error')))
    if not hosted_enabled():
        st.error('Running on local SQLite fallback. Data may not persist between Streamlit restarts/redeploys.')
    st.warning('No error thrown is not evidence of persistence. Use the round-trip test below and confirm every core table passes.')
    if st.button('Run Supabase round-trip test',key='run_supabase_roundtrip_test'):
        st.session_state['supabase_roundtrip_results']=run_supabase_roundtrip_diagnostics()
    results=st.session_state.get('supabase_roundtrip_results')
    if results is not None:
        st.dataframe(results,width='stretch')
        if not results.empty and bool(results['passed'].all()):
            st.success('Supabase round-trip persistence passed for every tested core table.')
        else:
            st.error('Supabase is configured but read/write failed, or Supabase is missing. Tester data may not persist.')
    auth_diagnostics_section()
    real_profile_flow_check()

def real_profile_flow_check():
    st.markdown('### Real Profile Flow Check')
    st.caption('This checks the real app profile/listing data, not synthetic DIAG rows.')
    buyers=table('buyers')
    sellers=table('sellers')
    products=table('products')
    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric('Active storage',active_storage_label())
    c2.metric('Active buyer id',safe(st.session_state.get('buyer_id'),'None'))
    c3.metric('Active seller id',safe(st.session_state.get('seller_tool_seller_id'),'None'))
    c4.metric('Buyer profiles',len(buyers))
    c5.metric('Seller stores',len(sellers))
    if buyers.empty:
        st.warning('No buyer profiles found in the active storage mode.')
    else:
        st.success('Buyer profiles are visible in the active storage mode.')
        latest_buyers=buyers.sort_values('id',ascending=False).head(5)
        st.dataframe(latest_buyers[[c for c in ['id','name','email','status','created_at'] if c in latest_buyers.columns]],width='stretch')
    if sellers.empty:
        st.warning('No seller stores found in the active storage mode.')
    else:
        st.success('Seller stores are visible in the active storage mode.')
        latest_sellers=sellers.sort_values('id',ascending=False).head(5)
        st.dataframe(latest_sellers[[c for c in ['id','store_name','email','status','created_at'] if c in latest_sellers.columns]],width='stretch')
    if products.empty:
        st.warning('No listings found in the active storage mode.')
    else:
        st.success('Listings are visible in the active storage mode.')
        latest_products=products.sort_values('id',ascending=False).head(5)
        st.dataframe(latest_products[[c for c in ['id','seller_id','artist','title','listing_status','created_at'] if c in latest_products.columns]],width='stretch')

def admin_database_status():
    admin_context('House Of Wax Admin → Database Status')
    st.subheader('Database Status / Data Health')
    admin_system_diagnostics()
    st.divider()
    if hosted_enabled():
        st.info('Supabase settings are detected. Run the System Diagnostics round-trip test above to prove hosted persistence is working.')
    else:
        st.warning('Hosted persistence is not connected. Local prototype database is being used.')
    st.info('Local SQLite is for development only and may not persist on Streamlit Cloud after redeploy, reboot, sleep, or container replacement. For real tester data persistence, connect Supabase before collecting tester data.')
    st.caption('Use this admin-only area to confirm storage health, table counts, photo records, and safe exports before deployment.')
    mode=database_mode()
    c1,c2,c3=st.columns(3)
    c1.metric('Storage mode',mode['storage_mode'])
    c2.metric('Supabase settings detected','Yes' if hosted_enabled() else 'No')
    c3.metric('Local database file','Found' if DB.exists() else 'Will be created')
    st.caption('Active database engine: '+safe(mode.get('engine')))
    st.caption('Local SQLite path: '+safe(mode.get('path')))
    if hosted_enabled():
        st.caption('Hosted database settings are active, but persistence is only proven after the round-trip diagnostics pass.')
    else:
        st.caption('Hosted database is not active yet. This keeps Streamlit deployment working without new secrets.')
    tables=df("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    st.write(f"**Tables detected:** {len(tables)}")
    if not tables.empty:
        st.dataframe(tables,width='stretch')
    counts=[]
    labels={'products':'Listings','sellers':'Seller profiles','buyers':'Buyer profiles','listing_inquiries':'Buyer inquiries','purchase_requests':'Purchase requests','product_gallery':'Photo records','tester_feedback':'Tester feedback','listing_reports':'Listing/seller reports'}
    for t,label in labels.items():
        try:
            counts.append({'Area':label,'Table':t,'Records':len(table(t))})
        except Exception:
            counts.append({'Area':label,'Table':t,'Records':'Unavailable'})
    metric_cols=st.columns(len(counts))
    for i,item in enumerate(counts):
        metric_cols[i].metric(item['Area'],item['Records'])
    st.dataframe(pd.DataFrame(counts),width='stretch')
    st.markdown('### Core hosted tables expected')
    st.write(', '.join(CORE_HOSTED_TABLES))
    if hosted_enabled():
        missing=[]
        for t in CORE_HOSTED_TABLES:
            payload,detail=hosted_request('get',t,params={'select':'id','limit':'1'},prefer='')
            if not detail.get('ok'):
                missing.append(f"{t}: HTTP {detail.get('status_code')} {safe(detail.get('message'))[:160]}")
        if missing:
            st.error('Supabase settings were detected, but these core tables may be missing or blocked by permissions: '+', '.join(missing))
        else:
            st.success('Core table read checks completed. Run the round-trip diagnostics above to prove writes and deletes.')
    st.warning('Admin-only export area. Buyer/seller contact data can be sensitive. The quick exports below remove obvious email, phone, contact, and access-code columns.')
    export_choice=st.selectbox('Export safe data table',KEY_DATA_TABLES,format_func=lambda x: labels.get(x,x),key='database_status_export_table')
    export_data=redact_export_table(export_choice)
    st.dataframe(export_data,width='stretch')
    csv_data=export_data.to_csv(index=False)
    json_data=export_data.to_json(orient='records',indent=2)
    c4,c5=st.columns(2)
    c4.download_button('Download safe CSV export',csv_data,file_name=f'house_of_wax_{export_choice}_safe_export.csv',mime='text/csv',key=f'database_status_csv_{export_choice}')
    c5.download_button('Download safe JSON export',json_data,file_name=f'house_of_wax_{export_choice}_safe_export.json',mime='application/json',key=f'database_status_json_{export_choice}')
    st.warning('Backup reminder: export important local data before any future migration. Production launch should use hosted database storage, real auth, cloud image storage, and tested permissions.')
    hosted_database_prep_section()

def update_app_user_seller_status_for_seller(sid, status):
    seller=get_seller(int(sid))
    if seller is None:
        return False
    email=safe(seller.get('email')).strip().lower()
    data={'seller_id':int(sid),'seller_application_status':normalize_seller_status(status),'account_type':'Buyer/Seller','updated_at':now()}
    if hosted_enabled():
        target=hosted_select('app_users',{'seller_id':int(sid)},limit=1)
        if target.empty and email:
            target=hosted_select('app_users',{'email':email},limit=1)
        if target.empty:
            return False
        return core_update('app_users',data,{'id':int(target.iloc[0]['id'])})
    target=df('SELECT * FROM app_users WHERE seller_id=? LIMIT 1',(int(sid),))
    if target.empty and email:
        target=df('SELECT * FROM app_users WHERE lower(email)=lower(?) LIMIT 1',(email,))
    if target.empty:
        return False
    run('UPDATE app_users SET seller_id=?,seller_application_status=?,account_type=?,updated_at=? WHERE id=?',(int(sid),normalize_seller_status(status),'Buyer/Seller',now(),int(target.iloc[0]['id'])))
    return True

def user_directory_dataframe():
    users=table('app_users')
    buyers=table('buyers')
    sellers=table('sellers')
    rows=[]
    if not users.empty:
        for _,u in users.iterrows():
            bid=int(u.get('buyer_id') or 0)
            sid=int(u.get('seller_id') or 0)
            buyer=buyers[buyers['id']==bid].iloc[0].to_dict() if bid and not buyers.empty and 'id' in buyers.columns and not buyers[buyers['id']==bid].empty else {}
            seller=sellers[sellers['id']==sid].iloc[0].to_dict() if sid and not sellers.empty and 'id' in sellers.columns and not sellers[sellers['id']==sid].empty else {}
            seller_status=safe(u.get('seller_application_status')) or (normalize_seller_status(seller.get('status')) if seller else 'Not Applied')
            warning=[] 
            if not safe(u.get('auth_user_id')): warning.append('missing auth_user_id')
            if not bid: warning.append('missing buyer link')
            if bid and not buyer: warning.append('buyer row missing')
            if sid and not seller: warning.append('seller row missing')
            rows.append({
                'display_name':safe(u.get('display_name')) or safe(buyer.get('name')) or safe(seller.get('owner_name')),
                'email':safe(u.get('email')) or safe(buyer.get('email')) or safe(seller.get('email')),
                'auth_user_id_masked':mask_identifier(u.get('auth_user_id')),
                'auth_account_found':'Unknown without secure Auth Admin API' if hosted_enabled() else 'Local fallback',
                'app_users_row_found':'Yes',
                'buyer_profile_linked':'Yes' if bid and buyer else 'No',
                'seller_profile_linked':'Yes' if sid and seller else 'No',
                'seller_application_status':seller_status,
                'account_status':account_status(u),
                'created_at':safe(u.get('created_at')),
                'updated_at':safe(u.get('updated_at')),
                'store_name':safe(seller.get('store_name')),
                'warning':', '.join(warning) if warning else ''
            })
    known_emails={safe(r.get('email')).lower() for r in rows}
    for _,b in buyers.iterrows() if not buyers.empty else []:
        email=safe(b.get('email')).lower()
        if email and email not in known_emails:
            rows.append({'display_name':safe(b.get('name')),'email':email,'auth_user_id_masked':'None','auth_account_found':'Unknown without secure Auth Admin API','app_users_row_found':'No','buyer_profile_linked':'Yes','seller_profile_linked':'No','seller_application_status':'Not Applied','account_status':safe(b.get('status'),'Active'),'created_at':safe(b.get('created_at')),'updated_at':'','store_name':'','warning':'buyer profile exists without app_users mapping'})
    known_emails={safe(r.get('email')).lower() for r in rows}
    for _,s in sellers.iterrows() if not sellers.empty else []:
        email=safe(s.get('email')).lower()
        if email and email not in known_emails:
            rows.append({'display_name':safe(s.get('owner_name')) or safe(s.get('store_name')),'email':email,'auth_user_id_masked':'None','auth_account_found':'Unknown without secure Auth Admin API','app_users_row_found':'No','buyer_profile_linked':'No','seller_profile_linked':'Yes','seller_application_status':normalize_seller_status(s.get('status')),'account_status':normalize_seller_status(s.get('status')),'created_at':safe(s.get('created_at')),'updated_at':'','store_name':safe(s.get('store_name')),'warning':'seller profile exists without app_users mapping'})
    return pd.DataFrame(rows)

def admin_user_directory():
    st.subheader('User Directory')
    st.info('Every app_users row, linked buyer profile, and linked seller profile found by the app is shown here. Search by display name, email, or store name.')
    q=st.text_input('Search users',placeholder='Try LDizzle, pattihanson29715@gmail.com, or a store name',key='user_directory_search')
    data=user_directory_dataframe()
    if data.empty:
        st.warning('No mapped users, buyers, or sellers were found in the active storage mode.')
    else:
        view=data.copy()
        if safe(q):
            needle=safe(q).lower()
            mask=view.apply(lambda row: needle in ' '.join(safe(v).lower() for v in row.values),axis=1)
            view=view[mask]
        st.dataframe(view,width='stretch')
        st.download_button('Download User Directory CSV',view.to_csv(index=False),file_name='house_of_wax_user_directory.csv',mime='text/csv',key='download_user_directory_csv')
    st.markdown('#### Reconcile Auth Users')
    if hosted_enabled():
        st.warning('This Streamlit app uses the Supabase anon/authenticated client. It cannot securely list all Supabase Auth users without a protected server-side service role. Do not expose service_role in Streamlit public code.')
        st.caption('If LDizzle or pattihanson29715@gmail.com exist only in Supabase Auth, they will not appear here until a secure admin reconciliation process creates/links their app_users row.')
    else:
        st.info('Local fallback mode can only reconcile local app_users/buyers/sellers rows.')
    with st.form('manual_user_reconcile_form'):
        email=st.text_input('Repair by exact email',key='manual_reconcile_email')
        display=st.text_input('Display name if app_users row is missing',key='manual_reconcile_display')
        auth_uid=st.text_input('Auth user ID if known optional',key='manual_reconcile_auth_uid')
        sub=st.form_submit_button('Create/link app_users + buyer profile')
    if sub:
        clean=safe(email).strip().lower()
        if not clean:
            st.error('Enter an exact email.')
        else:
            name=safe(display) or clean.split('@')[0]
            bid=create_or_get_buyer_for_auth(clean,name)
            uid=safe(auth_uid) or 'manual-'+hashlib.sha256(clean.encode('utf-8')).hexdigest()[:24]
            app_id=upsert_app_user(uid,clean,name,'Buyer',bid,0,'','No','Not Applied','Active')
            if app_id and bid:
                st.success('Mapping repaired/created. The user is now visible in User Directory.')
                st.rerun()
            else:
                st.error('Mapping repair failed. Check Supabase errors and exact email.')

def admin_seller_applications():
    st.subheader('Seller Applications')
    st.info('Use this page to approve seller privileges for people who already have one House Of Wax account.')
    sellers=table('sellers')
    if sellers.empty:
        st.warning('No seller applications or seller profiles found.')
        return
    users=table('app_users')
    rows=[]
    for _,s in sellers.iterrows():
        sid=int(s.get('id') or 0)
        email=safe(s.get('email')).lower()
        user_match=users[(users['seller_id']==sid)] if not users.empty and 'seller_id' in users.columns else pd.DataFrame()
        if user_match.empty and email and not users.empty and 'email' in users.columns:
            user_match=users[users['email'].fillna('').str.lower()==email]
        app_user=user_match.iloc[0].to_dict() if not user_match.empty else {}
        rows.append({
            'seller_id':sid,
            'app_user_email':safe(app_user.get('email')) or email,
            'app_user_found':'Yes' if app_user else 'No',
            'app_user_display_name':safe(app_user.get('display_name')),
            'store_name':safe(s.get('store_name')),
            'seller_status':normalize_seller_status(s.get('status')),
            'rules_accepted':'Yes' if seller_rules_accepted(s) else 'No',
            'created_at':safe(s.get('created_at')),
            'profile_warning':'' if app_user else 'seller profile is not linked to app_users'
        })
    data=pd.DataFrame(rows)
    pending=data[data['seller_status']=='Pending Seller Approval']
    other=data[data['seller_status']!='Pending Seller Approval']
    st.dataframe(pd.concat([pending,other],ignore_index=True),width='stretch')
    labels=[f"{int(r['seller_id'])} | {safe(r['store_name'])} | {safe(r['app_user_email'])} | {safe(r['seller_status'])}" for _,r in data.iterrows()]
    pick=st.selectbox('Select seller application',labels,key='seller_applications_pick')
    sid=int(pick.split('|')[0].strip())
    seller=get_seller(sid)
    status=normalize_seller_status(seller.get('status') if seller is not None else '')
    st.write('**Current seller status:** '+status)
    st.write('**Rules accepted:** '+('Yes' if seller_rules_accepted(seller) else 'No'))
    c1,c2,c3=st.columns(3)
    if c1.button('Approve Seller',key=f'seller_app_approve_{sid}'):
        core_update('sellers',{'status':'Approved Seller'},{'id':sid},"UPDATE sellers SET status='Approved Seller' WHERE id=?",(sid,))
        update_app_user_seller_status_for_seller(sid,'Approved Seller')
        if seller is not None:
            send_seller_approved_email(safe(seller.get('email')),safe(seller.get('store_name')))
        st.success('Seller approved. Buyer capability is preserved on the same account.')
        st.rerun()
    if c2.button('Needs Information / Pending',key=f'seller_app_pending_{sid}'):
        core_update('sellers',{'status':'Pending Seller Approval'},{'id':sid},"UPDATE sellers SET status='Pending Seller Approval' WHERE id=?",(sid,))
        update_app_user_seller_status_for_seller(sid,'Pending Seller Approval')
        st.warning('Seller application set to pending / needs information.')
        st.rerun()
    if c3.button('Suspend Seller',key=f'seller_app_suspend_{sid}'):
        core_update('sellers',{'status':'Suspended Seller'},{'id':sid},"UPDATE sellers SET status='Suspended Seller' WHERE id=?",(sid,))
        update_app_user_seller_status_for_seller(sid,'Suspended Seller')
        st.error('Seller suspended. Buyer capability remains on the account.')
        st.rerun()

def admin():
    header(); admin_context('House Of Wax Admin'); st.header('House Of Wax Admin')
    if not is_admin_unlocked():
        st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode to open prototype admin tools.')
        return
    admin_access_warning()
    prototype_role_notice()
    if ADMIN_PASSWORD:
        pwd=st.text_input('Admin password',type='password')
        if not st.button('Enter admin'): return
        if pwd!=ADMIN_PASSWORD: st.error('Wrong password.'); return
    else: st.info('No admin password set. Testing build allows admin access.')
    pending_seller_apps=pending_seller_application_count()
    if pending_seller_apps:
        st.error(f"{pending_seller_apps} seller application{'s' if pending_seller_apps!=1 else ''} waiting for review.")
        if st.button('Review seller applications',key='admin_dashboard_jump_to_seller_apps'):
            st.session_state['pending_admin_navigation']='Seller Applications'
            st.rerun()
    tabs=st.tabs(['Overview','Inquiries','Purchase Requests','Sellers','Buyers','Community tools','Reports','Cleanup'])
    with tabs[0]:
        if st.button('Create/repair House Of Wax Official seller'):
            sid=ensure_house_of_wax_official(); st.success(f'House Of Wax Official seller ready. Seller ID {sid}')
        c1,c2,c3,c4=st.columns(4); c1.metric('Buyers',len(table('buyers'))); c2.metric('Sellers',len(table('sellers'))); c3.metric('Products',len(table('products'))); c4.metric('Seller reviews',len(table('seller_reviews')))
        st.info('User Directory, Seller Applications, Moderation Center, Tester Feedback, and Database Status now live only in the sidebar Admin navigation (left side) — they were duplicated here and in the sidebar before, so this tab set was trimmed to remove the second copy.')
        with st.expander('AI Avatar Assistant (Home page)',expanded=False):
            if liveavatar_configured():
                st.success('Backend and avatar are configured in Secrets.')
                live=setting('liveavatar_enabled','false')=='true'
                new_live=st.toggle('Show the avatar assistant on the Home page',value=live,key='liveavatar_admin_toggle')
                if new_live!=live:
                    set_setting('liveavatar_enabled','true' if new_live else 'false'); st.rerun()
            else:
                st.warning('Not configured yet. Add LIVEAVATAR_BACKEND_URL and LIVEAVATAR_AVATAR_ID in Secrets once the backend service and HeyGen avatar are ready — the widget stays hidden until both are set.')
        with st.expander('Music Data Sources Roadmap',expanded=False):
            st.write('Future source/partner work should support both new and old music without making House Of Wax dependent on one outside source.')
            for item in [
                'MusicBrainz + Cover Art Archive for open music metadata and cover art.',
                'Discogs for collector/release marketplace reference where allowed by API terms.',
                'Last.fm or similar sources for popularity, tag, and discovery context where allowed.',
                'Future partnerships with local record stores, collectors, DJs, labels, and distributors.',
                'Cache metadata responsibly where allowed.',
                'Respect each API’s terms, rate limits, and attribution requirements.'
            ]:
                st.write(f'- {item}')
    with tabs[1]: admin_inquiry_view()
    with tabs[2]: admin_purchase_request_view()
    with tabs[3]: st.dataframe(table('sellers'),width='stretch')
    with tabs[4]: st.dataframe(table('buyers'),width='stretch')
    with tabs[5]:
        sid=seller_pick('adminseller'); badge=st.text_input('Badge',placeholder='Soul Specialist, Jazz Dealer, Verified Seller'); typ=st.selectbox('Badge type',['Community','Specialty','Performance','Verified'])
        if st.button('Add badge'):
            data={'seller_id':sid,'badge_name':badge,'badge_type':typ,'active':'Yes','created_at':now()}
            new_id=core_insert('seller_badges',data,"INSERT INTO seller_badges(seller_id,badge_name,badge_type,active,created_at) VALUES(?,?,?,'Yes',?)",(sid,badge,typ,now()))
            if new_id or not hosted_enabled():
                st.success('Badge added.')
            else:
                st.error('Badge could not be saved. Supabase error: '+safe(SUPABASE_STATUS.get('last_error'),'Unknown error'))
        if st.button('Create seller spotlight culture post'):
            s=get_seller(sid); run("INSERT INTO culture_posts(title,category,author,body,image_url,status,created_at) VALUES(?,'Seller Spotlight','House Of Wax',?,?,'Published',?)",(f"Seller Spotlight: {safe(s['store_name'])}",safe(s['seller_story'],safe(s['store_bio'])),safe(s['banner_url']) or safe(s['logo_url']),now())); st.success('Spotlight created.')
        st.subheader('Messages'); st.dataframe(table('messages'),width='stretch')
    with tabs[6]:
        rep=st.selectbox('Report',['buyers','sellers','products','product_gallery','listing_reports','messages','listing_inquiries','purchase_requests','seller_followers','seller_badges','store_announcements','seller_events','auctions','bids','listing_flags','culture_posts','knowledge_posts','glossary_terms','content_drafts','content_calendar','want_list','seller_reviews']); data=table(rep); st.dataframe(data,width='stretch'); st.download_button('Download CSV',data.to_csv(index=False),file_name=f'{rep}.csv')
    with tabs[7]:
        t=st.selectbox('Table',['buyers','sellers','products','product_gallery','listing_reports','messages','listing_inquiries','purchase_requests','seller_followers','seller_badges','store_announcements','seller_events','auctions','bids','listing_flags','culture_posts','knowledge_posts','glossary_terms','content_drafts','content_calendar','want_list','seller_reviews']); data=table(t); st.dataframe(data,width='stretch')
        if not data.empty:
            rid=st.selectbox('Row ID',data['id'].tolist()); confirm=st.checkbox('Confirm delete')
            if st.button('Delete row') and confirm: run(f'DELETE FROM {t} WHERE id=?',(int(rid),)); st.success('Deleted.')



# ---------- V23 Launch Prep + Public Pages ----------

def seller_standards():
    header()
    st.header('Seller Standards')
    st.write('Sellers on House Of Wax should help build a trusted marketplace and music culture community.')
    st.markdown('### Sellers are expected to')
    st.info('Approved sellers can manage and publish listings in their own stores. Sellers are responsible for the accuracy, legality, condition, pricing, images, and descriptions of the items they post.')
    st.write('- Describe items honestly.')
    st.write('- Use clear condition notes.')
    st.write('- Add barcode, catalog, matrix/runout, label, format, and release details when available.')
    st.write('- Upload strong photos.')
    st.write('- Price clearly.')
    st.write('- Respond to buyers professionally.')
    st.write('- Ship items safely and on time.')
    st.write('- Respect House Of Wax trust standards.')
    st.write('- Do not knowingly post counterfeit, stolen, misleading, illegal, hateful, violent, or prohibited items.')
    st.markdown('### House Of Wax Official')
    st.write('House Of Wax can also sell branded merchandise, official drops, curated goods, and platform items through the House Of Wax Official seller account.')

def buyer_expectations():
    header()
    st.header('Buyer Expectations')
    st.write('House Of Wax buyers should understand what they are buying and use the Knowledge Hub to collect smarter.')
    st.markdown('### Buyers are expected to')
    st.write('- Read item details before requesting to buy.')
    st.write('- Review photos, condition notes, and seller information.')
    st.write('- Ask questions before committing.')
    st.write('- Pay promptly when payment is due.')
    st.write('- Avoid buyer remorse disputes when an item was accurately described.')
    st.write('- Leave fair feedback after the transaction.')
    st.markdown('### Buying smarter')
    st.write('Use the Knowledge Hub to learn grading, formats, barcodes, matrix/runouts, bootlegs, reissues, and marketplace trust before buying.')

def policy_draft_notice():
    st.warning('Draft placeholder for prototype planning. Must be reviewed by a qualified attorney before public launch.')

def legal_policies():
    header()
    marketplace_context('House Of Wax Marketplace → Rules & Policies')
    st.header('Legal / Policies')
    st.info('These draft sections help organize House Of Wax marketplace rules, privacy expectations, seller expectations, and buyer expectations before launch.')
    st.warning('These are not final attorney-approved legal documents and should not be treated as production terms.')

    st.markdown('### House Of Wax Marketplace Publishing Policy')
    st.info('House Of Wax allows approved sellers to manage and publish listings in their own stores. Sellers are responsible for the accuracy, legality, condition, pricing, images, and descriptions of the items they post. House Of Wax does not pre-approve every listing. Listings and sellers may be reported by buyers, sellers, rights owners, or community members. House Of Wax may investigate reports and may hide, remove, or restrict listings or sellers that violate platform rules.')
    st.write('Sellers agree not to knowingly post counterfeit, stolen, misleading, illegal, hateful, violent, or prohibited items. Sellers must describe items honestly and respond to buyer questions in good faith.')
    st.write('Buyers should review the listing details, condition notes, seller information, and photos or cover art before requesting to buy. Buyers can report listings or sellers that appear misleading or against platform rules.')

    st.info('The real Privacy Policy and Terms of Service are live at ?legal=privacy and ?legal=terms -- edit those pages directly rather than this draft section.')

    st.markdown('### Seller Agreement Draft')
    policy_draft_notice()
    for item in ['Provide accurate item details.','Use real item photos when required or preferred.','Describe condition honestly, including damage or missing parts.','Respond to buyer inquiries professionally.','Do not list prohibited, counterfeit, stolen, unsafe, or misleading items.','Understand approved sellers can publish directly, but reported listings may be moderated by House Of Wax.','Understand fees, commissions, payment rules, and seller payouts are not finalized unless separately agreed.']:
        st.write(f'- {item}')

    st.markdown('### Buyer Guidelines Draft')
    policy_draft_notice()
    for item in ['Ask clear questions before requesting to buy.','Use Request to Buy only when seriously interested.','Communicate respectfully with sellers and House Of Wax.','Inspect item details, photos, condition notes, seller information, and status labels.','Understand payment, shipping, pickup, returns, and dispute rules are not finalized yet.']:
        st.write(f'- {item}')

    st.markdown('### Marketplace Rules Draft')
    policy_draft_notice()
    for item in ['Live listings from approved sellers can appear in Marketplace.','Draft, Hidden, Under Review, Removed by House Of Wax, inactive, or non-public listings should not be treated as public listings.','Pending and sold status should be clear to buyers.','House Of Wax may use trust indicators, seller profile context, reports, and moderation tools.','Seller trust indicators are platform signals, not outside verification.','House Of Wax may remove or hide listings that are unsafe, misleading, inappropriate, prohibited, or incomplete.']:
        st.write(f'- {item}')

    st.markdown('### Prohibited Items / Unsafe Listings Draft')
    policy_draft_notice()
    st.write('This list is general and non-exhaustive.')
    for item in ['Counterfeit goods','Stolen goods','Illegal items','Unsafe or hazardous items','Misleading listings','Inappropriate content','Listings that hide important condition, authenticity, ownership, or safety information']:
        st.write(f'- {item}')

    st.markdown('### Returns, Pickup, Shipping, and Disputes Draft')
    policy_draft_notice()
    for item in ['Return rules must be finalized before launch.','Pickup rules must clearly explain buyer/seller responsibilities and safe handoff expectations.','Shipping rules must cover cost, timing, packaging, tracking, damaged items, and lost packages.','Dispute rules must explain how buyers, sellers, and House Of Wax communicate when an item is not as described.','Payment and refund rules are not finalized in this prototype.']:
        st.write(f'- {item}')

    st.markdown('### Production Legal Checklist')
    policy_draft_notice()
    checklist=[
        'Attorney-reviewed Privacy Policy',
        'Attorney-reviewed Terms of Use',
        'Seller agreement',
        'Buyer dispute policy',
        'Payment/refund rules',
        'Shipping/pickup rules',
        'Data retention policy',
        'Moderation/removal policy'
    ]
    for item in checklist:
        st.write(f'- {item}')


def seller_onboarding():
    header()
    marketplace_context('House Of Wax Marketplace → Seller Onboarding')
    st.header('Seller Onboarding')
    st.info('Use this guide to onboard early House Of Wax sellers, partners, and testers without adding risky production features.')

    st.markdown('### Who House Of Wax is for')
    for item in ['Record sellers','Collectors','Music merch sellers','Memorabilia sellers','Culture goods sellers']:
        st.write(f'- {item}')

    st.markdown('### Seller onboarding walkthrough')
    steps=[
        'Create seller profile',
        'Add store/policy notes',
        'Search or enter item',
        'Confirm match',
        'Add condition and seller details',
        'Add real item photos',
        'Preview listing',
        'Review listing readiness',
        'Save as Draft or Publish to My Store',
        'Confirm seller account is approved',
        'Respond to inquiries',
        'Manage purchase requests',
        'Mark Pending or Sold'
    ]
    for i,item in enumerate(steps,1):
        st.write(f'{i}. {item}')

    st.markdown('### Seller listing quality tips')
    for item in ['Clear title','Accurate price','Honest condition','Real photos','Media/sleeve condition for music','Clear pickup/shipping notes','No counterfeit or unsafe items']:
        st.write(f'- {item}')

    st.markdown('### Seller trust tips')
    for item in ['Complete profile','Respond professionally','Use exact item photos','Keep listings accurate','Update sold/pending status quickly']:
        st.write(f'- {item}')

    st.warning('Early seller onboarding is still prototype guidance. Public launch still needs real authentication, hosted data, final legal terms, seller agreements, and payment/checkout decisions.')

def demo_guide():
    header()
    st.header('Demo Guide')
    st.info('House Of Wax is a working Streamlit prototype for demo and founder review. It is not a production marketplace yet.')
    st.write('Use this guide to walk through the core experience without needing to explain the whole app first.')
    st.caption('New here? The full testing checklist (Buyer/Seller/Admin paths) lives on the Home page under Tester Start Here.')
    c1,c2,c3=st.columns(3)
    with c1:
        st.subheader('Buyer flow')
        st.write('1. Open Marketplace.')
        st.write('2. Open a Live listing.')
        st.write('3. Use Contact Seller / Ask About This Item for questions.')
        st.write('4. Use Request to Buy (at the listed price) or Make an Offer (to propose a different price) when the buyer is ready. Checkout is not live yet; this sends a purchase request.')
        st.caption('Pending and Sold listings can appear as unavailable, but buyer action buttons stay hidden.')
    with c2:
        st.subheader('Seller flow')
        st.write('1. Open My House of Wax as Seller.')
        st.write('2. Open Seller Tools, then My Store / Seller Profile.')
        st.write('3. Click Add Inventory / Upload Product.')
        st.write('4. Search or enter item details.')
        st.write('5. Add seller details, photos, and condition notes.')
        st.write('6. Review the listing preview and readiness checklist.')
        st.write('7. Save as Draft or Publish to My Store.')
        st.write('8. Check My Listings / Inventory.')
    with c3:
        st.subheader('Admin flow')
        st.write('1. Switch to Admin role or enable Testing mode.')
        st.write('2. Open My House of Wax, then Admin.')
        st.write('3. Review seller approval and listing/seller reports.')
        st.write('4. Hide/remove listings or suspend/reinstate sellers when platform rules require it.')
        st.write('5. Review inquiries, purchase requests, and Database Status.')
    st.markdown('### Where to go')
    st.write('- Marketplace: public buyer browsing and listing details.')
    st.write('- My House of Wax: buyer, seller, admin, and demo workspaces.')
    st.write('- Tester Feedback: quick feedback form for buyers, sellers, reviewers, advisors, and early testers.')
    st.write('- Seller Tools: upload products, manage listings, profile, inquiries, and purchase requests.')
    st.write('- Knowledge Center / Education Hub: buyer education, seller listing guidance, condition, photos, trust standards, FAQs, and marketplace rules.')
    st.write('- Admin Tools: moderation center, seller approval, reports, inquiries, purchase requests, and database health.')
    st.write('- Seller Onboarding: early seller walkthrough, listing quality tips, and trust tips.')
    st.write('- Marketplace Launch Checklist: prototype readiness, public-launch needs, and early seller/buyer test plans.')
    st.write('- Business Plan / Funding Roadmap: final demo test plan, business foundation, funding stages, and use-of-funds priorities.')
    st.markdown('### Demo data')
    st.write('Use Test Setup inside My House of Wax only while Testing/Admin mode is enabled. Demo records are labeled for testing and should be replaced or removed before a real launch.')
    with st.expander('Submit tester feedback after a demo',expanded=False):
        tester_feedback_form('demo_guide')
    st.markdown('### Production needs before launch')
    for item in ['Real login/authentication and permission checks','Hosted database storage such as Supabase/Postgres','Permanent hosted image storage','Payments, checkout, refunds, and order operations','Legal/privacy policy, seller terms, buyer terms, and marketplace rules']:
        st.write(f'- {item}')
    st.warning('Prototype storage is local. Uploaded photos and the SQLite database are not production hosting. The repo .gitignore protects local database and upload folders.')
    st.caption('For partner, lender, grant, or investor conversations, open Pitch / Demo Package and Business Plan / Funding Roadmap from this same My House of Wax workspace. For the next build phase, open Seller Onboarding, Marketplace Launch Checklist, Production Readiness / Launch Roadmap, Auth + Roles Plan, Legal / Policies, Payment / Checkout Prep, and Admin Database Status.')


def pitch_demo_package():
    header()
    st.header('Pitch / Demo Package')
    st.info('House Of Wax is a marketplace and culture platform for records, music collectibles, merch, memorabilia, and culture goods.')
    st.write('The prototype shows how House Of Wax can help people discover items, help approved sellers publish directly, and help the platform protect trust through reports and moderation.')

    c1,c2=st.columns(2)
    with c1:
        st.subheader('What it is')
        st.write('House Of Wax combines a buyer marketplace, seller storefront tools, music culture education, and a House Of Wax review layer.')
        st.write('It is built for collectors, music fans, independent sellers, culture brands, local record sellers, merch sellers, and people who want clearer buying decisions.')
    with c2:
        st.subheader('Problem it solves')
        st.write('Music and culture marketplaces can be hard to trust. Listings may be incomplete, photos may be weak, condition details may be unclear, and buyers often need to contact sellers before committing.')
        st.write('House Of Wax makes the listing process more guided and gives the platform tools to approve sellers, receive reports, and moderate problem listings after publishing.')

    st.markdown('### Marketplace concept')
    st.write('Buyers browse live listings, view item details, ask sellers questions, and request to buy. Approved sellers build richer listings with search data, photos, condition notes, listing readiness, profile context, and trust badges. Admin/moderation tools help House Of Wax approve sellers, review reports, track inquiries, track purchase requests, and watch database health.')
    st.caption('Checkout is not live yet. Request to Buy and Make an Offer are the current purchase-intent workflows while payment decisions are prepared.')
    st.caption('The Knowledge Center / Education Hub supports the pitch by showing how House Of Wax teaches buyers, sellers, and early testers before the marketplace scales.')

    c3,c4,c5=st.columns(3)
    with c3:
        st.subheader('Buyer flow')
        st.write('- Browse Marketplace.')
        st.write('- View a live listing.')
        st.write('- Contact Seller / Ask About This Item.')
        st.write('- Request to Buy or Make an Offer.')
        st.write('- Follow inquiry and purchase request history.')
    with c4:
        st.subheader('Seller flow')
        st.write('- Open Seller Tools.')
        st.write('- Search item data or enter it manually.')
        st.write('- Add seller details, photos, price, and condition.')
        st.write('- Review the listing preview and readiness checklist.')
        st.write('- Save as Draft or Publish to My Store.')
    with c5:
        st.subheader('Admin flow')
        st.write('- Review seller approval and reports.')
        st.write('- Add moderation notes.')
        st.write('- Hide/remove listings or suspend/reinstate sellers.')
        st.write('- Review inquiries and purchase requests.')
        st.write('- Check database status and safe exports.')

    st.markdown('### Why trust tools matter')
    st.write('Trust badges, listing readiness, seller approval, and moderation reports help make the marketplace feel intentional instead of random. They also give House Of Wax a practical way to coach sellers, improve listing quality, and protect buyers before scaling.')
    st.caption('For early seller walkthroughs, open Seller Onboarding. For demo readiness, funding conversations, and beta testing, open Business Plan / Funding Roadmap and Marketplace Launch Checklist.')

    st.markdown('### Demo walkthrough')
    walkthrough=[
        'Step 1: Open Marketplace',
        'Step 2: View a live listing',
        'Step 3: Contact seller',
        'Step 4: Request to buy',
        'Step 5: Switch to Seller role',
        'Step 6: Upload a listing',
        'Step 7: Publish to My Store',
        'Step 8: Switch to Admin role',
        'Step 9: Review reports or seller approval',
        'Step 10: Check Database Status/export'
    ]
    for step in walkthrough:
        st.write(f'- {step}')
    st.caption('What to show someone: start with the Marketplace, then show the guided seller upload, then show the Admin Moderation Center. That tells the whole story quickly.')

    st.markdown('### What Works Now')
    for item in ['Marketplace','Seller upload flow','Smart search','Drafts and direct publishing','Listing readiness','Seller profiles','Trust badges','Buyer inquiries','Request to buy','Pending/Sold inventory status','Role separation prototype','Photo upload prototype','Database status/export','Moderation Center']:
        st.write(f'- {item}')

    st.markdown('### What Comes Next for Production')
    for item in ['Real authentication/login','Hosted database','Permanent cloud image storage','Payments or checkout','Shipping/pickup rules','Legal pages','Seller agreement','Privacy policy','Better admin security','More real-user testing']:
        st.write(f'- {item}')
    st.caption('For the build sequence behind these items, open Production Readiness / Launch Roadmap. For seller readiness, open Seller Onboarding and Marketplace Launch Checklist. For business/funding readiness, open Business Plan / Funding Roadmap. For login, policies, and payment direction, open Auth + Roles Plan, Legal / Policies, and Payment / Checkout Prep.')

    st.markdown('### Prototype completion estimate')
    st.success('Strong demo prototype: nearly complete for guided walkthroughs, founder review, partner conversations, and early feedback.')
    st.warning('Public production marketplace: still requires infrastructure, legal, payment, storage, authentication, security, and real-user testing before launch.')


def production_readiness_roadmap():
    header()
    st.header('Production Readiness / Launch Roadmap')
    st.info('Use this roadmap to organize the next development phase before House Of Wax becomes a public marketplace.')
    st.write('This section does not add production authentication or new infrastructure. It explains what is ready for demos, what is prototype-only, and what should be upgraded before public launch.')

    st.markdown('### What is working now')
    working_now=[
        ('Marketplace browsing','Live/public listings can appear with images, status, seller information, inquiry, and request-to-buy actions.','Medium'),
        ('Seller upload flow','Approved sellers can create guided listings with search data, details, photos, preview, readiness, draft, and direct publishing.','Medium'),
        ('Moderation Center','Admin can approve sellers, review reports, add notes, hide/remove listings, and suspend/reinstate sellers.','Medium'),
        ('Buyer inquiries and purchase requests','Buyers can ask about items and request to buy through controlled House Of Wax forms.','Medium'),
        ('Seller profiles and trust badges','Seller profile details, platform indicators, and listing quality signals are visible.','Low'),
        ('Database health/export','Admin can view local database status and safe export options for key tables.','Low')
    ]
    for name,desc,risk in working_now:
        st.write(f'- **{name}** — {desc} Risk level: {risk}.')

    st.markdown('### What is prototype-only')
    prototype_only=[
        ('Role selector','Current Buyer/Seller/Admin switching is prototype control only, not secure authentication.','High'),
        ('Local SQLite storage','Data is stored in a local app database unless hosted storage is added later.','High'),
        ('Local photo storage','Uploaded files use prototype storage and need cloud storage before launch.','High'),
        ('Testing/Admin mode','Admin tools are intentionally visible for demo/testing and must be locked behind real permissions.','High'),
        ('Manual review operations','Review and status tools work, but need stronger audit trails and permissions before scale.','Medium'),
        ('No real checkout','Request to Buy is an intent workflow, not a payment/order fulfillment system.','Medium')
    ]
    for name,desc,risk in prototype_only:
        st.write(f'- **{name}** — {desc} Risk level: {risk}.')

    st.markdown('### What must be upgraded before public launch')
    launch_upgrades=[
        ('Real authentication/login','Replace prototype role selection with real user accounts and session checks.','High'),
        ('Hosted database','Move from local SQLite to hosted storage such as Supabase/Postgres. Start with the Hosted Database / Supabase Prep checklist in Admin Database Status.','High'),
        ('Cloud image storage','Store listing photos in permanent hosted storage with safe access rules.','High'),
        ('Admin security hardening','Protect admin tools with real admin login, role checks, and private data controls.','High'),
        ('Payment or checkout decision','Decide whether House Of Wax handles payments directly or routes seller-managed transactions.','Medium'),
        ('Shipping/pickup rules','Define shipping, pickup, local handoff, cancellation, and inventory status rules.','Medium'),
        ('Legal pages and seller agreement','Add privacy policy, buyer terms, seller terms, marketplace rules, and content policies.','High'),
        ('Beta testing with real sellers','Test listing readiness, seller publishing, buyer messages, report/moderation, and status workflows with trusted sellers.','Medium')
    ]
    for name,desc,risk in launch_upgrades:
        st.write(f'- **{name}** — {desc} Risk level: {risk}.')

    st.markdown('### Recommended build order')
    build_order=[
        'Real authentication/login',
        'Hosted database',
        'Cloud image storage',
        'Payment or checkout decision',
        'Shipping/pickup rules',
        'Legal pages and seller agreement',
        'Admin security hardening',
        'Beta testing with real sellers'
    ]
    for i,item in enumerate(build_order,1):
        st.write(f'{i}. {item}')
    st.markdown('### Hosted database prep now')
    st.write('Admin Database Status now checks for future hosted database settings without requiring them: SUPABASE_URL, SUPABASE_ANON_KEY, and DATABASE_URL.')
    st.write('If settings are missing, the app stays on local SQLite. If settings are detected, the app shows that configuration exists but does not run a risky migration.')
    st.markdown('### Auth / Login prep now')
    st.write('Open Auth / Login Prep in My House of Wax to review the future sign-up, login, password reset, dashboard, role-permission, and admin-lockdown plan.')
    st.write('The current role selector remains prototype-only until real authentication, sessions, and permission checks are implemented.')
    st.markdown('### Legal and policy prep now')
    st.write('Open Legal / Policies to review draft privacy, terms, seller agreement, buyer guidelines, marketplace rules, prohibited items, returns/pickup/shipping/disputes, and the production legal checklist.')
    st.write('These policy pages are prototype planning placeholders and must be reviewed by a qualified attorney before public launch.')
    st.markdown('### Payment / Checkout prep now')
    st.write('Open Payment / Checkout Prep to compare request-to-buy, seller-managed payment, House Of Wax-managed checkout, local pickup, shipping, and hybrid purchase models.')
    st.write('Recommended path: keep Request to Buy first, add admin-tracked pending/sold status next, then consider Stripe checkout only after real auth, hosted database, permanent image storage, legal terms, seller agreement, and refund/dispute policy are ready.')
    st.markdown('### Seller onboarding and launch checklist now')
    st.write('Open Seller Onboarding to walk early sellers through profile setup, listing creation, photos, readiness, publishing, inquiries, purchase requests, and pending/sold status management.')
    st.write('Open Marketplace Launch Checklist to track prototype-ready items, public launch blockers, early seller testing, and buyer testing.')
    st.markdown('### Business plan and funding roadmap now')
    st.write('Open Business Plan / Funding Roadmap to review the final demo test plan, business foundation, early seller launch plan, funding stages, use-of-funds priorities, and beta metrics.')
    st.warning('Do not present the prototype role selector as production security. Public launch requires real login, permissions, hosted storage, privacy rules, and operational policies.')


def auth_roles_plan():
    header()
    st.header('Auth + Roles Plan')
    st.info('Current role selection is prototype control only. Production launch will require real login, sessions, permission checks, and protected data access.')
    st.write('No new dependencies, secrets, or environment variables are required for this plan. It is a roadmap for the future auth build.')

    st.markdown('### Future roles')
    roles=[
        ('Buyer',['Marketplace','Listing details','Contact seller','Request to buy','Their own inquiries','Their own purchase requests','Saved/favorite items if added later']),
        ('Seller',['Seller dashboard','Upload/listing tools','Their own listings','Listing statuses and reviewer notes','Their seller profile','Their own buyer inquiries','Their own purchase requests']),
        ('Admin',['Moderation Center','Seller/listing moderation','Inquiry monitoring','Purchase request monitoring','Data health/export','User/seller controls when added later']),
        ('House Of Wax Official',['Official listings','Branded merch/listings','Official inventory tools','Same safe protections as seller tools, plus admin approval if needed'])
    ]
    for role,items in roles:
        with st.expander(role,expanded=True):
            for item in items:
                st.write(f'- {item}')

    st.markdown('### Security and data notes')
    notes=[
        'Private buyer/seller contact data must be protected.',
        'Admin tools must require real admin login before public launch.',
        'Sellers should not see other sellers private data.',
        'Buyers should not see admin or seller private tools.',
        'Every private action should check the logged-in user role on the server side, not only in the visible interface.',
        'House Of Wax Official can be an official seller account, but it still needs clear permissions and approval rules.'
    ]
    for note in notes:
        st.write(f'- {note}')

    st.markdown('### Future auth options')
    st.write('- **Supabase Auth** — strong fit if the hosted database also moves to Supabase/Postgres.')
    st.write('- **Streamlit authentication package** — useful for a quicker prototype-to-beta login layer.')
    st.write('- **Custom auth with a backend later** — more control, but higher engineering and security responsibility.')
    st.caption('Do not add these dependencies until the production path is chosen. The app should keep running without new secrets for now.')

    st.markdown('### Recommended next step')
    st.success('Choose the production auth/database direction before adding real user accounts. The cleanest next phase is real login first, then hosted database, then cloud photo storage.')


def auth_login_prep():
    header()
    st.header('Auth / Login Prep')
    st.info('V25.43 adds the real login and role-access foundation. Local fallback auth is still prototype/testing support, not production security.')
    st.warning('Production launch requires real authentication. Admin tools, buyer/seller private data, purchase requests, and contact information must be protected by real login and permission checks.')

    st.markdown('### Future login flow')
    flow=[
        'Sign up',
        'Log in',
        'Forgot password',
        'Buyer dashboard',
        'Seller dashboard',
        'Admin-only area'
    ]
    for i,item in enumerate(flow,1):
        st.write(f'{i}. {item}')

    st.markdown('### Future account fields')
    fields=[
        ('user_id','Unique account identifier from the auth provider or backend.'),
        ('email','Login email and account contact. Must be private by default.'),
        ('display_name','Public or semi-public account name shown where appropriate.'),
        ('role','Buyer, Seller, Admin, or House Of Wax Official.'),
        ('created_at','Account creation timestamp.'),
        ('last_login','Recent login timestamp for account health and admin review.'),
        ('status','Active, Pending, Suspended, Closed, or similar account state.')
    ]
    st.caption('Future account fields: user_id, email, display_name, role, created_at, last_login, status.')
    st.dataframe(pd.DataFrame(fields,columns=['Field','Purpose']),width='stretch')

    st.markdown('### Recommended future role permissions')
    role_permissions=[
        ('Buyer','Can access Marketplace, listing details, Contact Seller, Request to Buy, their own inquiries, their own purchase requests, and future saved/favorite items.','Cannot access seller dashboards, other buyers private data, seller private tools, or admin tools.'),
        ('Seller','Can access Seller dashboard, upload/listing tools, their own listings, listing statuses, reviewer notes, seller profile, their buyer inquiries, and their purchase requests.','Cannot access other sellers private data, admin moderation tools, or buyer-only private account areas.'),
        ('Admin','Can access Moderation Center, seller/listing moderation, inquiry monitoring, purchase request monitoring, data health/export, and future user/seller controls.','Should not be available without real admin login and audit-friendly permission checks.'),
        ('House Of Wax Official','Can manage official listings, branded merch/listings, official inventory tools, and seller-like workflows with platform oversight.','Should still follow safe seller protections and admin approval rules if needed.')
    ]
    for role,can,cannot in role_permissions:
        with st.expander(role,expanded=True):
            st.write(f'**Can access:** {can}')
            st.write(f'**Cannot access:** {cannot}')

    st.markdown('### Environment / secret readiness')
    config=auth_config_status()
    if config['auth_configured']:
        st.success('Auth settings detected. Values are masked.')
    else:
        st.info('Auth not connected yet. Local prototype login fallback is active.')
    st.caption('Configuration checked: AUTH_PROVIDER, SUPABASE_URL, SUPABASE_ANON_KEY, ADMIN_EMAILS.')
    st.dataframe(pd.DataFrame(config['rows']),width='stretch')

    st.markdown('### Security warnings')
    warnings=[
        'Local fallback login is for demo/testing only.',
        'Production launch requires real authentication.',
        'Admin tools must be protected by real login.',
        'Buyer and seller private data must be permission-protected.',
        'Sellers should only see their own private listing, inquiry, and purchase request data.',
        'Buyers should only see their own private inquiries, purchase requests, and account activity.'
    ]
    for item in warnings:
        st.write(f'- {item}')

    st.markdown('### Future implementation options')
    st.write('- **Supabase Auth** — recommended if House Of Wax moves the hosted database to Supabase/Postgres.')
    st.write('- **Streamlit auth package** — useful for a faster beta login layer, but still needs careful permissions.')
    st.write('- **Custom backend auth later** — gives more control, but requires more security, maintenance, and testing.')
    st.caption('No new auth dependencies, credentials, or secrets are required for V25.43.')



def barcode_diagnostics_page():
    header()
    st.header('Barcode Lookup Diagnostics')
    st.write('Use this page to test a barcode and see exactly which sources House Of Wax checks.')
    code=st.text_input('Barcode to test',key='standalone_diag_barcode')
    c1,c2=st.columns(2)
    artist=c1.text_input('Artist fallback',key='standalone_diag_artist',placeholder='Example: Lady Gaga')
    title=c2.text_input('Title fallback',key='standalone_diag_title',placeholder='Example: The Fame, Born This Way, Chromatica')
    c3,c4=st.columns(2)
    if c3.button('Run barcode diagnostic lookup',key='standalone_diag_run'):
        matches,diagnostics=lookup_barcode_with_diagnostics(code)
        st.session_state['standalone_diag_matches']=matches
        st.session_state['standalone_diag_results']=diagnostics
    if c4.button('Run artist/title search',key='standalone_text_diag_run'):
        matches,diagnostics=lookup_by_artist_title_with_diagnostics(artist,title,code)
        st.session_state['standalone_diag_matches']=matches
        st.session_state['standalone_diag_results']=diagnostics
    if st.button('Smart Search: Find Best Match',key='standalone_smart_best_match'):
        best,ranked,diagnostics=run_smart_best_match_search(
            st.session_state.get('standalone_diag_artist',''),
            st.session_state.get('standalone_diag_title',''),
            code
        )
        st.session_state['standalone_diag_matches']=ranked
        st.session_state['standalone_diag_results']=diagnostics
        st.session_state['standalone_best_match']=best
    render_best_match_card(
        st.session_state.get('standalone_best_match'),
        'standalone_diag',
        st.session_state.get('standalone_diag_matches',[]),
        st.session_state.get('standalone_diag_artist',''),
        st.session_state.get('standalone_diag_title',''),
        code
    )

    show_barcode_diagnostics(st.session_state.get('standalone_diag_results',[]))
    show_universal_search_links(st.session_state.get('standalone_diag_artist',''),st.session_state.get('standalone_diag_title',''),code)
    manual_release_seed_form(st.session_state.get('standalone_diag_artist',''),st.session_state.get('standalone_diag_title',''),code,'standalone_diag')


    matches=st.session_state.get('standalone_diag_matches',[])
    if matches:
        st.markdown('### Matches')
        for i,m in enumerate(matches,1):
            with st.container(border=True):
                st.write(f"**{i}. {safe(m.get('artist'))} - {safe(m.get('title'))}**")
                st.caption(f"{safe(m.get('source'))} • {safe(m.get('format'))} • {safe(m.get('release_year'))} • score {safe(m.get('_match_score'))}")
                if safe(m.get('image_url')):
                    safe_image(safe(m.get('image_url')),width=160,fallback_text='Match image unavailable.')
                st.write(safe(m.get('external_url')))


def app_mode():
    role=current_account_role()
    st.sidebar.caption('Account role: '+safe(role,'Public'))
    if is_authenticated():
        st.sidebar.caption('Signed in: '+auth_user_email())
    else:
        st.sidebar.caption('Public browsing mode. Sign in from Account.')
    testing=st.sidebar.toggle('Testing mode', value=False, help='Unauthenticated prototype testing only. Signed-in normal users cannot unlock Admin with this toggle.',key='testing_mode_enabled')
    if is_admin_unlocked():
        st.sidebar.warning('House Of Wax Admin is visible because Admin access or unauthenticated Testing mode is enabled.')
    elif testing and is_authenticated():
        st.sidebar.info('Testing mode cannot grant Admin access to a signed-in non-admin user.')
    return testing


# Called here, not right after setup(), deliberately: this function's call
# chain reaches functions defined much later in this file (e.g. get_buyer),
# and Streamlit re-executes the whole script top-to-bottom on every run --
# calling this too early hits those names before Python has reached their
# def statement in this pass, raising a NameError. Only reproduced for a
# user who already has a linked buyer profile, since that's the only case
# that reaches the affected call; a brand-new profile short-circuits before
# it. Confirmed live against production data before and after this fix.
restore_session_from_query_params()
if safe(st.query_params.get('recovery_token')):
    password_reset_completion_screen()
    st.stop()
if safe(st.query_params.get('legal'))=='privacy':
    public_privacy_policy()
    st.stop()
if safe(st.query_params.get('legal'))=='terms':
    public_terms_of_service()
    st.stop()
testing_mode=app_mode()
apply_share_deep_link()
area_options=['House Of Wax Marketplace']
if is_admin_unlocked():
    area_options.append('House Of Wax Admin')
area=st.sidebar.radio('Choose area',area_options,key='house_of_wax_area')
if area=='House Of Wax Marketplace':
    st.sidebar.markdown('### House Of Wax Marketplace')
    st.sidebar.caption('Simple buyer path: Home, Search Music, Seller Stores, and My Account.')
    marketplace_menu=['Home','Search Music','Knowledge Hub','Seller Stores','My Account']
    if has_seller_capability() or is_admin_unlocked():
        marketplace_menu.append('Seller Dashboard')
    apply_pending_marketplace_navigation(marketplace_menu)
    if st.session_state.get('marketplace_navigation') not in marketplace_menu:
        st.session_state['marketplace_navigation']='Search Music' if st.session_state.get('marketplace_navigation')=='Marketplace' else 'Home'
    menu=st.sidebar.radio('Marketplace navigation',marketplace_menu,key='marketplace_navigation')
else:
    pending_seller_apps=pending_seller_application_count()
    st.sidebar.markdown('### House Of Wax Admin'+(f' ⚠️ {pending_seller_apps} pending' if pending_seller_apps else ''))
    st.sidebar.caption('Platform management: seller approval, moderation, reports, tester feedback, database status, Supabase diagnostics, and testing.')
    admin_menu=['Admin Dashboard','User Directory','Buyer Lookup','Seller Applications','Moderation Center','Content Admin','Homepage Editor','Legal / Policies','Tester Feedback','Database Status / Diagnostics','Test Setup']
    pending_admin_nav=st.session_state.pop('pending_admin_navigation',None)
    if pending_admin_nav in admin_menu:
        st.session_state['admin_navigation']=pending_admin_nav
    menu=st.sidebar.radio('Admin navigation',admin_menu,key='admin_navigation')
st.sidebar.caption('[Privacy Policy](?legal=privacy) · [Terms of Service](?legal=terms)')
if area=='House Of Wax Marketplace':
    mobile_navigation_bar()
if area=='House Of Wax Marketplace' and menu=='Search Music' and ('seller_id' in st.session_state or 'product_id' in st.session_state):
    if st.sidebar.button('Main Search Music',key='main_marketplace_reset'):
        st.session_state.pop('seller_id',None)
        st.session_state.pop('product_id',None)
        st.rerun()
if area=='House Of Wax Marketplace':
    if menu=='Home': home()
    elif menu=='Search Music': marketplace()
    elif menu=='Seller Stores': seller_stores()
    elif menu=='My Account':
        account_page()
    elif menu=='Seller Dashboard': seller_dashboard()
    elif menu=='Knowledge Hub': knowledge_hub()
    elif menu=='Account': account_page()
    elif menu=='Seller Onboarding': seller_onboarding()
else:
    if menu=='Admin Dashboard':
        admin()
    elif menu=='User Directory':
        header()
        admin_context('House Of Wax Admin -> User Directory')
        if is_admin_unlocked():
            admin_user_directory()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Buyer Lookup':
        header()
        admin_context('House Of Wax Admin -> Buyer Lookup')
        if is_admin_unlocked():
            buyer_dashboard_admin_lookup()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Legal / Policies':
        if is_admin_unlocked():
            legal_policies()
        else:
            header()
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Seller Applications':
        header()
        admin_context('House Of Wax Admin -> Seller Applications')
        if is_admin_unlocked():
            admin_seller_applications()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Moderation Center':
        header()
        if is_admin_unlocked():
            listing_review_queue()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Content Admin':
        if is_admin_unlocked():
            content_admin()
        else:
            header()
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Homepage Editor':
        header()
        admin_context('House Of Wax Admin → Homepage Editor')
        if is_admin_unlocked():
            homepage_editor()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Tester Feedback':
        header()
        admin_context('House Of Wax Admin → Tester Feedback')
        if is_admin_unlocked():
            admin_tester_feedback_view()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Database Status / Diagnostics':
        header()
        if is_admin_unlocked():
            admin_database_status()
        else:
            st.error('House Of Wax Admin is locked. Switch to Admin role or turn on Testing mode.')
    elif menu=='Test Setup':
        test_setup()

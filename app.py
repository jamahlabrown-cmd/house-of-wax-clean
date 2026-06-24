
# ROOT APP DEPLOY FIX — upload THIS app.py to the repository root, replacing the old root app.py.
import sqlite3
import re
from urllib.parse import quote_plus
from pathlib import Path
from datetime import datetime
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title='House Of Wax', page_icon='🎧', layout='wide')
APP_VERSION='V25.11 SMART BEST-MATCH SEARCH'
DB=Path('house_of_wax.db')
UPLOAD=Path('house_of_wax_uploads'); UPLOAD.mkdir(exist_ok=True)
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
def conn(): return sqlite3.connect(DB)
def run(sql,p=()):
    c=conn(); c.execute(sql,p); c.commit(); c.close()
def df(sql,p=()):
    c=conn(); out=pd.read_sql_query(sql,c,params=p); c.close(); return out
def table(t):
    try: return df(f'SELECT * FROM {t}')
    except Exception: return pd.DataFrame()
def addcol(t,c,typ):
    try:
        info=df(f'PRAGMA table_info({t})')
        if c not in info['name'].tolist(): run(f'ALTER TABLE {t} ADD COLUMN {c} {typ}')
    except Exception: pass
def save_file(up,folder):
    if up is None: return ''
    f=UPLOAD/folder; f.mkdir(parents=True,exist_ok=True)
    p=f/(datetime.now().strftime('%Y%m%d%H%M%S')+'_'+up.name.replace(' ','_').replace('/','_'))
    p.write_bytes(up.getbuffer()); return str(p)
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
    return bool(email) and not df(f'SELECT id FROM {t} WHERE lower(email)=lower(?)',(email.strip(),)).empty

# ---------- Database ----------
def setup():
    c=conn(); cur=c.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT)')
    cur.execute('''CREATE TABLE IF NOT EXISTS buyers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,email TEXT UNIQUE,phone TEXT,city TEXT,state TEXT,bio TEXT,status TEXT DEFAULT 'Trusted Buyer',rating REAL DEFAULT 100,completed_purchases INTEGER DEFAULT 0,unpaid_orders INTEGER DEFAULT 0,disputes INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS sellers(id INTEGER PRIMARY KEY AUTOINCREMENT,store_name TEXT,owner_name TEXT,email TEXT UNIQUE,phone TEXT,city TEXT,state TEXT,website TEXT,instagram TEXT,store_bio TEXT,seller_story TEXT,specialties TEXT,logo_url TEXT,banner_url TEXT,status TEXT DEFAULT 'Approved',seller_level TEXT DEFAULT 'Verified Seller',rating REAL DEFAULT 100,completed_sales INTEGER DEFAULT 0,disputes INTEGER DEFAULT 0,strikes INTEGER DEFAULT 0,auction_override TEXT DEFAULT 'Yes',access_code TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,sku TEXT,barcode TEXT,catalog_number TEXT,matrix_runout TEXT,category TEXT,artist TEXT,title TEXT,format TEXT,label TEXT,release_year TEXT,genre TEXT,media_grade TEXT,sleeve_grade TEXT,condition_notes TEXT,description TEXT,price REAL DEFAULT 0,quantity INTEGER DEFAULT 1,shipping_price REAL DEFAULT 0,image_url TEXT,video_url TEXT,audio_url TEXT,external_release_url TEXT,listing_status TEXT DEFAULT 'Active',listing_type TEXT DEFAULT 'Fixed Price',created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS product_gallery(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,image_url TEXT,caption TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,order_type TEXT,status TEXT DEFAULT 'New',item_price REAL DEFAULT 0,shipping_price REAL DEFAULT 0,platform_fee REAL DEFAULT 0,seller_payout REAL DEFAULT 0,buyer_message TEXT,created_at TEXT,updated_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS feedback(id INTEGER PRIMARY KEY AUTOINCREMENT,order_id INTEGER,reviewer_type TEXT,reviewer_id INTEGER,reviewee_type TEXT,reviewee_id INTEGER,rating INTEGER,comment TEXT,public TEXT DEFAULT 'Yes',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,sender_type TEXT,subject TEXT,message TEXT,status TEXT DEFAULT 'New',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_followers(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,buyer_id INTEGER,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_badges(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,badge_name TEXT,badge_type TEXT,active TEXT DEFAULT 'Yes',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS store_announcements(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,title TEXT,body TEXT,status TEXT DEFAULT 'Active',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_events(id INTEGER PRIMARY KEY AUTOINCREMENT,seller_id INTEGER,event_title TEXT,event_type TEXT,event_date TEXT,description TEXT,status TEXT DEFAULT 'Active',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS seller_policies(seller_id INTEGER PRIMARY KEY,shipping_policy TEXT,return_policy TEXT,grading_policy TEXT,customer_service_policy TEXT,buyer_requirements TEXT,local_pickup_policy TEXT,processing_time TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS auctions(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,auction_title TEXT,starting_bid REAL,reserve_price REAL,buy_now_price REAL,bid_increment REAL DEFAULT 1,start_time TEXT,end_time TEXT,status TEXT DEFAULT 'Live',notes TEXT,created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS bids(id INTEGER PRIMARY KEY AUTOINCREMENT,auction_id INTEGER,buyer_id INTEGER,bid_amount REAL,bid_time TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS listing_flags(id INTEGER PRIMARY KEY AUTOINCREMENT,product_id INTEGER,seller_id INTEGER,buyer_id INTEGER,reason TEXT,details TEXT,status TEXT DEFAULT 'Open',created_at TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS culture_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,category TEXT,author TEXT,body TEXT,image_url TEXT,status TEXT DEFAULT 'Published',created_at TEXT)''')
    cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_posts(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,category TEXT,audience TEXT,level TEXT,summary TEXT,body TEXT,house_tip TEXT,image_url TEXT,status TEXT DEFAULT 'Draft',featured TEXT DEFAULT 'No',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS glossary_terms(id INTEGER PRIMARY KEY AUTOINCREMENT,term TEXT UNIQUE,category TEXT,plain_definition TEXT,why_it_matters TEXT,example TEXT,status TEXT DEFAULT 'Published',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_drafts(id INTEGER PRIMARY KEY AUTOINCREMENT,source_type TEXT,source_id INTEGER,title TEXT,platform TEXT,caption TEXT,script TEXT,hashtags TEXT,cta TEXT,status TEXT DEFAULT 'Draft',created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS content_calendar(id INTEGER PRIMARY KEY AUTOINCREMENT,content_type TEXT,topic TEXT,platform TEXT,planned_date TEXT,status TEXT DEFAULT 'Planned',notes TEXT,created_at TEXT,updated_at TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS homepage_blocks(id INTEGER PRIMARY KEY AUTOINCREMENT,block_name TEXT,title TEXT,subtitle TEXT,body TEXT,button_text TEXT,button_target TEXT,image_url TEXT,status TEXT DEFAULT 'Active',sort_order INTEGER DEFAULT 0,created_at TEXT,updated_at TEXT)""")
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
    mig={'buyers':{'state':'TEXT','bio':'TEXT','status':'TEXT','rating':'REAL','completed_purchases':'INTEGER','unpaid_orders':'INTEGER'},'sellers':{'state':'TEXT','website':'TEXT','instagram':'TEXT','seller_story':'TEXT','specialties':'TEXT','logo_url':'TEXT','banner_url':'TEXT','status':'TEXT','seller_level':'TEXT','rating':'REAL','completed_sales':'INTEGER','auction_override':'TEXT','access_code':'TEXT'},'products':{'sku':'TEXT','barcode':'TEXT','catalog_number':'TEXT','matrix_runout':'TEXT','label':'TEXT','release_year':'TEXT','video_url':'TEXT','audio_url':'TEXT','external_release_url':'TEXT','listing_status':'TEXT','listing_type':'TEXT'},'feedback':{'public':'TEXT'}}
    for t,cols in mig.items():
        for col,typ in cols.items(): addcol(t,col,typ)
    for k,v in {'site_tagline':'A seller-powered marketplace for records, music culture, clothing, and collectors.','announcement':'V16 testing build: all core options are active.','platform_commission_percent':'9','auction_commission_percent':'10'}.items():
        if setting(k, None) is None: set_setting(k,v)
setup()


# ---------- V21 Visual Identity ----------
def apply_brand_style():
    st.markdown("""
    <style>
    :root {
        --how-black: #0b0b0b;
        --how-charcoal: #171717;
        --how-ink: #222222;
        --how-cream: #f6efe3;
        --how-bone: #fbf7ef;
        --how-gold: #c9a45c;
        --how-oxblood: #6f1d1b;
        --how-muted: #9b8f80;
        --how-card: #151515;
        --how-line: rgba(201,164,92,.35);
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
        letter-spacing: -0.03em;
        color: var(--how-cream) !important;
    }

    p, li, label, span {
        color: rgba(246,239,227,.92);
    }

    .block-container {
        padding-top: 1.8rem;
        max-width: 1180px;
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

    .stButton > button {
        border-radius: 999px;
        border: 1px solid rgba(201,164,92,.65);
        background: linear-gradient(135deg, rgba(201,164,92,.96), rgba(151,111,45,.96));
        color: #0b0b0b !important;
        font-weight: 800;
        letter-spacing: .01em;
        padding: .55rem 1rem;
        box-shadow: 0 10px 30px rgba(0,0,0,.22);
    }

    .stButton > button:hover {
        border: 1px solid rgba(246,239,227,.9);
        transform: translateY(-1px);
        filter: brightness(1.05);
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: .35rem;
        border-bottom: 1px solid rgba(201,164,92,.25);
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 999px 999px 0 0;
        color: rgba(246,239,227,.72);
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
        border: 1px solid rgba(201,164,92,.35);
        border-radius: 28px;
        padding: 34px;
        background:
            linear-gradient(135deg, rgba(11,11,11,.92), rgba(34,20,16,.86)),
            radial-gradient(circle at bottom right, rgba(201,164,92,.2), transparent 34%);
        box-shadow: 0 24px 70px rgba(0,0,0,.35);
        margin-bottom: 22px;
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
        color: var(--how-cream);
        font-size: clamp(2.5rem, 6vw, 5.2rem);
        line-height: .9;
        letter-spacing: -.06em;
        font-weight: 950;
        margin-bottom: .6rem;
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
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: -.04em;
        margin-bottom: .2rem;
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

    </style>
    """, unsafe_allow_html=True)

def section_header(title, subtitle='', kicker='House Of Wax'):
    st.markdown(f"""
    <div class="how-section">
        <div class="how-kicker">{kicker}</div>
        <div class="how-section-title">{title}</div>
        <div class="how-section-copy">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)

def brand_badges(labels):
    html=''.join([f'<span class="how-badge">{safe(label)}</span>' for label in labels])
    st.markdown(html, unsafe_allow_html=True)


# ---------- Data helpers ----------
def get_buyer(i):
    r=df('SELECT * FROM buyers WHERE id=?',(int(i),)); return None if r.empty else r.iloc[0]
def get_seller(i):
    r=df('SELECT * FROM sellers WHERE id=?',(int(i),)); return None if r.empty else r.iloc[0]
def ensure_buyer():
    b=table('buyers')
    if not b.empty: return int(b.iloc[0]['id'])
    run('''INSERT INTO buyers(name,email,phone,city,state,bio,status,rating,completed_purchases,unpaid_orders,disputes,strikes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',('Demo Buyer','buyer@test.com','1234567890','Charlotte','NC','Demo buyer for testing.','Trusted Buyer',100,0,0,0,0,now()))
    return int(table('buyers').iloc[0]['id'])
def ensure_seller():
    s=table('sellers')
    if not s.empty: return int(s.iloc[0]['id'])
    run('''INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',('Demo Wax Seller','Demo Owner','seller@test.com','1234567890','Charlotte','NC','https://example.com','@demowax','A demo seller for testing.','We collect records, culture goods, vintage music pieces, and community stories.','Soul, jazz, hip-hop, Carolina music, vintage tees','','','Approved','Verified Seller',100,12,0,0,'Yes','test123',now()))
    return int(table('sellers').iloc[0]['id'])

def ensure_house_of_wax_official():
    rows=df("SELECT * FROM sellers WHERE lower(store_name)=lower('House Of Wax Official') OR lower(email)=lower('official@houseofwax.com')")
    if not rows.empty:
        sid=int(rows.iloc[0]['id'])
    else:
        run("""INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ('House Of Wax Official','House Of Wax','official@houseofwax.com','','Charlotte','NC','','@houseofwax','The official House Of Wax seller account for branded merchandise, official drops, curated goods, and platform items.','House Of Wax is the platform voice for music culture, collecting education, marketplace trust, and official brand drops.','House Of Wax branded merchandise, slipmats, culture goods, official drops, curated records','','','Approved','Platform Official',100,0,0,0,'Yes','official123',now()))
        sid=int(df("SELECT id FROM sellers WHERE lower(email)=lower('official@houseofwax.com')").iloc[0]['id'])
    badge=df("SELECT id FROM seller_badges WHERE seller_id=? AND badge_name='Official House Of Wax'",(sid,))
    if badge.empty:
        run("INSERT INTO seller_badges(seller_id,badge_name,badge_type,active,created_at) VALUES(?,?,?,'Yes',?)",(sid,'Official House Of Wax','Platform',now()))
    existing=df("SELECT id FROM products WHERE seller_id=? AND title='House Of Wax Logo Tee'",(sid,))
    if existing.empty:
        run("""INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (sid,'HOW-TEE-001','','','','House Of Wax Merch','House Of Wax','House Of Wax Logo Tee','Apparel','House Of Wax','','Merch','New','New','Official sample item for testing.','Official House Of Wax branded tee sample. Replace with real photos and inventory when ready.',28.00,25,5.00,'','','','','Active','Fixed Price',now(),now()))
    return sid


def ensure_product():
    p=table('products')
    if not p.empty: return int(p.iloc[0]['id'])
    sid=ensure_seller()
    run('''INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,'DEMO-001','602547234567','CAT-001','A1/B1','Vinyl Records','Demo Artist','Demo Album','Vinyl','Demo Label','1978','Soul','VG+','VG','Light sleeve wear. Plays strong.','Demo product with barcode metadata.',24.99,1,5.00,'','','','','Active','Fixed Price',now(),now()))
    return int(table('products').iloc[0]['id'])
def seed_all(): return ensure_buyer(), ensure_seller(), ensure_house_of_wax_official(), ensure_product()
def create_buyer(email,name='Test Buyer'):
    email=(email or 'buyer@test.com').strip().lower()
    r=df('SELECT id FROM buyers WHERE lower(email)=lower(?)',(email,))
    if not r.empty: return int(r.iloc[0]['id'])
    run('''INSERT INTO buyers(name,email,phone,city,state,bio,status,rating,completed_purchases,unpaid_orders,disputes,strikes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(name,email,'','','','','Trusted Buyer',100,0,0,0,0,now()))
    return int(df('SELECT id FROM buyers WHERE lower(email)=lower(?)',(email,)).iloc[0]['id'])
def update_rating(kind,i):
    r=df("SELECT AVG(rating) avg FROM feedback WHERE reviewee_type=? AND reviewee_id=? AND public='Yes'",(kind,int(i)))
    if not r.empty and not pd.isna(r.iloc[0]['avg']):
        score=round(float(r.iloc[0]['avg'])*20,1)
        run(('UPDATE sellers SET rating=? WHERE id=?' if kind=='Seller' else 'UPDATE buyers SET rating=? WHERE id=?'),(score,int(i)))
def barcode_lookup(code):
    if not code: return {}
    r=df('''SELECT barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,description,price,shipping_price,image_url FROM products WHERE barcode=? ORDER BY created_at DESC LIMIT 1''',(code.strip(),))
    return {} if r.empty else r.iloc[0].to_dict()
def badges(sid):
    r=df("SELECT badge_name FROM seller_badges WHERE seller_id=? AND active='Yes'",(int(sid),))
    return '' if r.empty else ' • '.join([safe(x) for x in r['badge_name'].tolist()])
def followers(sid):
    r=df('SELECT COUNT(*) c FROM seller_followers WHERE seller_id=?',(int(sid),)); return 0 if r.empty else int(r.iloc[0]['c'] or 0)
def fee(total,auction=False): return round(float(total)*float(setting('auction_commission_percent' if auction else 'platform_commission_percent','9'))/100,2)

# ---------- UI helpers ----------
def header():
    apply_brand_style()
    st.title('🎧 House Of Wax')
    st.caption(setting('site_tagline'))
    brand_badges(['Marketplace', 'Knowledge Hub', 'Culture Education', 'Collect Smarter'])
    st.caption(f'Running {APP_VERSION}')
    st.warning('TESTING BUILD: seller stores, product upload, barcode inventory, buyer/seller profiles, public feedback, messaging, auctions, and admin are active.')
    st.info(setting('announcement'))
def buyer_pick(key,label='Buyer account'):
    if table('buyers').empty: ensure_buyer()
    opts=[f"{int(r['id'])} | {safe(r['name'])} | {safe(r['email'])} | {safe(r['status'])}" for _,r in table('buyers').iterrows()]
    return int(st.selectbox(label,opts,key=key).split('|')[0].strip())
def seller_pick(key,label='Seller account'):
    if table('sellers').empty: ensure_seller()
    opts=[f"{int(r['id'])} | {safe(r['store_name'])} | {safe(r['email'])} | {safe(r['status'])}" for _,r in table('sellers').iterrows()]
    return int(st.selectbox(label,opts,key=key).split('|')[0].strip())
def feedback_public(kind,i):
    r=df("SELECT * FROM feedback WHERE reviewee_type=? AND reviewee_id=? AND public='Yes' ORDER BY created_at DESC",(kind,int(i)))
    if r.empty: st.info('No public feedback yet.'); return
    st.metric('Public feedback score',f"{round(r['rating'].mean(),2)} / 5")
    for _,x in r.iterrows():
        with st.container(border=True): st.write(f"⭐ **{x['rating']} / 5**"); st.caption(f"{safe(x['reviewer_type'])} review • {safe(x['created_at'])}"); st.write(safe(x['comment'],'No comment.'))
def buyer_profile_public(bid):
    b=get_buyer(bid)
    if b is None: bid=ensure_buyer(); b=get_buyer(bid)
    st.subheader(f"Buyer trust profile: {safe(b['name'])}")
    c1,c2,c3,c4=st.columns(4); c1.metric('Status',safe(b['status'])); c2.metric('Rating',f"{b['rating']}%"); c3.metric('Purchases',int(b['completed_purchases'] or 0)); c4.metric('Unpaid orders',int(b['unpaid_orders'] or 0))
    st.write(f"**Bio:** {safe(b['bio'],'No buyer bio yet.')}"); feedback_public('Buyer',bid)
def product_card(p):
    with st.container(border=True):
        if safe(p['image_url']): st.image(safe(p['image_url']),use_container_width=True)
        else: st.markdown('### 🎵')
        st.subheader(f"{safe(p['artist'])} — {safe(p['title'])}"); st.caption(f"{safe(p['category'])} • {safe(p['format'])} • Barcode: {safe(p['barcode'],'none')}"); st.write(f"**Price:** {money(p['price'])}")
        if st.button('View item',key=f"item_{int(p['id'])}"): st.session_state['product_id']=int(p['id']); st.rerun()
def seller_profile(sid):
    s=get_seller(sid)
    if s is None: st.error('Seller not found.'); return
    if st.button('← Back'): st.session_state.pop('seller_id',None); st.rerun()
    if safe(s['banner_url']): st.image(safe(s['banner_url']),use_container_width=True)
    col1,col2=st.columns([1,4])
    with col1:
        if safe(s['logo_url']): st.image(safe(s['logo_url']),use_container_width=True)
        else: st.markdown('## 🏪')
    with col2:
        st.title(safe(s['store_name'])); st.caption(f"{safe(s['seller_level'])} • Rating {s['rating']}% • Sales {s['completed_sales']} • Followers {followers(sid)}")
        if badges(sid): st.info('Badges: '+badges(sid))
        if safe(s['instagram']): st.write('Instagram: '+safe(s['instagram']))
        if safe(s['website']): st.link_button('Seller website',safe(s['website']))
    with st.expander('Follow this seller'):
        bid=buyer_pick(f'follow{sid}')
        if st.button('Follow seller',key=f'followbtn{sid}'):
            if df('SELECT id FROM seller_followers WHERE seller_id=? AND buyer_id=?',(sid,bid)).empty: run('INSERT INTO seller_followers(seller_id,buyer_id,created_at) VALUES(?,?,?)',(sid,bid,now())); st.success('Followed.')
            else: st.info('Already following.')
    anns=df("SELECT * FROM store_announcements WHERE seller_id=? AND status='Active' ORDER BY created_at DESC",(sid,))
    if not anns.empty:
        st.subheader('Store announcements')
        for _,a in anns.iterrows():
            with st.container(border=True): st.write('**'+safe(a['title'])+'**'); st.write(safe(a['body']))
    evs=df("SELECT * FROM seller_events WHERE seller_id=? AND status='Active' ORDER BY event_date",(sid,))
    if not evs.empty:
        st.subheader('Drops / events')
        for _,e in evs.iterrows():
            with st.container(border=True): st.write(f"**{safe(e['event_title'])}** — {safe(e['event_type'])}"); st.caption(safe(e['event_date'])); st.write(safe(e['description']))
    st.subheader('About this seller'); st.write(safe(s['seller_story'],safe(s['store_bio'],'No story yet.'))); st.write('**Specialties:** '+safe(s['specialties'],'Not listed'))
    st.subheader('Public seller feedback'); feedback_public('Seller',sid)
    st.subheader('Public inventory')
    prods=df("SELECT * FROM products WHERE seller_id=? AND listing_status IN ('Active','Draft') ORDER BY created_at DESC",(sid,))
    if prods.empty: st.info('No inventory yet.')
    else:
        cols=st.columns(3)
        for i,(_,p) in enumerate(prods.iterrows()):
            with cols[i%3]: product_card(p)
def product_detail(pid):
    r=df('SELECT * FROM products WHERE id=?',(int(pid),))
    if r.empty: st.error('Product missing.'); st.session_state.pop('product_id',None); return
    p=r.iloc[0]; s=get_seller(int(p['seller_id']))
    if st.button('← Back to marketplace'): st.session_state.pop('product_id',None); st.rerun()
    l,rcol=st.columns([1.2,1])
    with l:
        if safe(p['image_url']): st.image(safe(p['image_url']),use_container_width=True)
        else: st.markdown('## 🎵')
        gal=df('SELECT * FROM product_gallery WHERE product_id=? ORDER BY created_at DESC',(pid,))
        if not gal.empty:
            st.subheader('Gallery')
            for _,g in gal.iterrows():
                if safe(g['image_url']): st.image(safe(g['image_url']),caption=safe(g['caption']),use_container_width=True)
    with rcol:
        st.title(f"{safe(p['artist'])} — {safe(p['title'])}"); st.write('**Price:** '+money(p['price'])); st.write('**Shipping:** '+money(p['shipping_price']))
        for label,col in [('Category','category'),('Format','format'),('Label','label'),('Release year','release_year'),('Barcode / UPC / EAN','barcode'),('Catalog #','catalog_number'),('Matrix / runout','matrix_runout'),('Condition','media_grade')]: st.write(f"**{label}:** {safe(p[col],'Not listed')}")
        if s is not None and st.button('View seller public profile'): st.session_state['seller_id']=int(s['id']); st.session_state.pop('product_id',None); st.rerun()
    st.subheader('Description'); st.write(safe(p['description'],'No description.'))
    st.divider(); st.subheader('Buyer actions')
    bid=buyer_pick(f'buy{pid}')
    with st.expander('Request to buy / message seller',expanded=True):
        action=st.selectbox('Action',['Request to Buy','Ask a Question','Make Offer'],key=f'act{pid}'); msg=st.text_area('Message',key=f'msg{pid}')
        if st.button('Send to seller',key=f'send{pid}'):
            total=float(p['price'] or 0)+float(p['shipping_price'] or 0); pf=fee(total)
            run('''INSERT INTO orders(product_id,seller_id,buyer_id,order_type,status,item_price,shipping_price,platform_fee,seller_payout,buyer_message,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',(pid,int(p['seller_id']),bid,action,'New',float(p['price'] or 0),float(p['shipping_price'] or 0),pf,total-pf,msg,now(),now()))
            run('''INSERT INTO messages(product_id,seller_id,buyer_id,sender_type,subject,message,status,created_at) VALUES(?,?,?,?,?,?,?,?)''',(pid,int(p['seller_id']),bid,'Buyer',action,msg,'New',now()))
            st.success('Sent. It appears in seller orders and messages.')
    with st.expander('Report listing'):
        reason=st.selectbox('Reason',['Counterfeit / Bootleg','Misgraded','Wrong information','Spam','Other']); details=st.text_area('Details')
        if st.button('Submit report'): run("INSERT INTO listing_flags(product_id,seller_id,buyer_id,reason,details,status,created_at) VALUES(?,?,?,?,?,'Open',?)",(pid,int(p['seller_id']),bid,reason,details,now())); st.success('Report submitted.')

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
            run("""INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (title,cat,aud,level,summary,body,tip,'Published','Yes' if 'VG+' in title else 'No',now(),now()))
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
            run("""INSERT OR IGNORE INTO glossary_terms(term,category,plain_definition,why_it_matters,example,status,created_at,updated_at) VALUES(?,?,?,?,?,'Published',?,?)""",
                (term,cat,definition,why,example,now(),now()))

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
        if safe(row.get('image_url')): st.image(safe(row.get('image_url')),use_container_width=True)
        st.subheader(safe(row.get('title')))
        st.caption(f"{safe(row.get('category'))} • {safe(row.get('level'))} • {safe(row.get('audience'))}")
        st.write(safe(row.get('summary')))
        unique_key=f"read_knowledge_{key_prefix}_{int(row['id'])}"
        if st.button('Read article',key=unique_key):
            st.session_state['selected_knowledge_id']=int(row['id']); st.rerun()

def knowledge_hub():
    seed_knowledge()
    header()
    st.header('House Of Wax Knowledge Hub')
    st.write('House Of Wax-owned education, culture, history, discovery, content series, and marketplace learning. This is not seller promotion. This hub teaches buyers, collectors, and visitors how to understand records, music culture, formats, trust, grading, barcodes, catalog numbers, matrix/runouts, genres, eras, and safe buying.')
    if 'selected_knowledge_id' in st.session_state:
        rows=df('SELECT * FROM knowledge_posts WHERE id=?',(int(st.session_state['selected_knowledge_id']),))
        if rows.empty:
            st.session_state.pop('selected_knowledge_id',None); st.rerun()
        post=rows.iloc[0]
        if st.button('← Back to Knowledge Hub'):
            st.session_state.pop('selected_knowledge_id',None); st.rerun()
        st.title(safe(post['title']))
        st.caption(f"{safe(post['category'])} • {safe(post['level'])} • For {safe(post['audience'])}")
        if safe(post['image_url']): st.image(safe(post['image_url']),use_container_width=True)
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
    featured=df("SELECT * FROM knowledge_posts WHERE status='Published' AND featured='Yes' ORDER BY updated_at DESC")
    if not featured.empty:
        st.subheader('Featured education')
        knowledge_card(featured.iloc[0], 'featured')
    st.subheader('Search the education library')
    q=st.text_input('Search topics like VG+, barcode, runout, bootleg, storage, trust')
    cats=['All']+KNOWLEDGE_CATEGORIES
    cat=st.selectbox('Category',cats)
    posts=df("SELECT * FROM knowledge_posts WHERE status='Published' ORDER BY updated_at DESC")
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
    st.divider()
    st.subheader('Collector glossary')
    terms=df("SELECT * FROM glossary_terms WHERE status='Published' ORDER BY term")
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
    tabs=st.tabs(['Article creator','Glossary builder','Social copy generator','Draft library','Content calendar','Reports','Content Series','Campaigns'])
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
            status=st.selectbox('Status',['Draft','Published'])
            featured=st.selectbox('Featured',['No','Yes'])
            submitted=st.form_submit_button('Save education article')
        if submitted:
            img=save(img_file,'knowledge_images') or img_url
            run("""INSERT INTO knowledge_posts(title,category,audience,level,summary,body,house_tip,image_url,status,featured,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (title,category,audience,level,summary,body,tip,img,status,featured,now(),now()))
            st.success('Knowledge article saved.')
        st.dataframe(table('knowledge_posts'),use_container_width=True)
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
            run("""INSERT OR REPLACE INTO glossary_terms(term,category,plain_definition,why_it_matters,example,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)""",
                (term,category,definition,why,example,status,now(),now()))
            st.success('Glossary term saved.')
        st.dataframe(table('glossary_terms'),use_container_width=True)
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
        st.dataframe(drafts,use_container_width=True)
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
        st.dataframe(table('content_calendar'),use_container_width=True)
    with tabs[5]:
        rep=st.selectbox('Content report',['knowledge_posts','glossary_terms','content_drafts','content_calendar','homepage_blocks','quick_tips','did_you_know','newsletter_signups'])
        data=table(rep)
        st.dataframe(data,use_container_width=True)
        st.download_button('Download CSV',data.to_csv(index=False),file_name=f'{rep}.csv')


# ---------- V18 Home + Editorial Experience ----------
def seed_homepage_editorial():
    seed_knowledge()
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
    r=df("SELECT * FROM homepage_blocks WHERE block_name=? AND status='Active' ORDER BY sort_order,id LIMIT 1",(name,))
    return {} if r.empty else r.iloc[0].to_dict()

def mini_card(title,subtitle,body):
    with st.container(border=True):
        st.caption(safe(subtitle))
        st.subheader(safe(title))
        st.write(safe(body))

def home():
    seed_homepage_editorial()
    header()
    hero=home_block('hero')
    st.markdown('---')
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
    if a.button('Explore Marketplace'): st.info('Use the sidebar to open Marketplace.')
    if b.button('Visit Knowledge Hub'): st.info('Use the sidebar to open Knowledge Hub.')
    if c.button("Read This Week's Feature"): st.info('Use the sidebar to open Knowledge Hub.')
    c1,c2,c3,c4=st.columns(4)
    c1.metric('Knowledge Articles',len(table('knowledge_posts')))
    c2.metric('Glossary Terms',len(table('glossary_terms')))
    c3.metric('Marketplace Items',len(table('products')))
    c4.metric('Community Posts',len(table('culture_posts')))
    st.markdown('---')
    l,r=st.columns(2)
    with l:
        x=home_block('featured_story'); mini_card(x.get('title','What Does VG+ Really Mean?'),x.get('subtitle','Featured Story'),x.get('body','Learn grading before you buy.'))
    with r:
        x=home_block('weekly_focus'); mini_card(x.get('title','This Week at House Of Wax'),x.get('subtitle','Matrix / Runout'),x.get('body','Runout markings can reveal pressing details.'))
    st.markdown('---')
    st.markdown('---')
    c1,c2,c3=st.columns(3)
    with c1:
        with st.container(border=True):
            st.subheader('About House Of Wax')
            st.write('Learn what the platform is, who it is for, and why culture and trust are built in.')
    with c2:
        with st.container(border=True):
            st.subheader('Trust & Safety')
            st.write('Read the standards behind buyer/seller feedback, transparency, and marketplace trust.')
    with c3:
        with st.container(border=True):
            st.subheader('Join the List')
            st.write('Sign up for Knowledge Hub updates, collecting tips, culture stories, and future drops.')

    section_header('Learn the Culture','Start with the basics or go deeper into pressings, grading, formats, trust, and music history.','Education + Discovery')
    tiles=[
        ('Record Collecting 101','Learn the basic language of collecting.'),
        ('Vinyl Grading School','Understand Mint, Near Mint, VG+, VG, and Good.'),
        ('Barcode, Catalog & Matrix Guides','Learn how identifiers help verify releases.'),
        ('Bootlegs & Reissues','Learn originals, reissues, unofficial pressings, and bootlegs.'),
        ('Care, Storage & Cleaning','Protect records, sleeves, tapes, CDs, posters, and memorabilia.'),
        ('Music History & Culture','Explore scenes, regions, genres, and movements.'),
        ('Genre Education','Learn the roots and sounds behind different genres.'),
        ('House Of Wax Trust Standards','Understand transparency and public feedback.')
    ]
    cols=st.columns(4)
    for i,(t,bdy) in enumerate(tiles):
        with cols[i%4]: mini_card(t,'Knowledge path',bdy)
    st.markdown('---')
    q,d=st.columns(2)
    with q:
        section_header('Collector Quick Tips','Useful knowledge in seconds.','Collect Smarter')
        tips=df("SELECT * FROM quick_tips WHERE status='Active' ORDER BY id LIMIT 5")
        for _,tip in tips.iterrows(): st.write(f"• {safe(tip['tip_text'])}")
    with d:
        section_header('Did You Know?','Fast facts from House Of Wax.','Quick Culture')
        facts=df("SELECT * FROM did_you_know WHERE status='Active' ORDER BY id LIMIT 4")
        for _,fact in facts.iterrows(): mini_card('Did you know?',safe(fact['category']),safe(fact['fact_text']))
    st.markdown('---')
    s,p=st.columns(2)
    with s:
        x=home_block('genre_spotlight'); mini_card(x.get('title','Southern Soul Essentials'),x.get('subtitle','Genre / Era Spotlight'),x.get('body','Explore the sound, labels, artists, and culture.'))
    with p:
        x=home_block('editorial_pick'); mini_card(x.get('title','Format Focus: Why Cassettes Still Matter'),x.get('subtitle','House Of Wax Editorial Pick'),x.get('body','Cassettes connect music to memory and mixtape culture.'))
    st.markdown('---')
    section_header('Latest From the Knowledge Hub','House Of Wax education, culture, and collecting guides.','Read + Learn')
    posts=df("SELECT * FROM knowledge_posts WHERE status='Published' ORDER BY updated_at DESC LIMIT 6")
    cols=st.columns(3)
    for i,(_,post) in enumerate(posts.iterrows()):
        with cols[i%3]: knowledge_card(post, f'home_latest_{i}')
    st.markdown('---')
    news=home_block('newsletter')
    st.markdown(f"## {safe(news.get('title'),'Join House Of Wax')}")
    st.write(safe(news.get('body'),'Get collector tips, music culture stories, grading guides, and marketplace education from House Of Wax.'))
    n1,n2,n3=st.columns([1,1,1])
    name=n1.text_input('Name',key='newsletter_name')
    email=n2.text_input('Email',key='newsletter_email')
    if n3.button('Join the List'):
        if not safe(email): st.warning('Enter an email first.')
        else:
            run("INSERT INTO newsletter_signups(email,name,source,created_at) VALUES(?,?,?,?)",(email,name,'Homepage',now()))
            st.success('You are on the House Of Wax list.')

def homepage_editor():
    seed_homepage_editorial()
    st.subheader('Homepage Editor')
    tabs=st.tabs(['Homepage Blocks','Quick Tips','Did You Know','Newsletter Signups'])
    with tabs[0]:
        st.dataframe(table('homepage_blocks'),use_container_width=True)
        with st.form('home_block_form'):
            bn=st.selectbox('Block',['hero','featured_story','weekly_focus','genre_spotlight','editorial_pick','newsletter'])
            title=st.text_input('Title'); sub=st.text_input('Subtitle'); body=st.text_area('Body')
            btn=st.text_input('Button text'); target=st.text_input('Button target')
            status=st.selectbox('Status',['Active','Draft','Hidden'])
            order=st.number_input('Sort order',min_value=0,value=1)
            if st.form_submit_button('Save homepage block'):
                run("INSERT INTO homepage_blocks(block_name,title,subtitle,body,button_text,button_target,status,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(bn,title,sub,body,btn,target,status,int(order),now(),now()))
                st.success('Homepage block saved.')
    with tabs[1]:
        st.dataframe(table('quick_tips'),use_container_width=True)
        with st.form('tip_form'):
            tip=st.text_area('Quick tip'); cat=st.text_input('Category')
            status=st.selectbox('Status',['Active','Draft','Hidden'],key='tip_status')
            if st.form_submit_button('Save quick tip'):
                run("INSERT INTO quick_tips(tip_text,category,status,created_at,updated_at) VALUES(?,?,?,?,?)",(tip,cat,status,now(),now()))
                st.success('Quick tip saved.')
    with tabs[2]:
        st.dataframe(table('did_you_know'),use_container_width=True)
        with st.form('fact_form'):
            fact=st.text_area('Fact'); cat=st.text_input('Category',key='fact_cat')
            status=st.selectbox('Status',['Active','Draft','Hidden'],key='fact_status')
            if st.form_submit_button('Save fact'):
                run("INSERT INTO did_you_know(fact_text,category,status,created_at,updated_at) VALUES(?,?,?,?,?)",(fact,cat,status,now(),now()))
                st.success('Fact saved.')
    with tabs[3]:
        data=table('newsletter_signups')
        st.dataframe(data,use_container_width=True)
        if not data.empty:
            st.download_button('Download newsletter signups',data.to_csv(index=False),file_name='newsletter_signups.csv')

def test_setup():
    header(); st.header('Test setup')
    if st.button('Create/repair demo buyer, seller, and product'): st.success(f'Demo ready: buyer/seller/product IDs {seed_all()}')
    st.code('Buyer: buyer@test.com\nSeller: seller@test.com\nSeller access code: test123')
    st.subheader('Buyers'); st.dataframe(table('buyers'),use_container_width=True); st.subheader('Sellers'); st.dataframe(table('sellers'),use_container_width=True); st.subheader('Products'); st.dataframe(table('products'),use_container_width=True)
def register():
    header(); st.header('Sell on House Of Wax / Create Accounts')
    st.info('House Of Wax is the platform. Independent sellers list their own inventory. House Of Wax can also sell through its official seller account for branded merch, official drops, curated goods, and platform items. Seller tools now live under My House of Wax. Before public launch, sellers should review Seller Standards and House Of Wax trust expectations.'); btab,stab=st.tabs(['Buyer','Seller store'])
    with btab:
        with st.form('buyerform'):
            name=st.text_input('Buyer name'); email=st.text_input('Buyer email'); phone=st.text_input('Phone'); city=st.text_input('City'); state=st.text_input('State'); bio=st.text_area('Buyer bio'); sub=st.form_submit_button('Create buyer')
        if sub:
            if email_exists('buyers',email): st.warning('Buyer already exists. Open My House of Wax.')
            else: run('''INSERT INTO buyers(name,email,phone,city,state,bio,status,rating,completed_purchases,unpaid_orders,disputes,strikes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(name,email,phone,city,state,bio,'Trusted Buyer',100,0,0,0,0,now())); st.success('Buyer created.')
    with stab:
        with st.form('sellerform'):
            store=st.text_input('Store name'); owner=st.text_input('Owner'); email=st.text_input('Seller email'); code=st.text_input('Access code',type='password'); bio=st.text_area('Store bio'); story=st.text_area('Seller story'); spec=st.text_area('Specialties'); logo=st.file_uploader('Logo',type=['png','jpg','jpeg','webp']); banner=st.file_uploader('Banner',type=['png','jpg','jpeg','webp']); sub=st.form_submit_button('Create active seller store')
        if sub:
            if email_exists('sellers',email): st.warning('Seller already exists. Open Seller Tools.')
            else: run('''INSERT INTO sellers(store_name,owner_name,email,phone,city,state,website,instagram,store_bio,seller_story,specialties,logo_url,banner_url,status,seller_level,rating,completed_sales,disputes,strikes,auction_override,access_code,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(store,owner,email,'','','','','',bio,story,spec,save_file(logo,'seller_logos'),save_file(banner,'seller_banners'),'Approved','Verified Seller',100,0,0,0,'Yes',code,now())); st.success('Seller store active.')
def marketplace():
    header(); st.header('Marketplace')
    st.write('Browse everything available on House Of Wax: independent seller inventory, House Of Wax Official items, branded merchandise, records, cassettes, CDs, posters, clothing, memorabilia, and culture goods.')
    if 'seller_id' in st.session_state: seller_profile(int(st.session_state['seller_id'])); return
    if 'product_id' in st.session_state: product_detail(int(st.session_state['product_id'])); return
    prods=df("SELECT * FROM products WHERE listing_status IN ('Active','Draft') ORDER BY created_at DESC")
    if prods.empty: st.info('No inventory yet. Use Test Setup or Seller Tools.'); return
    q=st.text_input('Search title, artist, barcode, catalog, category')
    if q:
        term=q.lower(); prods=prods[prods['artist'].fillna('').str.lower().str.contains(term)|prods['title'].fillna('').str.lower().str.contains(term)|prods['barcode'].fillna('').str.lower().str.contains(term)|prods['catalog_number'].fillna('').str.lower().str.contains(term)|prods['category'].fillna('').str.lower().str.contains(term)]
    cols=st.columns(3)
    for i,(_,p) in enumerate(prods.iterrows()):
        with cols[i%3]: product_card(p)
def seller_stores():
    header(); st.header('Seller stores')
    if 'seller_id' in st.session_state: seller_profile(int(st.session_state['seller_id'])); return
    sellers=table('sellers')
    if sellers.empty: st.info('No sellers yet.'); return
    for _,s in sellers.iterrows():
        with st.container(border=True):
            if safe(s['banner_url']): st.image(safe(s['banner_url']),use_container_width=True)
            st.subheader(safe(s['store_name'])); st.caption(f"{safe(s['seller_level'])} • Rating {s['rating']}% • Followers {followers(int(s['id']))}"); st.write(safe(s['store_bio']))
            if badges(int(s['id'])): st.info('Badges: '+badges(int(s['id'])))
            if st.button('Open public profile',key=f"openseller{int(s['id'])}"): st.session_state['seller_id']=int(s['id']); st.rerun()
def buyer_dashboard():
    header(); st.header('Buyer dashboard')
    mode=st.radio('Open buyer by',['Choose existing buyer','Create/open by email'],horizontal=True)
    if mode=='Choose existing buyer': bid=buyer_pick('buyerdb')
    else:
        email=st.text_input('Buyer email',value='buyer@test.com'); name=st.text_input('Buyer name',value='Test Buyer')
        if st.button('Create/open buyer'): st.session_state['buyer_id']=create_buyer(email,name)
        bid=st.session_state.get('buyer_id',ensure_buyer())
    b=get_buyer(bid); st.success(f"Loaded buyer: {safe(b['name'])} | {safe(b['email'])}")
    tabs=st.tabs(['Profile','Orders','Messages','Following','Leave seller feedback','Public feedback'])
    with tabs[0]:
        with st.form('bp'):
            name=st.text_input('Name',value=safe(b['name'])); email=st.text_input('Email',value=safe(b['email'])); bio=st.text_area('Bio',value=safe(b['bio'])); sub=st.form_submit_button('Save buyer profile')
        if sub: run('UPDATE buyers SET name=?,email=?,bio=? WHERE id=?',(name,email,bio,bid)); st.success('Saved.')
    with tabs[1]: st.dataframe(df('SELECT * FROM orders WHERE buyer_id=? ORDER BY created_at DESC',(bid,)),use_container_width=True)
    with tabs[2]: st.dataframe(df('SELECT * FROM messages WHERE buyer_id=? ORDER BY created_at DESC',(bid,)),use_container_width=True)
    with tabs[3]: st.dataframe(df('SELECT f.*,s.store_name,s.rating FROM seller_followers f LEFT JOIN sellers s ON f.seller_id=s.id WHERE f.buyer_id=?',(bid,)),use_container_width=True)
    with tabs[4]:
        orders=df("SELECT * FROM orders WHERE buyer_id=? AND status='Completed' ORDER BY created_at DESC",(bid,)); st.dataframe(orders,use_container_width=True)
        if not orders.empty:
            oid=st.selectbox('Completed order',orders['id'].tolist()); o=orders[orders['id']==oid].iloc[0]; rating=st.slider('Seller rating',1,5,5); comment=st.text_area('Public seller feedback')
            if st.button('Submit public seller feedback'): run("INSERT INTO feedback(order_id,reviewer_type,reviewer_id,reviewee_type,reviewee_id,rating,comment,public,created_at) VALUES(?,'Buyer',?,'Seller',?,?,?,'Yes',?)",(int(oid),bid,int(o['seller_id']),int(rating),comment,now())); update_rating('Seller',int(o['seller_id'])); st.success('Feedback posted.')
    with tabs[5]: buyer_profile_public(bid)

# ---------- V24 Barcode Lookup + Auto-Fill ----------
MUSIC_CATEGORIES=['Vinyl Records','CDs','Cassettes']
NON_MUSIC_PHOTO_REQUIRED=['Clothing','Music Memorabilia','Culture Goods','House Of Wax Merch','Official Drops','Slipmats & Accessories']

def is_music_category(category):
    return safe(category) in MUSIC_CATEGORIES

def normalize_barcode(code):
    return re.sub(r'[^0-9A-Za-z]', '', safe(code))

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

def render_best_match_card(best, key_prefix='main'):
    if not best:
        return
    st.markdown('### Recommended best match')
    with st.container(border=True):
        c1,c2=st.columns([1,2])
        with c1:
            if safe(best.get('image_url')):
                st.image(safe(best.get('image_url')),use_container_width=True)
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
            st.caption(f"Match score: {safe(best.get('_final_score')) or safe(best.get('_match_score'))}")
            if st.button('Use recommended match',key=f'use_recommended_match_{key_prefix}'):
                st.session_state['v24_autofill_listing']=best
                st.session_state['v24_autofill_barcode']=st.session_state.get(f'v24_lookup_barcode_clean_{key_prefix}','')
                try:
                    rid=create_or_update_how_release(st.session_state['v24_autofill_barcode'],best)
                    st.session_state['v25_release_id']=rid
                except Exception:
                    pass
                st.success('Recommended match loaded into listing draft.')


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
            st.dataframe(pd.DataFrame(st.session_state[f'source_health_results_{key_prefix}']),use_container_width=True)
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
    if code:
        queries.append(f'barcode:{code}')
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
    if code:
        queries.append(code)
    if artist and title:
        queries.append(f'{artist} {title}')
    elif artist:
        queries.append(artist)
    elif title:
        queries.append(title)
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

def score_release_match(result, artist='', title=''):
    artist=safe(artist).lower()
    title=safe(title).lower()
    hay=f"{safe(result.get('artist'))} {safe(result.get('title'))}".lower()
    score=0
    if artist:
        for part in artist.split():
            if part and part in hay:
                score+=10
    if title:
        for part in title.split():
            if part and part in hay:
                score+=12
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
    diagnostics.append({'Step':'Search terms','Status':f'Artist: {artist or "blank"} | Title: {title or "blank"} | Barcode: {code or "blank"}','Details':'This broad search is used when barcode-only lookup does not find a match.'})
    results=[]

    # Discogs broad search first for physical music culture/collector data.
    try:
        dres=lookup_discogs_broad_search(artist,title,code)
        if dres:
            diagnostics.append({'Step':'Discogs broad search','Status':f'{len(dres)} match(es)','Details':'Discogs returned release candidates. Works best when DISCOGS_TOKEN is connected.'})
            results.extend(dres)
        else:
            token_msg='connected' if discogs_token_status() else 'not connected'
            diagnostics.append({'Step':'Discogs broad search','Status':'No match','Details':f'Discogs returned no result. Discogs token status: {token_msg}.'})
    except Exception as e:
        diagnostics.append({'Step':'Discogs broad search','Status':'Error','Details':safe(e)})

    # Apple/iTunes album search is reliable for popular mainstream artists and gives good cover art.
    try:
        ares=lookup_itunes_text_search(artist,title,code)
        if ares:
            diagnostics.append({'Step':'Apple/iTunes album search','Status':f'{len(ares)} match(es)','Details':'Apple/iTunes returned album candidates and artwork. Good fallback for popular artists.'})
            results.extend(ares)
        else:
            diagnostics.append({'Step':'Apple/iTunes album search','Status':'No match','Details':'Apple/iTunes returned no album candidate for these terms.'})
    except Exception as e:
        diagnostics.append({'Step':'Apple/iTunes album search','Status':'Error','Details':safe(e)})

    # MusicBrainz broad search uses multiple query styles because strict Lucene queries can miss results.
    try:
        mbres=lookup_musicbrainz_broad_search(artist,title,code)
        if mbres:
            diagnostics.append({'Step':'MusicBrainz broad search','Status':f'{len(mbres)} match(es)','Details':'MusicBrainz returned release candidates using broad query attempts.'})
            results.extend(mbres)
        else:
            diagnostics.append({'Step':'MusicBrainz broad search','Status':'No match','Details':'MusicBrainz returned no result after broad query attempts.'})
    except Exception as e:
        diagnostics.append({'Step':'MusicBrainz broad search','Status':'Error','Details':safe(e)})

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

    # 1. House Of Wax internal release database
    try:
        internal=get_best_how_release(code)
        if internal:
            diagnostics.append({'Step':'House Of Wax release database','Status':'Match found','Details':'Using internal House Of Wax release record first.'})
            return [how_release_to_autofill(internal)], diagnostics
        diagnostics.append({'Step':'House Of Wax release database','Status':'No match','Details':'No internal House Of Wax release record exists for this barcode yet.'})
    except Exception as e:
        diagnostics.append({'Step':'House Of Wax release database','Status':'Error','Details':safe(e)})

    # 2. Local barcode cache
    try:
        cached=df("SELECT * FROM barcode_lookup_cache WHERE barcode=? ORDER BY id DESC LIMIT 10",(code,))
        if not cached.empty:
            results=[]
            for _,r in cached.iterrows():
                res={k:r.get(k,'') for k in ['source','external_id','artist','title','format','label','release_year','country','genre','style','catalog_number','image_url','external_url','raw_summary']}
                results.append(res)
                try:
                    create_or_update_how_release(code,res)
                except Exception:
                    pass
            diagnostics.append({'Step':'Barcode lookup cache','Status':f'{len(results)} cached match(es)','Details':'Using prior lookup results saved by House Of Wax.'})
            return results, diagnostics
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
                return discogs_results, diagnostics
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
            return mb_results, diagnostics
        diagnostics.append({'Step':'MusicBrainz','Status':'No match','Details':'MusicBrainz responded, but did not return a release for this barcode.'})
    except Exception as e:
        diagnostics.append({'Step':'MusicBrainz','Status':'Error','Details':safe(e)})

    diagnostics.append({'Step':'Final result','Status':'Manual entry needed','Details':'No source returned a match. Seller can still enter the item manually and House Of Wax can build the database over time.'})
    return [], diagnostics

def show_barcode_diagnostics(diagnostics):
    if diagnostics:
        st.markdown('### Lookup diagnostics')
        st.dataframe(pd.DataFrame(diagnostics),use_container_width=True)
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
        return [how_release_to_autofill(internal)]
    cached=df("SELECT * FROM barcode_lookup_cache WHERE barcode=? ORDER BY id DESC LIMIT 10",(barcode,))
    results=[]
    if not cached.empty:
        for _,r in cached.iterrows():
            res={k:r.get(k,'') for k in ['source','external_id','artist','title','format','label','release_year','country','genre','style','catalog_number','image_url','external_url','raw_summary']}
            results.append(res)
            try:
                create_or_update_how_release(barcode,res)
            except Exception:
                pass
        return results
    results=lookup_discogs_barcode(barcode)
    if not results:
        results=lookup_musicbrainz_barcode(barcode)
    for res in results:
        try:
            cache_lookup_result(barcode,res)
            create_or_update_how_release(barcode,res)
        except Exception:
            pass
    return results

def render_barcode_lookup_widget(key_prefix='main'):
    seed_listing_media_policy()
    st.markdown('### Barcode / UPC lookup')
    st.write('For records, CDs, and cassettes, scan or type the barcode. House Of Wax checks its own release database first, then outside sources for release information and cover art. For shirts, dolls, memorabilia, merch, and accessories, sellers should use a photo of the exact item or an official product image.')
    render_source_health_panel(key_prefix)
    c1,c2=st.columns([2,1])
    barcode=c1.text_input('Scan or enter barcode / UPC',key=f'v24_lookup_barcode_{key_prefix}',placeholder='Click here, then scan with USB/Bluetooth scanner or type manually')
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
        else:
            with st.spinner('Looking up barcode...'):
                matches,diagnostics=lookup_barcode_with_diagnostics(code)
            st.session_state[f'v25_lookup_diagnostics_{key_prefix}']=diagnostics
            if matches:
                st.session_state[f'v24_barcode_matches_{key_prefix}']=matches
                st.session_state[f'v24_lookup_barcode_clean_{key_prefix}']=code
                st.success(f'Found {len(matches)} possible match(es). Choose one below to auto-fill the listing draft.')
            else:
                st.warning('No lookup match found yet. Review diagnostics below, then manually enter the product if needed.')

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

    render_best_match_card(st.session_state.get(f'v25_best_match_{key_prefix}'),key_prefix)

    show_barcode_diagnostics(st.session_state.get(f'v25_lookup_diagnostics_{key_prefix}',[]))
    current_artist=st.session_state.get(f'v25_search_artist_{key_prefix}','')
    current_title=st.session_state.get(f'v25_search_title_{key_prefix}','')
    show_universal_search_links(current_artist,current_title,barcode)
    manual_release_seed_form(current_artist,current_title,barcode,key_prefix)



    matches=st.session_state.get(f'v24_barcode_matches_{key_prefix}',[])
    if matches:
        labels=[f"{i+1}. {safe(m.get('artist'))} - {safe(m.get('title'))} ({safe(m.get('source'))}, {safe(m.get('release_year'))})" for i,m in enumerate(matches)]
        pick=st.selectbox('Possible barcode matches',labels,key=f'v24_match_select_{key_prefix}')
        idx=int(pick.split('.',1)[0])-1
        selected=matches[idx]
        colA,colB=st.columns([1,2])
        with colA:
            if safe(selected.get('image_url')):
                st.image(safe(selected.get('image_url')),use_container_width=True)
            else:
                st.info('No image returned.')
        with colB:
            st.write(f"**Artist:** {safe(selected.get('artist'))}")
            st.write(f"**Title:** {safe(selected.get('title'))}")
            st.write(f"**Format:** {safe(selected.get('format'))}")
            st.write(f"**Label:** {safe(selected.get('label'))}")
            st.write(f"**Year:** {safe(selected.get('release_year'))}")
            st.write(f"**Source:** {safe(selected.get('source'))}")
            if safe(selected.get('external_url')):
                st.write(f"External release URL: {safe(selected.get('external_url'))}")
        if st.button('Use this match to auto-fill listing draft',key=f'v24_use_match_{key_prefix}'):
            st.session_state['v24_autofill_listing']=selected
            st.session_state['v24_autofill_barcode']=st.session_state.get(f'v24_lookup_barcode_clean_{key_prefix}',normalize_barcode(barcode))
            try:
                rid=create_or_update_how_release(st.session_state['v24_autofill_barcode'],selected)
                st.session_state['v25_release_id']=rid
            except Exception:
                pass
            st.success('Listing draft filled and saved to the House Of Wax release database. Scroll to the Add Product form and review before saving.')

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
    st.dataframe(releases,use_container_width=True)
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
        st.dataframe(sources,use_container_width=True)
        st.markdown('### Seller corrections')
        st.dataframe(corrections,use_container_width=True)


def upload_product(sid,key):
    defaults=v24_listing_defaults()
    st.markdown('### Add / upload product')
    st.write('Use the barcode lookup first for records, CDs, and cassettes. Then review these fields before saving.')
    with st.form(key):
        c1,c2,c3=st.columns(3)
        sku=c1.text_input('SKU')
        barcode=c2.text_input('Barcode / UPC / EAN',value=defaults.get('barcode',''))
        catalog=c3.text_input('Catalog number',value=defaults.get('catalog_number',''))
        matrix=st.text_input('Matrix / runout')

        c4,c5,c6=st.columns(3)
        category=c4.selectbox('Category',['Vinyl Records','CDs','Cassettes','Clothing','Music Memorabilia','Culture Goods','House Of Wax Merch','Official Drops','Slipmats & Accessories'])
        artist=c5.text_input('Artist / Brand',value=defaults.get('artist',''))
        title=c6.text_input('Title / Product',value=defaults.get('title',''))

        c7,c8,c9=st.columns(3)
        fmt_default=defaults.get('format','') or ('Vinyl' if category=='Vinyl Records' else '')
        fmt=c7.text_input('Format',value=fmt_default)
        label=c8.text_input('Label / Brand',value=defaults.get('label',''))
        year=c9.text_input('Release year',value=defaults.get('release_year',''))

        genre=st.text_input('Genre / style',value=defaults.get('genre',''))
        mg=st.selectbox('Media/product grade',['Mint','Near Mint','VG+','VG','Good','Used','New','N/A'])
        sg=st.selectbox('Sleeve/packaging grade',['Mint','Near Mint','VG+','VG','Good','Used','New','N/A'])
        notes=st.text_area('Condition notes')
        desc=st.text_area('Description')

        c10,c11,c12=st.columns(3)
        price=c10.number_input('Price',min_value=0.0,step=.01)
        qty=c11.number_input('Quantity',min_value=1,value=1)
        ship=c12.number_input('Shipping price',min_value=0.0,step=.01)

        st.markdown('### Product image')
        if is_music_category(category):
            st.info('Music item: the barcode/release image is used by default when available. You can still upload an actual item photo if you want condition proof.')
        else:
            st.warning('Non-music item: upload or enter a real/official image for this exact item.')
        img=st.file_uploader('Optional seller photo / exact item image',type=['png','jpg','jpeg','webp'])
        imgurl=st.text_input('Image URL',value=defaults.get('image_url',''))
        external_release_url=st.text_input('External release URL',value=defaults.get('external_url',''))
        sub=st.form_submit_button('Upload product')
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
    if sub:
        saved_image=save_file(img,'product_images')
        image=saved_image or imgurl
        description=desc or f'{artist} — {title}. {notes}'
        run("""INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(sid,sku,barcode,catalog,matrix,category,artist,title,fmt,label,year,genre,mg,sg,notes,description,float(price),int(qty),float(ship),image,'','',external_release_url,'Active','Fixed Price',now(),now()))
        if is_music_category(category) and imgurl and not saved_image:
            st.success('Product uploaded using barcode/release image.')
        elif not is_music_category(category) and not image:
            st.warning('Product uploaded, but this non-music item should have an exact item or official product image before going public.')
        else:
            st.success('Product uploaded and public.')


def seller_dashboard():
    header(); st.header('Seller dashboard')
    mode=st.radio('Open seller by',['Choose existing seller','Email + access code'],horizontal=True)
    if mode=='Choose existing seller': sid=seller_pick('sellerdb')
    else:
        email=st.text_input('Seller email',value='seller@test.com'); code=st.text_input('Access code',value='test123',type='password'); r=df('SELECT * FROM sellers WHERE lower(email)=lower(?) AND access_code=?',(email.strip(),code)); sid=ensure_seller() if r.empty else int(r.iloc[0]['id'])
    s=get_seller(sid); st.success(f"Loaded seller: {safe(s['store_name'])} | {safe(s['email'])}")
    tabs=st.tabs(['Store profile','Policies','Upload product','Barcode scanner','Bulk import','Gallery','Listings','Orders','Messages','Announcements','Events/drops','Badges','Leave buyer feedback','Public feedback'])
    with tabs[0]:
        with st.form('sp'):
            store=st.text_input('Store name',value=safe(s['store_name'])); bio=st.text_area('Store bio',value=safe(s['store_bio'])); story=st.text_area('Seller story',value=safe(s['seller_story'])); spec=st.text_area('Specialties',value=safe(s['specialties'])); logo=st.file_uploader('Logo',type=['png','jpg','jpeg','webp']); banner=st.file_uploader('Banner',type=['png','jpg','jpeg','webp']); logo_url=st.text_input('Logo URL/path',value=safe(s['logo_url'])); banner_url=st.text_input('Banner URL/path',value=safe(s['banner_url'])); sub=st.form_submit_button('Save profile')
        if sub: run("UPDATE sellers SET store_name=?,store_bio=?,seller_story=?,specialties=?,logo_url=?,banner_url=?,status='Approved',seller_level='Verified Seller',auction_override='Yes' WHERE id=?",(store,bio,story,spec,save_file(logo,'seller_logos') or logo_url,save_file(banner,'seller_banners') or banner_url,sid)); st.success('Saved.')
    with tabs[1]:
        p=df('SELECT * FROM seller_policies WHERE seller_id=?',(sid,)); pol=p.iloc[0] if not p.empty else {}
        with st.form('policy'):
            shipping=st.text_area('Shipping policy',value=safe(pol.get('shipping_policy') if len(pol) else 'Ships within 3 business days.')); returns=st.text_area('Return policy',value=safe(pol.get('return_policy') if len(pol) else 'No buyer remorse returns unless seller approves.')); grading=st.text_area('Grading policy',value=safe(pol.get('grading_policy') if len(pol) else 'Collector grading standards.')); sub=st.form_submit_button('Save policies')
        if sub: run('INSERT OR REPLACE INTO seller_policies(seller_id,shipping_policy,return_policy,grading_policy) VALUES(?,?,?,?)',(sid,shipping,returns,grading)); st.success('Policies saved.')
    with tabs[2]:
        render_barcode_lookup_widget('upload_product')
        upload_product(sid,'normal_upload')
    with tabs[3]:
        st.subheader('Barcode scanner / inventory quick add')
        st.info('Click into the barcode field and scan with a USB/Bluetooth scanner, phone keyboard scanner, or type/paste the barcode.')
        render_barcode_lookup_widget('barcode_quick_add')
        upload_product(sid,'barcode_quick_add')
    with tabs[4]:
        csv=st.file_uploader('Upload CSV',type=['csv']); st.caption('Supports barcode,catalog_number,matrix_runout,artist,title,format,label,release_year,genre,price,quantity,image_url')
        if csv is not None:
            data=pd.read_csv(csv); st.dataframe(data,use_container_width=True)
            if st.button('Import CSV products'):
                n=0
                for _,r in data.iterrows(): run('''INSERT INTO products(seller_id,sku,barcode,catalog_number,matrix_runout,category,artist,title,format,label,release_year,genre,media_grade,sleeve_grade,condition_notes,description,price,quantity,shipping_price,image_url,video_url,audio_url,external_release_url,listing_status,listing_type,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(sid,safe(r.get('sku')),safe(r.get('barcode')),safe(r.get('catalog_number')),safe(r.get('matrix_runout')),safe(r.get('category'),'Vinyl Records'),safe(r.get('artist')),safe(r.get('title')),safe(r.get('format'),'Vinyl'),safe(r.get('label')),safe(r.get('release_year')),safe(r.get('genre')),safe(r.get('media_grade')),safe(r.get('sleeve_grade')),safe(r.get('condition_notes')),safe(r.get('description')),float(r.get('price',0) or 0),int(r.get('quantity',1) or 1),float(r.get('shipping_price',0) or 0),safe(r.get('image_url')),safe(r.get('video_url')),safe(r.get('audio_url')),safe(r.get('external_release_url')),safe(r.get('listing_status'),'Active'),'Fixed Price',now(),now())); n+=1
                st.success(f'Imported {n}.')
    with tabs[5]:
        prods=df('SELECT * FROM products WHERE seller_id=?',(sid,)); st.dataframe(prods,use_container_width=True)
        if not prods.empty:
            pid=st.selectbox('Product for gallery',prods['id'].tolist()); img=st.file_uploader('Gallery image',type=['png','jpg','jpeg','webp']); url=st.text_input('Or image URL'); cap=st.text_input('Caption')
            if st.button('Add gallery image'):
                image=save_file(img,'product_gallery') or url
                if image: run('INSERT INTO product_gallery(product_id,image_url,caption,created_at) VALUES(?,?,?,?)',(int(pid),image,cap,now())); st.success('Gallery image added.')
    with tabs[6]:
        prods=df('SELECT * FROM products WHERE seller_id=? ORDER BY created_at DESC',(sid,)); st.dataframe(prods,use_container_width=True)
        if not prods.empty:
            pid=st.selectbox('Listing ID',prods['id'].tolist()); status=st.selectbox('Status',['Active','Draft','Sold','Removed'])
            if st.button('Update listing'): run('UPDATE products SET listing_status=?,updated_at=? WHERE id=? AND seller_id=?',(status,now(),int(pid),sid)); st.success('Updated.')
    with tabs[7]:
        orders=df('SELECT o.*,b.name buyer_name,b.email buyer_email,b.rating buyer_rating FROM orders o LEFT JOIN buyers b ON o.buyer_id=b.id WHERE o.seller_id=? ORDER BY o.created_at DESC',(sid,)); st.dataframe(orders,use_container_width=True)
        if not orders.empty:
            bids=orders['buyer_id'].dropna().astype(int).unique().tolist(); bp=st.selectbox('View buyer public trust profile',bids); buyer_profile_public(int(bp)); oid=st.selectbox('Order ID',orders['id'].tolist()); status=st.selectbox('Order status',['New','Contacted','Invoice Sent','Paid','Shipped','Completed','Cancelled','Disputed'])
            if st.button('Update order'):
                run('UPDATE orders SET status=?,updated_at=? WHERE id=? AND seller_id=?',(status,now(),int(oid),sid))
                if status=='Completed': row=orders[orders['id']==oid].iloc[0]; run('UPDATE sellers SET completed_sales=completed_sales+1 WHERE id=?',(sid,)); run('UPDATE buyers SET completed_purchases=completed_purchases+1 WHERE id=?',(int(row['buyer_id']),))
                st.success('Order updated.')
    with tabs[8]: st.dataframe(df('SELECT * FROM messages WHERE seller_id=? ORDER BY created_at DESC',(sid,)),use_container_width=True)
    with tabs[9]:
        with st.form('ann'): title=st.text_input('Announcement title'); body=st.text_area('Announcement body'); sub=st.form_submit_button('Post announcement')
        if sub: run("INSERT INTO store_announcements(seller_id,title,body,status,created_at) VALUES(?,?,?,'Active',?)",(sid,title,body,now())); st.success('Posted.')
        st.dataframe(df('SELECT * FROM store_announcements WHERE seller_id=?',(sid,)),use_container_width=True)
    with tabs[10]:
        with st.form('ev'): title=st.text_input('Drop/event title'); typ=st.selectbox('Type',['Record Drop','Auction Drop','Sale','Live Event','Other']); date=st.text_input('Date/time'); desc=st.text_area('Description'); sub=st.form_submit_button('Save event')
        if sub: run("INSERT INTO seller_events(seller_id,event_title,event_type,event_date,description,status,created_at) VALUES(?,?,?,?,?,'Active',?)",(sid,title,typ,date,desc,now())); st.success('Saved.')
    with tabs[11]: st.write(badges(sid) or 'No badges yet.'); st.dataframe(df('SELECT * FROM seller_badges WHERE seller_id=?',(sid,)),use_container_width=True)
    with tabs[12]:
        orders=df("SELECT * FROM orders WHERE seller_id=? AND status='Completed'",(sid,)); st.dataframe(orders,use_container_width=True)
        if not orders.empty:
            oid=st.selectbox('Completed order',orders['id'].tolist(),key='sellerfb'); o=orders[orders['id']==oid].iloc[0]; rating=st.slider('Buyer rating',1,5,5); comment=st.text_area('Public buyer feedback')
            if st.button('Submit public buyer feedback'): run("INSERT INTO feedback(order_id,reviewer_type,reviewer_id,reviewee_type,reviewee_id,rating,comment,public,created_at) VALUES(?,'Seller',?,'Buyer',?,?,?,'Yes',?)",(int(oid),sid,int(o['buyer_id']),int(rating),comment,now())); update_rating('Buyer',int(o['buyer_id'])); st.success('Feedback posted.')
    with tabs[13]: feedback_public('Seller',sid)
def auctions():
    header(); st.header('Auctions'); sid=seller_pick('auction_seller'); prods=df("SELECT * FROM products WHERE seller_id=? AND listing_status IN ('Active','Draft')",(sid,))
    if not prods.empty:
        with st.form('auction'): pid=st.selectbox('Product',prods['id'].tolist()); title=st.text_input('Auction title'); start=st.number_input('Starting bid',min_value=0.0,step=1.0); end=st.text_input('End time'); sub=st.form_submit_button('Create live auction')
        if sub: run("INSERT INTO auctions(product_id,seller_id,auction_title,starting_bid,reserve_price,buy_now_price,bid_increment,start_time,end_time,status,notes,created_at) VALUES(?,?,?,?,?,?,1,?,?,'Live','',?)",(int(pid),sid,title,float(start),0,0,now(),end,now())); st.success('Auction created.')
    st.dataframe(table('auctions'),use_container_width=True)
def culture():
    header(); st.header('Knowledge Hub'); posts=df("SELECT * FROM culture_posts WHERE status='Published' ORDER BY created_at DESC")
    if posts.empty: st.info('No culture posts yet.')
    for _,p in posts.iterrows():
        with st.container(border=True):
            if safe(p['image_url']): st.image(safe(p['image_url']),use_container_width=True)
            st.subheader(safe(p['title'])); st.caption(f"{safe(p['category'])} • {safe(p['author'])}"); st.write(safe(p['body']))
def admin():
    header(); st.header('Admin')
    if ADMIN_PASSWORD:
        pwd=st.text_input('Admin password',type='password')
        if not st.button('Enter admin'): return
        if pwd!=ADMIN_PASSWORD: st.error('Wrong password.'); return
    else: st.info('No admin password set. Testing build allows admin access.')
    tabs=st.tabs(['Overview','Sellers','Buyers','Community tools','Reports','Cleanup'])
    with tabs[0]:
        if st.button('Create/repair House Of Wax Official seller'):
            sid=ensure_house_of_wax_official(); st.success(f'House Of Wax Official seller ready. Seller ID {sid}')
        c1,c2,c3,c4=st.columns(4); c1.metric('Buyers',len(table('buyers'))); c2.metric('Sellers',len(table('sellers'))); c3.metric('Products',len(table('products'))); c4.metric('Orders',len(table('orders')))
    with tabs[1]: st.dataframe(table('sellers'),use_container_width=True)
    with tabs[2]: st.dataframe(table('buyers'),use_container_width=True)
    with tabs[3]:
        sid=seller_pick('adminseller'); badge=st.text_input('Badge',placeholder='Soul Specialist, Jazz Dealer, Verified Seller'); typ=st.selectbox('Badge type',['Community','Specialty','Performance','Verified'])
        if st.button('Add badge'): run("INSERT INTO seller_badges(seller_id,badge_name,badge_type,active,created_at) VALUES(?,?,?,'Yes',?)",(sid,badge,typ,now())); st.success('Badge added.')
        if st.button('Create seller spotlight culture post'):
            s=get_seller(sid); run("INSERT INTO culture_posts(title,category,author,body,image_url,status,created_at) VALUES(?,'Seller Spotlight','House Of Wax',?,?,'Published',?)",(f"Seller Spotlight: {safe(s['store_name'])}",safe(s['seller_story'],safe(s['store_bio'])),safe(s['banner_url']) or safe(s['logo_url']),now())); st.success('Spotlight created.')
        st.subheader('Messages'); st.dataframe(table('messages'),use_container_width=True); st.subheader('Feedback'); st.dataframe(table('feedback'),use_container_width=True)
    with tabs[4]:
        rep=st.selectbox('Report',['buyers','sellers','products','product_gallery','orders','feedback','messages','seller_followers','seller_badges','store_announcements','seller_events','auctions','bids','listing_flags','culture_posts','knowledge_posts','glossary_terms','content_drafts','content_calendar']); data=table(rep); st.dataframe(data,use_container_width=True); st.download_button('Download CSV',data.to_csv(index=False),file_name=f'{rep}.csv')
    with tabs[5]:
        t=st.selectbox('Table',['buyers','sellers','products','product_gallery','orders','feedback','messages','seller_followers','seller_badges','store_announcements','seller_events','auctions','bids','listing_flags','culture_posts','knowledge_posts','glossary_terms','content_drafts','content_calendar']); data=table(t); st.dataframe(data,use_container_width=True)
        if not data.empty:
            rid=st.selectbox('Row ID',data['id'].tolist()); confirm=st.checkbox('Confirm delete')
            if st.button('Delete row') and confirm: run(f'DELETE FROM {t} WHERE id=?',(int(rid),)); st.success('Deleted.')



# ---------- V23 Launch Prep + Public Pages ----------
def about_house_of_wax():
    header()
    st.header('About House Of Wax')
    st.write('House Of Wax is a music marketplace and culture platform built for collectors, sellers, and people who want to understand music culture the right way.')
    st.markdown("""
    <div class="how-callout">
    House Of Wax is not just a place to list items. It is a marketplace with education, culture, trust standards, and community built into the experience.
    </div>
    """, unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1:
        st.subheader('Marketplace')
        st.write('Browse records, CDs, cassettes, memorabilia, clothing, branded merch, official drops, and culture goods from approved sellers.')
    with c2:
        st.subheader('Knowledge Hub')
        st.write('Learn about grading, barcodes, matrix/runouts, formats, collecting basics, music history, scenes, genres, and marketplace trust.')
    with c3:
        st.subheader('Community')
        st.write('House Of Wax is built around transparency, public reputation, education, and respect for music culture.')

def trust_safety():
    header()
    st.header('Trust & Safety')
    st.write('House Of Wax is designed to make marketplace trust visible and easier to understand.')
    st.markdown('### What House Of Wax believes')
    st.write('- Condition transparency matters.')
    st.write('- Buyer and seller feedback should help the community make better decisions.')
    st.write('- Sellers should accurately describe items, ship responsibly, and communicate clearly.')
    st.write('- Buyers should pay promptly, ask questions before purchasing, and respect seller policies.')
    st.write('- Education reduces disputes and builds a stronger marketplace.')
    st.markdown('### Trust tools being built')
    brand_badges(['Public feedback','Seller approval','Buyer history','Condition education','Marketplace standards'])
    st.info('This prototype is not yet a production payment or dispute platform. Policies should be reviewed before public launch.')

def seller_standards():
    header()
    st.header('Seller Standards')
    st.write('Sellers on House Of Wax should help build a trusted marketplace and music culture community.')
    st.markdown('### Sellers are expected to')
    st.write('- Describe items honestly.')
    st.write('- Use clear condition notes.')
    st.write('- Add barcode, catalog, matrix/runout, label, format, and release details when available.')
    st.write('- Upload strong photos.')
    st.write('- Price clearly.')
    st.write('- Respond to buyers professionally.')
    st.write('- Ship items safely and on time.')
    st.write('- Respect House Of Wax trust standards.')
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

def contact_newsletter():
    header()
    st.header('Contact / Newsletter')
    st.write('Join the House Of Wax list for collecting tips, culture stories, Knowledge Hub updates, marketplace announcements, and future drops.')
    with st.form('public_newsletter_signup'):
        name=st.text_input('Name')
        email=st.text_input('Email')
        interest=st.selectbox('What are you most interested in?',['Records','Music culture','Marketplace updates','Selling on House Of Wax','House Of Wax merch','General updates'])
        submitted=st.form_submit_button('Join the list')
        if submitted:
            if email:
                try:
                    run("INSERT INTO newsletter_signups(name,email,interest,created_at) VALUES(?,?,?,?)",(name,email,interest,now()))
                    st.success('You are on the House Of Wax list.')
                except Exception as e:
                    st.error(f'Newsletter signup table is not ready yet: {e}')
            else:
                st.error('Add an email address.')
    st.markdown('### Contact')
    st.write('For now, use this page as the contact placeholder. Before launch, connect this to a real House Of Wax email or contact form.')

def launch_checklist():
    header()
    st.header('Launch Checklist')
    st.write('Use this checklist before sharing House Of Wax more widely.')
    checklist=[
        'Confirm public navigation works',
        'Confirm Marketplace has clean sample or real listings',
        'Confirm Knowledge Hub has strong starter content',
        'Confirm Sell on House Of Wax explains seller onboarding',
        'Confirm My House of Wax works for buyer/seller/admin tools',
        'Hide or restrict Test Setup before public launch',
        'Review seller standards',
        'Review buyer expectations',
        'Review trust and safety language',
        'Set Streamlit subdomain',
        'Prepare official House Of Wax email/contact',
        'Prepare logo and brand images',
        'Prepare first 10 Knowledge Hub posts',
        'Prepare first newsletter signup campaign',
        'Review business plan and budget'
    ]
    for item in checklist:
        st.checkbox(item,key=f"launch_check_{item}")
    st.info('This checklist is saved only in the current Streamlit session. Production launch tracking should later be stored in the database.')



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
    render_best_match_card(st.session_state.get('standalone_best_match'),'standalone_diag')

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
                    st.image(safe(m.get('image_url')),width=160)
                st.write(safe(m.get('external_url')))


def my_house_of_wax():
    header()
    st.header('My House of Wax')
    st.write('Your branded account area for buying, selling, messages, feedback, content tools, admin tools, and testing tools.')
    st.info('For a cleaner public site, dashboards live here instead of being spread across the main navigation.')

    workspace_options=['Buyer Account','Seller Tools']
    if testing_mode:
        workspace_options += ['Content Admin','Admin','Test Setup','Auctions','Seller Stores','Release Database','Barcode Diagnostics','Launch Checklist']
    else:
        workspace_options += ['Content Admin']
    section=st.radio('Choose your workspace',workspace_options)

    if section=='Buyer Account':
        buyer_dashboard()
    elif section=='Seller Tools':
        seller_dashboard()
    elif section=='Content Admin':
        content_admin()
    elif section=='Admin':
        admin()
    elif section=='Test Setup':
        test_setup()
    elif section=='Auctions':
        auctions()
    elif section=='Seller Stores':
        seller_stores()
    elif section=='Release Database':
        release_database_admin()
    elif section=='Barcode Diagnostics':
        barcode_diagnostics_page()
    elif section=='Launch Checklist':
        launch_checklist()



def app_mode():
    # Public mode cleans the main site; testing mode exposes internal prototype tools.
    return st.sidebar.toggle('Testing mode', value=False, help='Turn on to show prototype/admin/testing tools inside My House of Wax.')


testing_mode=app_mode()
st.sidebar.caption('Public: Home, Marketplace, Knowledge Hub, Sell on House Of Wax. Accounts/tools: My House of Wax.')
menu=st.sidebar.radio('House Of Wax',['Home','Marketplace','Knowledge Hub','Sell on House Of Wax','About','Trust & Safety','Contact / Newsletter','My House of Wax'])
if menu=='Home': home()
elif menu=='Marketplace': marketplace()
elif menu=='Knowledge Hub': knowledge_hub()
elif menu=='Sell on House Of Wax': register()
elif menu=='About': about_house_of_wax()
elif menu=='Trust & Safety': trust_safety()
elif menu=='Contact / Newsletter': contact_newsletter()
elif menu=='My House of Wax': my_house_of_wax()

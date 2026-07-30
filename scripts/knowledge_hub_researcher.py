"""
Daily Knowledge Hub research job for House Of Wax.

Runs outside the Streamlit app (via a GitHub Actions cron job -- Streamlit
Community Cloud has no scheduler of its own). Uses Claude with live web
search to research one new, currently-relevant vinyl/music-collecting/music-
culture topic not already covered, and writes it into the same Supabase
`knowledge_posts` table the Knowledge Hub reads from -- as status='Draft',
source_type='AI Research', never published automatically. A human reviews
and publishes it from the "AI Research Queue" tab in Content Admin.

Required environment variables (set as GitHub Actions secrets, never
committed): ANTHROPIC_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY.
The service role key bypasses Row Level Security -- knowledge_posts writes
are otherwise restricted to real admin accounts (see
supabase_core_policies.sql: "admin manage knowledge posts"), so a plain
anon key cannot insert here. Treat this key as a secret on par with a
database password: GitHub Actions secret only, never in the repo, never in
Streamlit secrets (the app itself has no need for it).

Run locally to test:
    ANTHROPIC_API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... \
        python scripts/knowledge_hub_researcher.py
"""
import json
import os
import sys
from datetime import datetime, timezone

import anthropic
import requests

# Keep in sync with KNOWLEDGE_CATEGORIES in app.py -- duplicated here
# because app.py runs setup() at import time (Streamlit secrets, DB
# connections) and isn't safely importable from a bare script.
# tests/test_smoke.py::test_knowledge_categories_stay_in_sync_with_researcher_script
# guards against these two lists drifting apart.
KNOWLEDGE_CATEGORIES = [
    'Record Collecting 101',
    'Vinyl Grading School',
    'Barcode, Catalog & Matrix Guides',
    'Spotting Bootlegs and Reissues',
    'How to Buy Safely',
    'Care, Storage & Cleaning',
    'Genre Education',
    'Music History & Culture',
    'House Of Wax Trust Standards',
    'Marketplace Education',
    'Trending Now: Style & Sound',
]

# Founder: steer the audience toward trending styles, new artists, and
# music/entertainment culture -- but a topic that's just one option among
# 11 categories could go weeks without the model picking it on its own.
# Force it onto a predictable cadence instead.
TRENDING_CATEGORY = 'Trending Now: Style & Sound'
TRENDING_DAY_INTERVAL = 3


def is_trending_day():
    # GITHUB_EVENT_NAME is a default GitHub Actions env var, set on every
    # run with no workflow YAML changes needed (this repo's push credential
    # lacks the `workflow` scope needed to edit .github/workflows/*). A
    # manual workflow_dispatch trigger is almost always someone wanting to
    # see a trending article right now, not waiting on the 3-day cadence.
    if os.environ.get('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        return True
    return datetime.now(timezone.utc).timetuple().tm_yday % TRENDING_DAY_INTERVAL == 0


MODEL = 'claude-opus-4-8'


def env(name):
    value = os.environ.get(name, '').strip()
    if not value:
        print(f'[knowledge_hub_researcher] missing required environment variable: {name}', file=sys.stderr)
        sys.exit(1)
    return value


def fetch_existing_titles(supabase_url, service_key):
    resp = requests.get(
        f'{supabase_url}/rest/v1/knowledge_posts',
        headers={'apikey': service_key, 'Authorization': f'Bearer {service_key}'},
        params={'select': 'title,category', 'order': 'created_at.desc', 'limit': '300'},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def extract_json_object(text):
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError(f'No JSON object found in model output: {text[:500]!r}')
    return json.loads(text[start:end + 1])


def extract_sources(response):
    # Citations on a text block only exist when the model cites a span of
    # prose -- but both research_article() and fact_check_article() require
    # a FINAL message that is ONLY a raw JSON object, which has nowhere for
    # inline citation markup to attach, even when real web searches
    # happened. Also pull source URLs directly from the web_search_tool_
    # result blocks (the actual search results Claude received) so real
    # searches still get credited.
    sources = []
    seen = set()
    for block in response.content:
        if block.type == 'text':
            for c in (getattr(block, 'citations', None) or []):
                url = getattr(c, 'url', None)
                if url and url not in seen:
                    seen.add(url)
                    sources.append((getattr(c, 'title', None) or url, url))
        elif block.type == 'web_search_tool_result':
            for r in (getattr(block, 'content', None) or []):
                url = getattr(r, 'url', None)
                if url and url not in seen:
                    seen.add(url)
                    sources.append((getattr(r, 'title', None) or url, url))
    return sources


def research_article(client, existing_titles, forced_category=None):
    existing_list = '\n'.join(f"- {t['title']} ({t.get('category', '')})" for t in existing_titles) or '(none yet)'

    if forced_category:
        topic_instruction = (
            f'Your job each run: pick exactly ONE new article topic that is not a near-duplicate of an already-'
            f'published or already-queued title (list given below). Your topic for today MUST be in this '
            f'category: {forced_category}. Do not pick a different category today, even if another one seems '
            f'like a better fit for what you find while researching.'
        )
    else:
        topic_instruction = (
            'Your job each run: pick exactly ONE new article topic that is not a near-duplicate of an already-'
            'published or already-queued title (list given below), grounded in one of these categories:\n'
            + '\n'.join(f'- {c}' for c in KNOWLEDGE_CATEGORIES)
        )

    system_prompt = (
        'You are the research and editorial voice of House Of Wax, a marketplace and education platform for '
        'vinyl records and music collectibles. The Knowledge Hub is the cornerstone of the platform -- it is '
        'introduced to visitors as "written by House Of Wax and never sponsored by a seller." Readers trust it '
        'to be accurate. A wrong fact under that byline costs more than a slow week of content, so verify real '
        'claims with web search rather than relying on memory alone, and never invent a source, statistic, or '
        'quote.\n\n'
        + topic_instruction + '\n\n'
        f'One of the categories, "{TRENDING_CATEGORY}," is different from the rest: it must be about something '
        'genuinely current -- a breakout artist, a genre revival, or a fashion/streetwear trend intersecting '
        'with music culture right now (this week or month) -- not a general evergreen topic dressed up as news. '
        'Use web search to confirm it is actually current, not something from years ago being treated as new. '
        'Always close by connecting it back to what it means for collectors: which era, genre, artist catalog, '
        'or pressing style is suddenly worth digging for because of this trend.\n\n'
        'Favor topics where live web search actually adds value: current reissue news, an anniversary worth '
        'marking this month, a genre or scene deep-dive, a real grading/authentication question collectors '
        'ask, pressing/matrix trivia, care and storage, or buyer/seller trust standards. Use web search to '
        'confirm specific facts (dates, pressing plants, chart positions, label names) before stating them -- '
        'do not guess. Write in a knowledgeable, collector-to-collector tone: direct, useful, never breathless '
        'hype, never sponsored-sounding.\n\n'
        'Voice: write like someone who has actually spent years digging through crates, not a content farm. '
        'Zero corporate hedge-speak ("we strive to," "our goal is to," "elevate your collection"). Real genre '
        'and culture vocabulary (breaks, deep cuts, first pressing, the digger mentality) is welcome when it '
        'fits naturally -- but never force slang in just to sound current. Forced slang reads as costume, not '
        'culture, and undermines the credibility this Knowledge Hub is built on with people who actually live '
        'this. Earn the voice with accuracy and specificity, not vocabulary.\n\n'
        'Article structure, matching the existing Knowledge Hub schema exactly:\n'
        '- summary: a tight 1-3 sentence "quick answer" a skimming reader can get value from immediately.\n'
        '- body: the full guide, several paragraphs, plain language, genuinely useful and specific -- not '
        'generic filler.\n'
        '- house_tip: one concrete, practical closing tip in House Of Wax\'s voice.\n\n'
        'When you are done researching, your FINAL message must be ONLY a single JSON object, no markdown code '
        'fences, no other prose before or after it, with exactly these keys: title, category (must exactly '
        'match one of the categories listed above), audience (one of: Beginners, Collectors, Buyers, Sellers, '
        'Everyone), level (one of: Beginner, Intermediate, Advanced), summary, body, house_tip.'
    )

    user_prompt = (
        'Articles already published or already waiting for review (avoid close duplicates):\n'
        f'{existing_list}\n\n'
        'Research and draft today\'s new Knowledge Hub article now.'
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        thinking={'type': 'adaptive'},
        system=system_prompt,
        tools=[{'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 6}],
        messages=[{'role': 'user', 'content': user_prompt}],
    )

    text = ''.join(block.text for block in response.content if block.type == 'text').strip()
    article = extract_json_object(text)
    sources = extract_sources(response)

    return article, sources


def fact_check_article(client, article):
    # A second, independent pass: hands the drafted article back to Claude
    # with fresh web search and asks it to verify the claims, before a human
    # ever sees the draft. Founder: "make sure we double check these before
    # I see it." Deliberately a separate call rather than folding this into
    # research_article() -- a model re-reading its own already-written
    # answer with a skeptical, fact-checking framing catches things a single
    # "research and write" pass does not.
    system_prompt = (
        "You are a rigorous, skeptical fact-checker for House Of Wax's Knowledge Hub. You are reviewing a "
        "drafted article before any human sees it -- your job is to catch wrong or unverifiable claims now, "
        "not to write anything new or improve the prose.\n\n"
        "Check every concrete factual claim in the article below -- artist/band names, release titles, dates, "
        "labels, pressing plants, chart positions, catalog numbers, quotes -- against live web search. Do not "
        "rely on memory alone; confirm with a real source. Treat any claim you cannot confirm from a real "
        "source as unverified, even if it sounds plausible.\n\n"
        "When you are done, your FINAL message must be ONLY a single JSON object, no markdown code fences, no "
        "other prose before or after it, with exactly these keys: verdict (one of: PASS, NEEDS REVIEW), notes "
        "(a short, specific explanation -- if PASS, briefly say what you confirmed; if NEEDS REVIEW, name the "
        "exact claim(s) in question and why)."
    )
    user_prompt = (
        f"Title: {article.get('title', '')}\n\n"
        f"Summary: {article.get('summary', '')}\n\n"
        f"Body:\n{article.get('body', '')}\n\n"
        f"House Of Wax tip: {article.get('house_tip', '')}\n\n"
        "Fact-check the claims above."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        thinking={'type': 'adaptive'},
        system=system_prompt,
        tools=[{'type': 'web_search_20260209', 'name': 'web_search', 'max_uses': 6}],
        messages=[{'role': 'user', 'content': user_prompt}],
    )

    text = ''.join(block.text for block in response.content if block.type == 'text').strip()
    result = extract_json_object(text)
    verdict = result.get('verdict', 'NEEDS REVIEW')
    if verdict not in ('PASS', 'NEEDS REVIEW'):
        verdict = 'NEEDS REVIEW'
    notes = str(result.get('notes', '')).strip()
    sources = extract_sources(response)

    return verdict, notes, sources


def validate_article(article):
    required = ['title', 'category', 'audience', 'level', 'summary', 'body', 'house_tip']
    missing = [k for k in required if not str(article.get(k, '')).strip()]
    if missing:
        raise ValueError(f'Model output missing required fields: {missing}')
    if article['category'] not in KNOWLEDGE_CATEGORIES:
        print(f"[knowledge_hub_researcher] category {article['category']!r} not recognized, defaulting to 'Music History & Culture'")
        article['category'] = 'Music History & Culture'


def save_draft(supabase_url, service_key, article, sources, fact_check_notes=''):
    now = datetime.now(timezone.utc).isoformat()
    sources_text = '\n'.join(f'{title} — {url}' for title, url in sources)
    record = {
        'title': article['title'],
        'category': article['category'],
        'audience': article['audience'],
        'level': article['level'],
        'summary': article['summary'],
        'body': article['body'],
        'house_tip': article['house_tip'],
        'status': 'Draft',
        'featured': 'No',
        'source_type': 'AI Research',
        'sources': sources_text,
        'fact_check_notes': fact_check_notes,
        'created_at': now,
        'updated_at': now,
    }
    resp = requests.post(
        f'{supabase_url}/rest/v1/knowledge_posts',
        headers={
            'apikey': service_key,
            'Authorization': f'Bearer {service_key}',
            'Content-Type': 'application/json',
            'Prefer': 'return=representation',
        },
        json=record,
        timeout=30,
    )
    if not resp.ok:
        print(f'[knowledge_hub_researcher] Supabase insert failed ({resp.status_code}): {resp.text}', file=sys.stderr)
        sys.exit(1)
    return resp.json()


def main():
    anthropic_key = env('ANTHROPIC_API_KEY')
    supabase_url = env('SUPABASE_URL').rstrip('/')
    service_key = env('SUPABASE_SERVICE_ROLE_KEY')

    client = anthropic.Anthropic(api_key=anthropic_key)

    print('[knowledge_hub_researcher] fetching existing article titles for dedup...')
    existing_titles = fetch_existing_titles(supabase_url, service_key)
    print(f'[knowledge_hub_researcher] found {len(existing_titles)} existing titles')

    forced_category = TRENDING_CATEGORY if is_trending_day() else None
    if forced_category:
        print(f'[knowledge_hub_researcher] trending day -- forcing category: {forced_category}')
    print('[knowledge_hub_researcher] researching todays article...')
    article, sources = research_article(client, existing_titles, forced_category=forced_category)
    validate_article(article)

    print(f"[knowledge_hub_researcher] drafted: {article['title']!r} ({article['category']}) with {len(sources)} source(s)")

    print('[knowledge_hub_researcher] fact-checking the draft before saving...')
    verdict, notes, fact_check_sources = fact_check_article(client, article)
    print(f'[knowledge_hub_researcher] fact-check verdict: {verdict} -- {notes[:200]}')

    seen = {url for _, url in sources}
    for title, url in fact_check_sources:
        if url not in seen:
            seen.add(url)
            sources.append((title, url))

    fact_check_notes = f'{verdict}: {notes}' if notes else verdict

    saved = save_draft(supabase_url, service_key, article, sources, fact_check_notes)
    saved_id = saved[0]['id'] if isinstance(saved, list) and saved else '?'
    print(f'[knowledge_hub_researcher] saved as Draft, knowledge_posts.id={saved_id}. Review it in Content Admin -> AI Research Queue.')


if __name__ == '__main__':
    main()

-- House Of Wax V25.43 Auth / RLS foundation policies for Supabase/Postgres.
-- Run after supabase_core_schema.sql.
-- These policies replace prototype allow-all policies with ownership-based rules.
-- Review before public launch; production may need stricter public field views and service-side admin tooling.

-- is_admin_user() exists so admin-bypass policies never query app_users
-- directly inline. A policy defined ON app_users that queries app_users
-- in its own USING clause causes Postgres to detect infinite recursion
-- and reject the query entirely (error 42P17) -- which breaks not just
-- app_users but every other table whose policies look up app_users too,
-- since evaluating that lookup re-triggers app_users' own RLS. A
-- security definer function runs with the privileges of its owner
-- (bypassing RLS for its internal query), so it can safely check
-- admin_access without re-entering RLS evaluation.
create or replace function is_admin_user()
returns boolean
language sql
security definer
set search_path = public
stable
as $$
  select exists (
    select 1 from app_users
    where auth_user_id = auth.uid()
    and lower(admin_access) in ('yes','true','1','admin')
  );
$$;

alter table app_users enable row level security;
alter table buyers enable row level security;
alter table sellers enable row level security;
alter table products enable row level security;
alter table product_gallery enable row level security;
alter table listing_inquiries enable row level security;
alter table purchase_requests enable row level security;
alter table tester_feedback enable row level security;
alter table listing_reports enable row level security;
alter table knowledge_posts enable row level security;
alter table glossary_terms enable row level security;
alter table homepage_blocks enable row level security;
alter table quick_tips enable row level security;
alter table did_you_know enable row level security;
alter table newsletter_signups enable row level security;
alter table seller_followers enable row level security;
alter table seller_badges enable row level security;
alter table store_announcements enable row level security;
alter table seller_events enable row level security;
alter table seller_policies enable row level security;

do $$
declare
    t text;
begin
    foreach t in array array[
        'app_users',
        'buyers',
        'sellers',
        'products',
        'product_gallery',
        'listing_inquiries',
        'purchase_requests',
        'tester_feedback',
        'listing_reports',
        'knowledge_posts',
        'glossary_terms',
        'homepage_blocks',
        'quick_tips',
        'did_you_know',
        'newsletter_signups',
        'seller_followers',
        'seller_badges',
        'store_announcements',
        'seller_events',
        'seller_policies'
    ]
    loop
        execute format('drop policy if exists "prototype anon read %s" on %I', t, t);
        execute format('drop policy if exists "prototype anon insert %s" on %I', t, t);
        execute format('drop policy if exists "prototype anon update %s" on %I', t, t);
        execute format('drop policy if exists "prototype anon delete %s" on %I', t, t);
    end loop;
end $$;

drop policy if exists "app users read own row" on public."app_users";
create policy "app users read own row"
on app_users for select to authenticated
using (auth_user_id = auth.uid());

drop policy if exists "app users insert own row" on public."app_users";
create policy "app users insert own row"
on app_users for insert to authenticated
with check (auth_user_id = auth.uid());

drop policy if exists "app users update own row" on public."app_users";
create policy "app users update own row"
on app_users for update to authenticated
using (auth_user_id = auth.uid())
with check (auth_user_id = auth.uid());

drop policy if exists "buyers read own profile" on public."buyers";
create policy "buyers read own profile"
on buyers for select to authenticated
using (
  id in (select buyer_id from app_users where auth_user_id = auth.uid())
  or lower(email) = lower(auth.email())
);

drop policy if exists "buyers update own profile" on public."buyers";
create policy "buyers update own profile"
on buyers for update to authenticated
using (id in (select buyer_id from app_users where auth_user_id = auth.uid()))
with check (id in (select buyer_id from app_users where auth_user_id = auth.uid()));

-- Originally just "auth.uid() is not null" -- any authenticated user could
-- insert a buyers row under ANY email, not just their own, via a direct API
-- call (the app itself always passes auth_user_email(), so this was never
-- exploitable through the UI, but RLS should hold even against a request
-- that skips the app). Tightened during the V25.43 policy-logic audit. Safe
-- to tighten: the admin repair tool (which legitimately creates a buyer row
-- for someone else's email) goes through the separate unconditional
-- "admin manage buyers" policy below, which this doesn't touch.
drop policy if exists "buyers create own profile" on public."buyers";
create policy "buyers create own profile"
on buyers for insert to authenticated
with check (auth.uid() is not null and lower(email) = lower(auth.email()));

drop policy if exists "public read approved seller stores" on public."sellers";
create policy "public read approved seller stores"
on sellers for select to anon, authenticated
using (status in ('Approved Seller','Approved','Active','Verified'));

drop policy if exists "sellers read own store" on public."sellers";
create policy "sellers read own store"
on sellers for select to authenticated
using (
  id in (select seller_id from app_users where auth_user_id = auth.uid())
  or lower(email) = lower(auth.email())
);

drop policy if exists "sellers update own store" on public."sellers";
create policy "sellers update own store"
on sellers for update to authenticated
using (id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (id in (select seller_id from app_users where auth_user_id = auth.uid()));

-- Same tightening as "buyers create own profile" above, same reasoning:
-- every app.py call site already passes auth_user_email(), and the
-- unconditional "admin manage sellers" policy below is untouched by this.
drop policy if exists "sellers create own store" on public."sellers";
create policy "sellers create own store"
on sellers for insert to authenticated
with check (auth.uid() is not null and lower(email) = lower(auth.email()));

drop policy if exists "public read live products" on public."products";
create policy "public read live products"
on products for select to anon, authenticated
using (listing_status in ('Live','Active','Approved','Public','Pending Pickup/Payment','Pending','Sold'));

drop policy if exists "seller read own products" on public."products";
create policy "seller read own products"
on products for select to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "seller create own products" on public."products";
create policy "seller create own products"
on products for insert to authenticated
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "seller update own products" on public."products";
create policy "seller update own products"
on products for update to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "public read product gallery for public products" on public."product_gallery";
create policy "public read product gallery for public products"
on product_gallery for select to anon, authenticated
using (product_id in (select id from products where listing_status in ('Live','Active','Approved','Public','Pending Pickup/Payment','Pending','Sold')));

drop policy if exists "seller manage gallery for own products" on public."product_gallery";
create policy "seller manage gallery for own products"
on product_gallery for all to authenticated
using (product_id in (select id from products where seller_id in (select seller_id from app_users where auth_user_id = auth.uid())))
with check (product_id in (select id from products where seller_id in (select seller_id from app_users where auth_user_id = auth.uid())));

drop policy if exists "buyer create own inquiries" on public."listing_inquiries";
create policy "buyer create own inquiries"
on listing_inquiries for insert to authenticated
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "buyer read own inquiries" on public."listing_inquiries";
create policy "buyer read own inquiries"
on listing_inquiries for select to authenticated
using (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid())
   or seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "seller update own inquiries" on public."listing_inquiries";
create policy "seller update own inquiries"
on listing_inquiries for update to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "buyer create own purchase requests" on public."purchase_requests";
create policy "buyer create own purchase requests"
on purchase_requests for insert to authenticated
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "buyer seller read purchase requests" on public."purchase_requests";
create policy "buyer seller read purchase requests"
on purchase_requests for select to authenticated
using (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid())
   or seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "seller update own purchase requests" on public."purchase_requests";
create policy "seller update own purchase requests"
on purchase_requests for update to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "buyer update own purchase requests" on public."purchase_requests";
create policy "buyer update own purchase requests"
on purchase_requests for update to authenticated
using (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()))
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "authenticated submit listing reports" on public."listing_reports";
create policy "authenticated submit listing reports"
on listing_reports for insert to authenticated
with check (true);

drop policy if exists "authenticated submit tester feedback" on public."tester_feedback";
create policy "authenticated submit tester feedback"
on tester_feedback for insert to authenticated
with check (true);

drop policy if exists "public read active homepage blocks" on public."homepage_blocks";
create policy "public read active homepage blocks"
on homepage_blocks for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage homepage blocks" on public."homepage_blocks";
create policy "admin manage homepage blocks"
on homepage_blocks for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read active quick tips" on public."quick_tips";
create policy "public read active quick tips"
on quick_tips for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage quick tips" on public."quick_tips";
create policy "admin manage quick tips"
on quick_tips for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read active did you know" on public."did_you_know";
create policy "public read active did you know"
on did_you_know for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage did you know" on public."did_you_know";
create policy "admin manage did you know"
on did_you_know for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- newsletter_signups holds real visitor email addresses. No public read
-- policy is defined at all -- only insert (so the signup form works for
-- anyone) and the admin bypass below (so the Homepage Editor can list
-- and export signups).
drop policy if exists "anon submit newsletter signup" on public."newsletter_signups";
create policy "anon submit newsletter signup"
on newsletter_signups for insert to anon, authenticated
with check (true);

drop policy if exists "admin manage newsletter signups" on public."newsletter_signups";
create policy "admin manage newsletter signups"
on newsletter_signups for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- Follower counts and badges are shown on public seller storefronts, so
-- both need public read. Only a buyer's own follow action needs a write
-- policy -- badges are admin-granted trust signals, not self-assigned.
drop policy if exists "public read seller followers" on public."seller_followers";
create policy "public read seller followers"
on seller_followers for select to anon, authenticated
using (true);

drop policy if exists "buyer follow seller" on public."seller_followers";
create policy "buyer follow seller"
on seller_followers for insert to authenticated
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage seller followers" on public."seller_followers";
create policy "admin manage seller followers"
on seller_followers for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read active seller badges" on public."seller_badges";
create policy "public read active seller badges"
on seller_badges for select to anon, authenticated
using (active = 'Yes');

drop policy if exists "admin manage seller badges" on public."seller_badges";
create policy "admin manage seller badges"
on seller_badges for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- Announcements, events, and policies are seller-owned content shown on
-- the seller's own public storefront -- public read, seller writes only
-- their own rows, admin can manage any row.
drop policy if exists "public read active store announcements" on public."store_announcements";
create policy "public read active store announcements"
on store_announcements for select to anon, authenticated
using (status = 'Active');

drop policy if exists "seller manage own store announcements" on public."store_announcements";
create policy "seller manage own store announcements"
on store_announcements for all to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage store announcements" on public."store_announcements";
create policy "admin manage store announcements"
on store_announcements for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read active seller events" on public."seller_events";
create policy "public read active seller events"
on seller_events for select to anon, authenticated
using (status = 'Active');

drop policy if exists "seller manage own seller events" on public."seller_events";
create policy "seller manage own seller events"
on seller_events for all to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage seller events" on public."seller_events";
create policy "admin manage seller events"
on seller_events for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read seller policies" on public."seller_policies";
create policy "public read seller policies"
on seller_policies for select to anon, authenticated
using (true);

drop policy if exists "seller manage own seller policies" on public."seller_policies";
create policy "seller manage own seller policies"
on seller_policies for all to authenticated
using (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()))
with check (seller_id in (select seller_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage seller policies" on public."seller_policies";
create policy "admin manage seller policies"
on seller_policies for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read published knowledge posts" on public."knowledge_posts";
create policy "public read published knowledge posts"
on knowledge_posts for select to anon, authenticated
using (status = 'Published');

drop policy if exists "admin manage knowledge posts" on public."knowledge_posts";
create policy "admin manage knowledge posts"
on knowledge_posts for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "public read published glossary terms" on public."glossary_terms";
create policy "public read published glossary terms"
on glossary_terms for select to anon, authenticated
using (status = 'Published');

drop policy if exists "admin manage glossary terms" on public."glossary_terms";
create policy "admin manage glossary terms"
on glossary_terms for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- ---------- Admin bypass policies ----------
-- The app has no elevated Postgres role (no service_role key is used
-- anywhere in the Streamlit app), so every "admin" action in the UI runs
-- under the same authenticated role as a normal user and is just as
-- subject to RLS as anyone else. Without a bypass policy per table, admin
-- screens for seller approval, moderation, and support silently show
-- empty/partial data instead of erroring. Same pattern as the
-- knowledge_posts/glossary_terms admin policies above.

drop policy if exists "admin manage sellers" on public."sellers";
create policy "admin manage sellers"
on sellers for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage products" on public."products";
create policy "admin manage products"
on products for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage buyers" on public."buyers";
create policy "admin manage buyers"
on buyers for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage app users" on public."app_users";
create policy "admin manage app users"
on app_users for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage listing inquiries" on public."listing_inquiries";
create policy "admin manage listing inquiries"
on listing_inquiries for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage purchase requests" on public."purchase_requests";
create policy "admin manage purchase requests"
on purchase_requests for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage listing reports" on public."listing_reports";
create policy "admin manage listing reports"
on listing_reports for all to authenticated
using (is_admin_user())
with check (is_admin_user());

drop policy if exists "admin manage tester feedback" on public."tester_feedback";
create policy "admin manage tester feedback"
on tester_feedback for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- listing_reports and tester_feedback previously only allowed inserts from
-- the authenticated role, but the report-a-listing and tester-feedback
-- forms in the app have no sign-in gate and are reachable while signed
-- out. Extending the same insert-only, no-read-back policy to anon
-- matches how those forms actually behave today, instead of silently
-- failing for a signed-out visitor.
drop policy if exists "anon submit listing reports" on public."listing_reports";
create policy "anon submit listing reports"
on listing_reports for insert to anon
with check (true);

drop policy if exists "anon submit tester feedback" on public."tester_feedback";
create policy "anon submit tester feedback"
on tester_feedback for insert to anon
with check (true);

-- Admin management should be handled by secure server/service tooling or custom claims.
-- Do not expose service_role keys in Streamlit.
-- Note: the ADMIN_EMAILS allowlist (app-layer only) is not enforceable in RLS;
-- admins added only via that allowlist (not app_users.admin_access='Yes') will
-- need admin_access set on their app_users row to write knowledge content directly.

-- products.reviewer_notes is internal admin moderation commentary, never
-- meant to be public. RLS is row-level only, so the "public read live
-- products" policy above (which grants anon full-row SELECT on live
-- listings) was exposing it to any unauthenticated request via
-- select=* on the REST API. Restrict anon's column-level access instead
-- of touching the row policy, so this doesn't affect Testing Mode admin
-- access (which runs as anon/authenticated too, with no real elevated
-- Postgres role) -- any genuinely signed-in user keeps full access.
revoke select on public.products from anon;
grant select (
  id, seller_id, sku, barcode, catalog_number, matrix_runout, category,
  artist, title, format, label, release_year, genre, media_grade,
  sleeve_grade, condition_notes, description, price, quantity,
  shipping_price, image_url, reference_image_url, video_url, audio_url,
  external_release_url, listing_status, listing_type, created_at, updated_at
) on public.products to anon;

-- sellers.paypal_link is how a buyer actually pays a seller directly (see
-- the hands-off payment model) -- a real spam/phishing target if exposed to
-- anyone via the public REST API, not just genuine buyers mid-transaction.
-- Same anon-safe-select pattern as products.reviewer_notes above. This grant
-- was applied directly against the live database (that's why get_seller_full's
-- select=* started 401ing for anon/Testing Mode -- see the V25.43.83 fix) but
-- was never added here, so recreating this database from this file alone
-- would have left sellers fully exposed to anon select=*. Keep this in sync
-- with SELLERS_ANON_SAFE_SELECT in app.py if that list ever changes.
revoke select on public.sellers from anon;
grant select (
  id, store_name, owner_name, email, phone, city, state, website, instagram,
  store_bio, seller_story, specialties, logo_url, banner_url, status,
  seller_level, rating, completed_sales, disputes, strikes, auction_override,
  access_code, rules_accepted, rules_accepted_at, created_at
) on public.sellers to anon;

-- want_list, seller_reviews, and avatar_faq_videos: found with zero RLS/policy
-- coverage anywhere in this file during the V25.43 audit, despite being live
-- CORE_HOSTED_TABLES features. Adding the policies their actual app.py usage
-- requires, matching the ownership/public-read patterns already established
-- above for the equivalent tables (buyers-own-rows, public content, etc).

-- want_list is a buyer's private want-hunting list -- no public read, only
-- the owning buyer (and admin) can see or manage it.
drop policy if exists "buyer manage own want list" on public."want_list";
create policy "buyer manage own want list"
on want_list for all to authenticated
using (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()))
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage want list" on public."want_list";
create policy "admin manage want list"
on want_list for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- Matching a new listing against every buyer's want_list needs to read
-- across ALL buyers, not just the seller's own -- something RLS on
-- want_list deliberately blocks above. app.py's find_want_list_matches_for_notify
-- already expects a security-definer RPC of this exact name/shape (see the
-- comment there); without it, notify_want_list_matches silently returns no
-- matches and buyers never get notified, with no error anywhere. This is
-- almost certainly why want-list match emails have not been going out.
create or replace function find_want_list_matches(p_artist text, p_title text default '')
returns table(buyer_id bigint, email text, name text, want_title text)
language sql
security definer
set search_path = public
stable
as $$
  select w.buyer_id, b.email, b.name, w.title as want_title
  from want_list w
  join buyers b on b.id = w.buyer_id
  where w.status = 'Active'
    and lower(w.artist) = lower(p_artist)
    and (w.title is null or w.title = '' or lower(w.title) = lower(coalesce(p_title,'')));
$$;

-- seller_reviews are shown on public seller profile pages (seller_profile()
-- calls seller_reviews(sid) with no auth gate), so anon needs read access.
-- Only the reviewing buyer can create their own review; no update/delete
-- path exists in the app today, so none is granted here either.
drop policy if exists "public read seller reviews" on public."seller_reviews";
create policy "public read seller reviews"
on seller_reviews for select to anon, authenticated
using (true);

drop policy if exists "buyer create own seller review" on public."seller_reviews";
create policy "buyer create own seller review"
on seller_reviews for insert to authenticated
with check (buyer_id in (select buyer_id from app_users where auth_user_id = auth.uid()));

drop policy if exists "admin manage seller reviews" on public."seller_reviews";
create policy "admin manage seller reviews"
on seller_reviews for all to authenticated
using (is_admin_user())
with check (is_admin_user());

-- avatar_faq_videos is admin-authored FAQ content, publicly readable when
-- Active -- same shape as homepage_blocks/quick_tips/did_you_know above.
drop policy if exists "public read active avatar faq videos" on public."avatar_faq_videos";
create policy "public read active avatar faq videos"
on avatar_faq_videos for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage avatar faq videos" on public."avatar_faq_videos";
create policy "admin manage avatar faq videos"
on avatar_faq_videos for all to authenticated
using (is_admin_user())
with check (is_admin_user());

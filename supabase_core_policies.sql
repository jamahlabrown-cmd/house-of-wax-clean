-- House Of Wax V25.43 Auth / RLS foundation policies for Supabase/Postgres.
-- Run after supabase_core_schema.sql.
-- These policies replace prototype allow-all policies with ownership-based rules.
-- Review before public launch; production may need stricter public field views and service-side admin tooling.

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
        'newsletter_signups'
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

drop policy if exists "buyers create own profile" on public."buyers";
create policy "buyers create own profile"
on buyers for insert to authenticated
with check (auth.uid() is not null);

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

drop policy if exists "sellers create own store" on public."sellers";
create policy "sellers create own store"
on sellers for insert to authenticated
with check (auth.uid() is not null);

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
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "public read active quick tips" on public."quick_tips";
create policy "public read active quick tips"
on quick_tips for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage quick tips" on public."quick_tips";
create policy "admin manage quick tips"
on quick_tips for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "public read active did you know" on public."did_you_know";
create policy "public read active did you know"
on did_you_know for select to anon, authenticated
using (status = 'Active');

drop policy if exists "admin manage did you know" on public."did_you_know";
create policy "admin manage did you know"
on did_you_know for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

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
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "public read published knowledge posts" on public."knowledge_posts";
create policy "public read published knowledge posts"
on knowledge_posts for select to anon, authenticated
using (status = 'Published');

drop policy if exists "admin manage knowledge posts" on public."knowledge_posts";
create policy "admin manage knowledge posts"
on knowledge_posts for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "public read published glossary terms" on public."glossary_terms";
create policy "public read published glossary terms"
on glossary_terms for select to anon, authenticated
using (status = 'Published');

drop policy if exists "admin manage glossary terms" on public."glossary_terms";
create policy "admin manage glossary terms"
on glossary_terms for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

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
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage products" on public."products";
create policy "admin manage products"
on products for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage buyers" on public."buyers";
create policy "admin manage buyers"
on buyers for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage app users" on public."app_users";
create policy "admin manage app users"
on app_users for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage listing inquiries" on public."listing_inquiries";
create policy "admin manage listing inquiries"
on listing_inquiries for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage purchase requests" on public."purchase_requests";
create policy "admin manage purchase requests"
on purchase_requests for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage listing reports" on public."listing_reports";
create policy "admin manage listing reports"
on listing_reports for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

drop policy if exists "admin manage tester feedback" on public."tester_feedback";
create policy "admin manage tester feedback"
on tester_feedback for all to authenticated
using (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')))
with check (auth.uid() in (select auth_user_id from app_users where lower(admin_access) in ('yes','true','1','admin')));

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

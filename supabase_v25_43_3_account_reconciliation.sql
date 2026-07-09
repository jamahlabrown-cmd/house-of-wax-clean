-- House Of Wax V25.43.3 one-account reconciliation helper
-- Run only in the Supabase SQL editor or another trusted admin SQL environment.
-- Do not paste service_role keys into Streamlit or public client code.
-- This script does not drop tables and does not delete user data.

alter table if exists public.app_users
  add column if not exists seller_application_status text default 'Not Applied';

alter table if exists public.app_users
  add column if not exists account_status text default 'Active';

update public.app_users
set account_status = coalesce(nullif(account_status, ''), coalesce(nullif(status, ''), 'Active'))
where account_status is null or account_status = '';

update public.app_users
set seller_application_status = 'Not Applied'
where coalesce(seller_id, 0) = 0
  and (seller_application_status is null or seller_application_status = '');

update public.app_users
set seller_application_status = 'Pending Seller Approval'
where coalesce(seller_id, 0) > 0
  and (seller_application_status is null or seller_application_status = '' or seller_application_status = 'Not Applied');

-- Find Supabase Auth users that do not yet have an app_users row.
-- This requires Supabase admin SQL access because auth.users is protected.
select
  au.id as auth_user_id,
  au.email,
  au.created_at as auth_created_at,
  au.last_sign_in_at,
  pu.id as app_user_id,
  pu.buyer_id,
  pu.seller_id,
  pu.seller_application_status,
  case when pu.id is null then 'Missing app_users row' else 'Mapped' end as mapping_status
from auth.users au
left join public.app_users pu
  on pu.auth_user_id = au.id
  or lower(pu.email) = lower(au.email)
order by au.created_at desc;

-- Optional manual repair pattern for one exact Auth user.
-- Replace the placeholders, review the row first, then run intentionally.
-- This creates/links app_users only. The app will create/link buyer profile
-- on next sign-in, or you can create buyer rows separately if needed.
/*
insert into public.app_users (
  auth_user_id,
  email,
  display_name,
  account_type,
  buyer_id,
  seller_id,
  seller_application_status,
  admin_access,
  account_status,
  status,
  created_at,
  updated_at
)
values (
  'AUTH_USER_ID_HERE',
  lower('EMAIL_HERE'),
  'DISPLAY_NAME_HERE',
  'Buyer',
  0,
  0,
  'Not Applied',
  'No',
  'Active',
  'Active',
  now(),
  now()
)
on conflict (email) do update
set
  auth_user_id = excluded.auth_user_id,
  display_name = coalesce(nullif(public.app_users.display_name, ''), excluded.display_name),
  account_type = coalesce(nullif(public.app_users.account_type, ''), 'Buyer'),
  account_status = coalesce(nullif(public.app_users.account_status, ''), 'Active'),
  status = coalesce(nullif(public.app_users.status, ''), 'Active'),
  seller_application_status = coalesce(nullif(public.app_users.seller_application_status, ''), 'Not Applied'),
  updated_at = now();
*/

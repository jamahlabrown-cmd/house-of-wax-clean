-- House Of Wax homepage copy refresh (V25.43.91).
-- Run this in the Supabase SQL editor to push the new copy live immediately.
--
-- Why this is a separate script: homepage_blocks, quick_tips, and did_you_know
-- are only seeded from app.py's defaults in local-SQLite/demo mode -- once
-- Supabase is the active store, seed_homepage_editorial() returns early and
-- never touches these tables again. Redeploying app.py alone will NOT change
-- what visitors see; these rows have to be updated directly.
--
-- Safe to re-run: homepage_blocks updates match on block_name (one active row
-- each), and quick_tips/did_you_know are archived (Hidden) rather than
-- deleted, so no history is lost.

update public.homepage_blocks set
  subtitle='Dig deeper. Buy smarter. Play louder.',
  body='Every used record has a story — who owned it, how it was pressed, why it still matters. We''ll help you read the runout groove, grade a sleeve like you mean it, and buy from sellers who actually know their stock.',
  updated_at=now()::text
where block_name='hero' and status='Active';

update public.homepage_blocks set
  body='VG+ doesn''t mean flawless — it means played, loved, and still sounding strong, with only light signs it''s been spun before. Know the grade before you trust the price.',
  updated_at=now()::text
where block_name='featured_story' and status='Active';

update public.homepage_blocks set
  title='The Secret Code Etched Into Every Record',
  subtitle='This Week: Matrix & Runout',
  body='Look close at the dead wax near the label — those scratched letters and numbers are the record''s fingerprint. They can name the pressing plant, the mastering engineer, even which version you''re actually holding.',
  updated_at=now()::text
where block_name='weekly_focus' and status='Active';

update public.homepage_blocks set
  subtitle='Genre Spotlight',
  body='Southern soul isn''t just a sound, it''s a sense of place — church roots, blues undertow, deep vocals, and stories that could only come from where they were sung.',
  updated_at=now()::text
where block_name='genre_spotlight' and status='Active';

update public.homepage_blocks set
  body='Cassettes are portable, imperfect, and personal — built for mixtapes, not perfection. Their comeback isn''t nostalgia. It''s people wanting something they can actually hold.',
  updated_at=now()::text
where block_name='editorial_pick' and status='Active';

update public.homepage_blocks set
  body='No spam, no fluff — just grading breakdowns, pressing deep-dives, and the occasional argument about first pressings, straight from House Of Wax.',
  updated_at=now()::text
where block_name='newsletter' and status='Active';

-- Quick tips: archive the old set, install the new one.
update public.quick_tips set status='Hidden', updated_at=now()::text where status='Active';
insert into public.quick_tips(tip_text,category,status,created_at,updated_at) values
  ('A barcode narrows it down. It doesn''t seal the deal — check the runout too.','Barcode, Catalog & Matrix Guides','Active',now()::text,now()::text),
  ('A mint sleeve can hide a trashed record. Always grade the vinyl and the jacket separately.','Vinyl Grading School','Active',now()::text,now()::text),
  ('''Original pressing'' isn''t automatically ''best sounding pressing.'' Some remasters genuinely outclass the OG.','Record Collecting 101','Active',now()::text,now()::text),
  ('Promo stamp on the cover? Cool story. Still won''t save a record with condition and demand against it.','Record Collecting 101','Active',now()::text,now()::text),
  ('If a "rare" find is priced like a garage-sale record, slow down and ask why.','How to Buy Safely','Active',now()::text,now()::text);

-- Did you know: archive the old set, install the new one.
update public.did_you_know set status='Hidden', updated_at=now()::text where status='Active';
insert into public.did_you_know(fact_text,category,status,created_at,updated_at) values
  ('Those tiny etched letters near the label — the runout — can name-drop the pressing plant, the mastering engineer, even the exact version you''re holding.','Barcode, Catalog & Matrix Guides','Active',now()::text,now()::text),
  ('VG+ is the most-quoted grade in collecting, and the most misunderstood. It still means ''played'' — just played carefully.','Vinyl Grading School','Active',now()::text,now()::text),
  ('Not all reissues are lesser copies. A well-mastered, clearly labeled reissue can earn more respect than a beat-up original.','Spotting Bootlegs and Reissues','Active',now()::text,now()::text),
  ('Rarity isn''t the only thing that makes memorabilia matter. Sometimes the story is the value.','Music History & Culture','Active',now()::text,now()::text);

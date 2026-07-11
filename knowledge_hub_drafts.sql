-- House Of Wax Knowledge Hub — draft article batch
-- Inserts 5 new articles as Draft status. They will NOT appear publicly
-- until reviewed and published from Content Admin > Article Library.
-- Safe to run once; re-running will create duplicate rows (titles are not unique).

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) values
(
  'Record Collecting 101: Where to Actually Start',
  'Record Collecting 101',
  'Beginners',
  'Beginner',
  'Collecting is not about buying everything you find. It is about learning enough to buy on purpose.',
  E'Most new collectors start the same way: they buy whatever looks interesting at a low price, then realize a few months in that they own a shelf of records they do not really listen to. A better starting point is to pick one or two artists, labels, or genres you already love and go deep before you go wide. Learn what a first pressing of an album looks like versus a reissue, what formats it was released in (LP, 45, cassette, CD), and roughly what fair condition and price look like for it.\n\nFormat matters more than most beginners expect. A 12-inch LP, a 7-inch 45, and a cassette are not interchangeable versions of the same thing — they can have different mixes, different track lists, and very different collector value. Before buying, check the listing for format, pressing details, and condition notes for both the media and the sleeve. If those details are missing, ask the seller before you buy, not after.\n\nBudget is the other piece people skip. Decide what you are willing to spend per item and per month before you start browsing, not while you are looking at a listing. Collecting stays fun when it has a boundary around it.',
  'Start with one artist or label you already love, and let your collection grow outward from there instead of buying at random.',
  'Draft','No',now()::text,now()::text
),
(
  'How to Buy Vinyl Safely Online (Without Getting Burned)',
  'How to Buy Safely',
  'Buyers',
  'Beginner',
  'Most bad buying experiences come from skipped questions, not bad luck.',
  E'Before you buy from a seller you have not bought from before, take two minutes to look at their profile: how long they have been active, what other listings look like, and whether their condition notes are specific or vague. A seller who writes "VG+, light sleeve wear, plays clean" is telling you more than one who writes "good condition."\n\nIf photos only show the front cover, ask for photos of the actual disc, the back cover, and any visible wear before you commit. A listing photo pulled from the internet instead of the actual item is a warning sign, and so is a price that is dramatically lower than every other copy of the same record. Rare or high-demand records rarely show up underpriced by accident.\n\nUse the platform''s own tools instead of moving a deal off-platform. Send your questions through Contact Seller, and use Request to Buy rather than agreeing to a side deal over email or text. Staying on-platform keeps a record of what was said and agreed to, which protects you if the item does not match what was described.',
  'If a listing cannot answer "what pressing, what condition, and can I see real photos," ask before you pay, not after.',
  'Draft','No',now()::text,now()::text
),
(
  'How to Explore a New Genre Without Getting Lost',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Genres are a starting map, not a strict rulebook — most great records sit between categories.',
  E'When you are new to a genre, it helps to stop thinking of it as one sound and start thinking of it as a family tree. Almost every genre has an origin point, a handful of regional scenes that shaped it differently, and later movements that pushed against or built on what came before. Southern soul does not sound like Chicago soul, and 1960s reggae does not sound like 1980s dancehall, even though they share a lineage.\n\nLiner notes, label names, and personnel credits are some of the best free research tools a collector has. A producer, session player, or studio that shows up across several records you like is often a faster way to find your next favorite artist than searching by genre name alone. Following people, not just genre tags, tends to lead somewhere more interesting.\n\nDo not worry about getting the "correct" entry point. Genres blur at the edges on purpose — some of the most respected records in any style are the ones that borrowed from somewhere else.',
  'Pick one artist you already like, then follow the musicians and producers who worked with them — that trail usually beats a genre search.',
  'Draft','No',now()::text,now()::text
),
(
  'Why the Story Behind a Record Matters as Much as the Music',
  'Music History & Culture',
  'Everyone',
  'Beginner',
  'A record is a physical object with a place and time attached to it — that context is part of what you are collecting.',
  E'Every record was made somewhere, by someone, for a reason. A pressing plant, a regional scene, a label with a specific sound, a moment in a city''s history — all of that shapes what ends up in your hands. Knowing the context behind a record does not just make you a more informed collector, it changes how the music sounds to you. A gospel-rooted soul record from a small Southern label carries a different weight once you know the church halls and radio stations that shaped it.\n\nA simple habit worth building: before or after you buy something new, spend five minutes learning who made it, where it was recorded, and what else was happening in that scene at the time. Who was the label run by? What other artists came out of the same city or studio? Small questions like these turn a purchase into a piece of a bigger picture instead of just an item on a shelf.\n\nThis is also why House Of Wax treats culture and history as part of the marketplace, not separate from it. Understanding the story behind a record helps you buy smarter and appreciate it more.',
  'Look up the label and city behind your next purchase before you play it for the first time — it changes how you listen.',
  'Draft','No',now()::text,now()::text
),
(
  'How the House Of Wax Marketplace Actually Works',
  'Marketplace Education',
  'Everyone',
  'Beginner',
  'Understanding listing statuses and the buying flow helps both buyers and sellers avoid confusion.',
  E'A listing on House Of Wax moves through a few clear stages. "Live" means it is publicly available and open to inquiries or purchase requests. Once a buyer submits a purchase request and the seller accepts it, the listing moves to "Pending Pickup/Payment" so other buyers know it is being finalized. If that request is later declined or closed and no other request is active, the listing automatically returns to "Live" so it stays available.\n\nInquiries and purchase requests serve different purposes. Use Contact Seller / Ask About This Item when you have a question about condition, pressing, or shipping before you are ready to commit. Use Request to Buy when you are ready to move forward with a specific item. Sellers see both in one place and can respond directly.\n\nSeller accounts go through an approval step before they can publish live listings, and public buyer/seller feedback exists so that trust in the marketplace is visible, not just assumed. If something about a listing or a seller does not seem right, use the report tools rather than guessing — that is what they are there for.',
  'If you are ever unsure whether to send an inquiry or a purchase request, ask a question first — you can always request to buy once you have the answer.',
  'Draft','No',now()::text,now()::text
);

-- House Of Wax Knowledge Hub -- first content batch, revision pass
-- Updates 3 of the original 5 articles (Record Collecting 101, How to
-- Explore a New Genre, Why the Story Behind a Record Matters) with
-- concrete artist examples and, for two of them, a representative
-- YouTube video via the existing video_url field.
--
-- "How to Buy Vinyl Safely Online" and "How the House Of Wax
-- Marketplace Actually Works" are left untouched -- they're process
-- and trust content, not music content, so an artist mention would be
-- forced rather than useful.
--
-- Uses UPDATE (these 5 were already loaded in the first session), so
-- safe to run only if you already ran the original first-batch SQL.

update knowledge_posts set
  body = E'Most new collectors start the same way: they buy whatever looks interesting at a low price, then realize a few months in that they own a shelf of records they do not really listen to. A better starting point is to pick one or two artists, labels, or genres you already love and go deep before you go wide. If you love Fleetwood Mac, that might mean tracking down every studio pressing from Peter Green-era Fleetwood Mac through the Rumours-era lineup before branching out -- learning what a first pressing looks like versus a reissue, what formats it was released in (LP, 45, cassette, CD), and roughly what fair condition and price look like for it.\n\nFormat matters more than most beginners expect. A 12-inch LP, a 7-inch 45, and a cassette are not interchangeable versions of the same thing -- they can have different mixes, different track lists, and very different collector value. Before buying, check the listing for format, pressing details, and condition notes for both the media and the sleeve. If those details are missing, ask the seller before you buy, not after.\n\nBudget is the other piece people skip. Decide what you are willing to spend per item and per month before you start browsing, not while you are looking at a listing. Collecting stays fun when it has a boundary around it.',
  updated_at = now()::text
where status='Draft' and title='Record Collecting 101: Where to Actually Start';

update knowledge_posts set
  body = E'When you are new to a genre, it helps to stop thinking of it as one sound and start thinking of it as a family tree. Almost every genre has an origin point, a handful of regional scenes that shaped it differently, and later movements that pushed against or built on what came before. Southern soul does not sound like Chicago soul, and 1960s reggae does not sound like 1980s dancehall, even though they share a lineage.\n\nLiner notes, label names, and personnel credits are some of the best free research tools a collector has. A producer, session player, or studio that shows up across several records you like is often a faster way to find your next favorite artist than searching by genre name alone. For example, a fan of Aretha Franklin''s Atlantic recordings can trace producer Jerry Wexler''s credits to a whole web of other Muscle Shoals and Stax-adjacent soul artists worth exploring next. Following people, not just genre tags, tends to lead somewhere more interesting.\n\nDo not worry about getting the "correct" entry point. Genres blur at the edges on purpose -- some of the most respected records in any style are the ones that borrowed from somewhere else. House Of Wax''s Genre Spotlight articles in the Knowledge Hub are a good place to find a starting artist and track for genres you have not explored yet.',
  video_url = 'https://www.youtube.com/watch?v=U0yIf9Tkgu4',
  updated_at = now()::text
where status='Draft' and title='How to Explore a New Genre Without Getting Lost';

update knowledge_posts set
  body = E'Every record was made somewhere, by someone, for a reason. A pressing plant, a regional scene, a label with a specific sound, a moment in a city''s history -- all of that shapes what ends up in your hands. Knowing the context behind a record does not just make you a more informed collector, it changes how the music sounds to you. Otis Redding''s "(Sittin'' On) The Dock of the Bay," recorded for Stax Records in Memphis just before his death in 1967, carries a different weight once you know the label, the city, and the moment it came out of -- that context is part of what you are hearing, not separate from it.\n\nA simple habit worth building: before or after you buy something new, spend five minutes learning who made it, where it was recorded, and what else was happening in that scene at the time. Who was the label run by? What other artists came out of the same city or studio? Small questions like these turn a purchase into a piece of a bigger picture instead of just an item on a shelf.\n\nThis is also why House Of Wax treats culture and history as part of the marketplace, not separate from it. Understanding the story behind a record helps you buy smarter and appreciate it more.',
  video_url = 'https://www.youtube.com/watch?v=rTVjnBo96Ug',
  updated_at = now()::text
where status='Draft' and title='Why the Story Behind a Record Matters as Much as the Music';

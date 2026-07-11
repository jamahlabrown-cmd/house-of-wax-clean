-- House Of Wax -- one-time production seed for Homepage Editor content.
-- Local SQLite dev auto-seeds this via seed_homepage_editorial(), but that
-- function now skips seeding entirely when hosted (same pattern as
-- seed_knowledge()) so a fresh Supabase project needs this run once.
-- Safe to run only if these tables are currently empty -- re-running
-- after content already exists would create duplicates (block_name is
-- not unique).

insert into homepage_blocks (block_name,title,subtitle,body,button_text,button_target,status,sort_order,created_at,updated_at) values
('hero','House Of Wax','Music. Culture. Collecting. Community.','Discover the stories, sounds, formats, and knowledge behind the music you collect. House Of Wax is where marketplace trust meets music culture education.','Visit Knowledge Hub','Knowledge Hub','Active',1,now()::text,now()::text),
('featured_story','What Does VG+ Really Mean?','Featured Story','VG+ does not mean perfect. It means the record has been played but should still sound strong, with only light signs of use. Before you buy used vinyl, learn what grades actually mean.','Read the Guide','Knowledge Hub','Active',2,now()::text,now()::text),
('weekly_focus','This Week at House Of Wax','Matrix / Runout','The small letters and numbers etched near the center of a record can tell a big story. Matrix and runout information can help identify pressings, mastering details, and release versions.','Learn About Runouts','Knowledge Hub','Active',3,now()::text,now()::text),
('genre_spotlight','Southern Soul Essentials','Genre / Era Spotlight','Southern soul is more than a sound. It carries church roots, regional storytelling, blues influence, deep vocals, and a sense of place.','Explore Spotlight','Knowledge Hub','Active',4,now()::text,now()::text),
('editorial_pick','Format Focus: Why Cassettes Still Matter','House Of Wax Editorial Pick','Cassettes are portable, imperfect, personal, and deeply tied to mixtape culture. Their return is not just nostalgia -- it is about physical connection.','Read More','Knowledge Hub','Active',5,now()::text,now()::text),
('newsletter','Join House Of Wax','Join the Culture','Get collector tips, music culture stories, grading guides, and marketplace education from House Of Wax.','Join the List','Newsletter','Active',6,now()::text,now()::text);

insert into quick_tips (tip_text,category,status,created_at,updated_at) values
('A barcode can help identify a reissue, but it does not tell the whole story.','Barcode, Catalog & Matrix Guides','Active',now()::text,now()::text),
('A clean sleeve does not always mean the record is clean. Check both media and sleeve grades.','Vinyl Grading School','Active',now()::text,now()::text),
('Original pressings are not always the best sounding version. Research matters.','Record Collecting 101','Active',now()::text,now()::text),
('A promo copy can be collectible, but condition and demand still matter.','Record Collecting 101','Active',now()::text,now()::text),
('If a rare record is priced too low, slow down and verify the details.','How to Buy Safely','Active',now()::text,now()::text);

insert into did_you_know (fact_text,category,status,created_at,updated_at) values
('The matrix/runout area of a record can sometimes help identify the pressing plant, mastering engineer, or version.','Barcode, Catalog & Matrix Guides','Active',now()::text,now()::text),
('VG+ is one of the most common collector grades, but it still allows minor signs of use.','Vinyl Grading School','Active',now()::text,now()::text),
('Some reissues are highly respected by collectors, especially when they are well mastered and clearly documented.','Spotting Bootlegs and Reissues','Active',now()::text,now()::text),
('Music memorabilia can carry cultural value even when it is not rare.','Music History & Culture','Active',now()::text,now()::text);

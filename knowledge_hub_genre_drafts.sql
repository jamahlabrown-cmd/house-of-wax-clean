-- House Of Wax Knowledge Hub -- Genre Education draft batch
-- Inserts 9 new articles as Draft status. They will NOT appear publicly
-- until reviewed and published from Content Admin > Article Library.
-- Safe to run once; re-running will create duplicate rows (titles are not unique).

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) values
(
  'Genre Spotlight: Eurodance',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Fast, synthetic, and built for the dancefloor -- Eurodance defined a specific stretch of the 1990s.',
  E'Eurodance grew out of late-1980s and early-1990s European club culture, blending high-BPM electronic production with pop songwriting and, often, a rapped verse paired with a sung, anthemic chorus. It leaned heavily on synthesizers and drum machines rather than live instrumentation, which made it cheap to produce and easy to export across borders -- a big reason it spread so fast across Germany, the Netherlands, Sweden, and beyond before crossing to US radio and clubs.\n\nThe genre peaked commercially in the early-to-mid 1990s, and it is often remembered for its clear structure: a spoken or rapped intro, a driving beat, and a big, simple hook meant to work as loud on the radio as it did in a club. Vocals were frequently split between a rapper and a featured singer, a format that became something of a Eurodance signature.\n\nCollecting Eurodance means paying attention to regional pressings -- the same single often had different mixes released in different countries, and 12-inch club mixes can differ significantly from the radio edit found on CD singles.',
  'Check the back cover for "Radio Edit," "Club Mix," or "Extended Version" -- Eurodance singles frequently packed several different mixes onto one release, and collectors often care which one they are actually getting.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Rock',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Rock is less one genre than a family tree -- knowing the branches helps you know what you are actually collecting.',
  E'Rock traces back to the 1950s, growing out of rhythm and blues, country, and gospel, with electric guitar as its throughline. From there it split constantly: the British Invasion and garage rock in the 1960s, hard rock and progressive rock in the 1970s, punk as a direct reaction against rock''s growing excess, then new wave, metal, alternative, and grunge across the 1980s and 1990s. Each branch has its own sound, scene, and collector culture, which is why "I collect rock" usually means something much more specific once you get into it.\n\nBecause the rock era overlaps almost entirely with the vinyl era, it is one of the deepest and most document-rich genres for collectors -- pressing variations, promo copies, and regional releases are extensively cataloged for major rock acts, which is both a blessing (lots of reference material) and a trap (lots of room to overpay for a common pressing mistaken for a rare one).\n\nIf you are new to rock collecting, picking a decade or a specific scene (British Invasion, 1970s arena rock, 1990s alternative) is a much better starting point than trying to collect "rock" broadly.',
  'Before buying a rock pressing at a premium price, look up the catalog number -- rock reissues are extremely common, and a "rare" original is often actually a widely available later pressing.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: House',
  'Genre Education',
  'Everyone',
  'Beginner',
  'House music was born in Chicago clubs in the early 1980s and has shaped electronic dance music ever since.',
  E'House takes its name from Chicago''s Warehouse club, where DJs like Frankie Knuckles blended disco records with drum machines to keep dancefloors moving after disco''s mainstream backlash in the late 1970s. The core sound is built around a steady four-on-the-floor kick drum, a driving bassline, and repetitive, hypnotic loops meant for extended DJ mixing rather than radio play.\n\nFrom Chicago, house spread to Detroit (feeding into techno), New York (garage house, deep house), and the UK and Europe, where it fueled the acid house and rave scenes of the late 1980s. Decades later, the genre has splintered into dozens of subgenres -- deep house, tech house, tribal house, progressive house -- each with a different tempo, mood, and production style, but all sharing that same steady four-on-the-floor foundation.\n\nHouse collecting is heavily driven by 12-inch singles, since the genre was built for DJs mixing in clubs, not albums meant to be listened to start to finish at home.',
  'Look for "Original Mix," "Dub," and "Instrumental" versions on the same 12-inch -- DJs bought house records specifically for these different mixes, and a complete pressing usually has several.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Rap and Hip Hop',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Hip hop began as a culture built around DJing, MCing, breakdancing, and graffiti -- rap is the music that culture produced.',
  E'Hip hop culture traces back to the early 1970s in the Bronx, where DJs like DJ Kool Herc extended the instrumental "breaks" of funk and soul records for dancers, while MCs began rhyming over the beats. What started as live park-jam and block-party culture became a recorded genre by the late 1970s, and rap -- the music itself -- has been one of the most commercially dominant and stylistically fast-moving genres ever since.\n\nRap''s eras are usually described by region and decade: the boom-bap and golden age sound of late-1980s and early-1990s New York, the G-funk of early-1990s West Coast rap, the rise of Southern hip hop in the late 1990s and 2000s, and the trap-influenced sound that has dominated since the 2010s. Sampling is central to the genre''s history -- producers built beats from funk, soul, and jazz records, which is part of why crate-digging culture and hip hop collecting are so closely linked.\n\nBecause of that sampling history, collecting hip hop often overlaps with collecting the funk, soul, and jazz records that early producers sampled from.',
  'Promo-only 12-inch singles and instrumental/acapella versions are especially collectible in hip hop -- DJs and producers wanted those separated stems, and pressings weren''t always made available to the public.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Country',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Country music grew out of rural Southern and Appalachian folk traditions and has splintered into many distinct sounds since.',
  E'Country''s roots go back to the 1920s, when Appalachian folk, gospel, and blues traditions combined with early commercial recording to create a genre built around storytelling, string instruments, and plainspoken vocals. Nashville became its commercial center by the mid-20th century, but the genre has never been one single sound -- honky-tonk, bluegrass, the polished "Nashville Sound" of the 1950s-60s, outlaw country''s rougher 1970s reaction against that polish, and the pop-leaning country of recent decades are all meaningfully different from each other.\n\nOutlaw country in particular is a useful reference point for collectors: artists like Willie Nelson and Waylon Jennings pushed back against Nashville''s tightly controlled studio system in the 1970s, favoring rougher production and more personal songwriting, and that era has its own dedicated collector base distinct from mainstream Nashville releases.\n\nBecause country has such a long, continuous commercial history, original pressings, reissues, and greatest-hits compilations from the same era can look very similar -- reading the fine print matters.',
  'Check whether a country LP is a "Greatest Hits" or compilation release before assuming it is a studio album -- labels released a huge number of country compilations, and they are often mistaken for rarer original albums.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Reggae',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Reggae grew out of Jamaica''s ska and rocksteady scenes and carries deep cultural and political roots.',
  E'Reggae developed in Jamaica in the late 1960s, evolving out of the faster tempo of ska and the more relaxed rocksteady sound that followed it. Its defining feature is the rhythm: an emphasis on the off-beat guitar or piano "skank," a heavy, prominent bassline, and a generally slower, deeper groove than its predecessors. Reggae became inseparable from Rastafari culture and its themes of spirituality, resistance, and social justice, most famously carried worldwide by Bob Marley in the 1970s.\n\nJamaican studio culture produced an enormous number of singles built around shared "riddims" -- a single backing track that dozens of different artists and producers would record different vocals or instrumental versions over. This makes reggae collecting distinct: it is common and expected to own multiple records built on the exact same riddim, each valuable for a different vocalist or dub version rather than a unique backing track.\n\nDub -- stripped-down, effects-heavy instrumental remixes pioneered by engineers like King Tubby -- grew directly out of reggae studio culture and remains one of the genre''s most collected offshoots.',
  'Learn to recognize riddims, not just artists -- in reggae, the same instrumental backing track often appears across many different singles, and knowing the riddim helps you understand what you are actually looking at.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: R&B',
  'Genre Education',
  'Everyone',
  'Beginner',
  'R&B has meant several different things across seven decades -- knowing the era tells you what sound to expect.',
  E'Rhythm and blues started as a 1940s-50s catch-all term for Black popular music blending blues, jazz, and gospel, and it became the direct foundation for soul music in the 1960s and funk in the 1970s. By the 1980s and 1990s, "R&B" had shifted to describe a different thing: polished, vocal-driven music blending soul tradition with synthesizers, drum machines, and increasingly, hip hop production -- the sound most people associate with the term today.\n\nThat later era of R&B is closely tied to New Jack Swing (its own genre, but a major influence) and to the rise of vocal-group and solo artist-driven records through the 1990s and 2000s, with production shifting again toward hip hop-influenced beats as the decades went on.\n\nBecause the term covers such a long span, "R&B" on a record bin divider could mean a 1950s doo-wop single, a 1970s soul album, or a 1990s vocal group record -- always check the actual era and sound before assuming what you are getting.',
  'When a record is labeled "R&B," check the release year first -- the term describes very different sounds depending on whether it is from the 1950s, the 1970s, or the 1990s.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: New Jack Swing',
  'Genre Education',
  'Everyone',
  'Beginner',
  'New Jack Swing fused R&B vocals with hip hop drum programming and defined the sound of late-80s and early-90s R&B.',
  E'New Jack Swing emerged in the late 1980s, largely credited to producer Teddy Riley, who combined smooth R&B vocal arrangements with the hard, syncopated drum machine programming of hip hop. The result was a sound that felt both radio-polished and street-credible at the same time -- a bridge between traditional R&B vocal groups and the hip hop production style that would come to dominate R&B in the following decades.\n\nThe genre had a relatively short but intense commercial peak, roughly the late 1980s through the mid-1990s, and it shaped a huge amount of mainstream R&B and pop production during that window, well beyond the artists most directly associated with it.\n\nBecause New Jack Swing sits at the intersection of R&B and hip hop, records from this era are collected by fans of both genres, and its drum programming has continued to be referenced and sampled by producers long after the genre''s commercial peak passed.',
  'New Jack Swing is a relatively narrow window (roughly the late 1980s to mid-1990s) -- if you like the sound, search by that era specifically rather than just by artist, since many artists moved on to other styles afterward.',
  'Draft','No',now()::text,now()::text
);

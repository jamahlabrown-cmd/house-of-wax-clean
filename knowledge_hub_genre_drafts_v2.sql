-- House Of Wax Knowledge Hub -- Genre Education, revision pass
-- Replaces the 20 genre articles from the first three draft batches with
-- deeper, artist-rich versions that also include a representative YouTube
-- video per article (video_url), so readers get a visual + a track they
-- can choose to play -- no hosted/auto-playing copyrighted audio, no
-- hosted artist photos. YouTube's own licensing covers the embed.
--
-- SAFE TO RUN EVEN IF YOU NEVER RAN THE EARLIER BATCH SQL: this deletes
-- any existing Draft row with a matching title first, then inserts the
-- new version, so it works whether 0, some, or all of the earlier drafts
-- were loaded. Nothing published is touched.
--
-- NOTE ON VIDEO LINKS: most of these are confirmed official artist/label
-- channel uploads. Four are not clearly labeled "official" in search
-- results (Frankie Knuckles - Your Love, B.B. King - The Thrill Is Gone,
-- Mahalia Jackson - Precious Lord Take My Hand, Derrick May - Strings of
-- Life) -- these are flagged in a comment above each row. Spot-check
-- those four links yourself before publishing those specific articles.

delete from knowledge_posts where status='Draft' and title in (
  'Genre Spotlight: Eurodance','Genre Spotlight: Rock','Genre Spotlight: House',
  'Genre Spotlight: Rap and Hip Hop','Genre Spotlight: Country','Genre Spotlight: Reggae',
  'Genre Spotlight: R&B','Genre Spotlight: New Jack Swing','Genre Spotlight: Jazz',
  'Genre Spotlight: Blues','Genre Spotlight: Soul','Genre Spotlight: Funk',
  'Genre Spotlight: Metal','Genre Spotlight: Punk','Genre Spotlight: Latin Music',
  'Genre Spotlight: Afrobeat and Afrobeats','Genre Spotlight: Gospel',
  'Genre Spotlight: Techno','Genre Spotlight: Trance','Genre Spotlight: Drum and Bass'
);

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,video_url,status,featured,created_at,updated_at) values
(
  'Genre Spotlight: Eurodance',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Fast, synthetic, and built for the dancefloor -- Eurodance defined a specific stretch of the 1990s.',
  E'Eurodance grew out of late-1980s and early-1990s European club culture, blending high-BPM electronic production with pop songwriting and, often, a rapped verse paired with a sung, anthemic chorus. Sweden''s Ace of Base became one of the genre''s biggest commercial breakouts with "The Sign" and "All That She Wants," while Germany''s Snap! ("Rhythm Is a Dancer") and 2 Unlimited ("No Limit," "Get Ready for This") pushed the sound into arenas and stadiums worldwide. Real McCoy, La Bouche, and Corona filled out the genre''s mid-90s commercial peak with tracks like "Another Night" and "The Rhythm of the Night."\n\nThe genre leaned heavily on synthesizers and drum machines rather than live instrumentation, which made it cheap to produce and easy to export across borders -- a big reason it spread so fast across Germany, the Netherlands, Sweden, and beyond before crossing to US radio and clubs. Vocals were frequently split between a rapper and a featured singer, a structure that became something of a Eurodance signature.\n\nCollecting Eurodance means paying attention to regional pressings -- the same single often had different mixes released in different countries, and 12-inch club mixes can differ significantly from the radio edit found on CD singles.',
  'Check the back cover for "Radio Edit," "Club Mix," or "Extended Version" -- Eurodance singles frequently packed several different mixes onto one release, and collectors often care which one they are actually getting.',
  'https://www.youtube.com/watch?v=iqu132vTl5Y',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Rock',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Rock is less one genre than a family tree -- knowing the branches helps you know what you are actually collecting.',
  E'Rock traces back to the 1950s, growing out of rhythm and blues, country, and gospel, with pioneers like Chuck Berry and Elvis Presley putting electric guitar and a driving backbeat at the center of popular music. From there it split constantly: the British Invasion brought The Beatles and The Rolling Stones to American radio in the 1960s, while hard rock and progressive rock in the 1970s produced Led Zeppelin and Pink Floyd. Punk arrived as a direct reaction against that growing excess, and grunge -- led by Nirvana in the early 1990s -- reacted against the polish of 1980s arena rock in turn.\n\nEach branch has its own sound, scene, and collector culture, which is why "I collect rock" usually means something much more specific once you get into it -- a Beatles collector and a Nirvana collector are chasing very different things.\n\nBecause the rock era overlaps almost entirely with the vinyl era, it is one of the deepest and most document-rich genres for collectors -- pressing variations, promo copies, and regional releases are extensively cataloged for major rock acts, which is both a blessing (lots of reference material) and a trap (lots of room to overpay for a common pressing mistaken for a rare one).',
  'Before buying a rock pressing at a premium price, look up the catalog number -- rock reissues are extremely common, and a "rare" original is often actually a widely available later pressing.',
  'https://www.youtube.com/watch?v=hTWKbfoikeg',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: House',
  'Genre Education',
  'Everyone',
  'Beginner',
  'House music was born in Chicago clubs in the early 1980s and has shaped electronic dance music ever since.',
  E'House takes its name from Chicago''s Warehouse club, where resident DJ Frankie Knuckles blended disco records with drum machines to keep dancefloors moving after disco''s mainstream backlash in the late 1970s. Producers like Larry Heard (recording as Mr. Fingers) and Marshall Jefferson, whose "Move Your Body" is often called the genre''s first true house anthem, helped codify the sound in the mid-1980s. The core formula is built around a steady four-on-the-floor kick drum, a driving bassline, and repetitive, hypnotic loops meant for extended DJ mixing rather than radio play.\n\nFrom Chicago, house spread to Detroit (feeding into techno), New York (garage house, deep house, with producers like Kerri Chandler carrying that sound forward), and the UK and Europe, where it fueled the acid house and rave scenes of the late 1980s.\n\nHouse collecting is heavily driven by 12-inch singles, since the genre was built for DJs mixing in clubs, not albums meant to be listened to start to finish at home.',
  'Look for "Original Mix," "Dub," and "Instrumental" versions on the same 12-inch -- DJs bought house records specifically for these different mixes, and a complete pressing usually has several.',
  'https://www.youtube.com/watch?v=LOLE1YE_oFQ',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Rap and Hip Hop',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Hip hop began as a culture built around DJing, MCing, breakdancing, and graffiti -- rap is the music that culture produced.',
  E'Hip hop culture traces back to the early 1970s in the Bronx, where DJs like DJ Kool Herc extended the instrumental "breaks" of funk and soul records for dancers, while MCs began rhyming over the beats. Grandmaster Flash and the Furious Five''s "The Message" (1982) is widely considered the moment rap proved it could carry serious social commentary, not just party rhymes, and Run-DMC brought the genre into the rock mainstream later that decade.\n\nRap''s eras are usually described by region and decade: the boom-bap and golden age sound of late-1980s and early-1990s New York (Public Enemy, Nas), the G-funk of early-1990s West Coast rap (Dr. Dre, Snoop Dogg), the rise of Southern hip hop with groups like OutKast in the late 1990s and 2000s, and the trap-influenced sound that has dominated since the 2010s. Sampling is central to the genre''s history -- producers built beats from funk, soul, and jazz records, which is part of why crate-digging culture and hip hop collecting are so closely linked.\n\nBecause of that sampling history, collecting hip hop often overlaps with collecting the funk, soul, and jazz records that early producers sampled from.',
  'Promo-only 12-inch singles and instrumental/acapella versions are especially collectible in hip hop -- DJs and producers wanted those separated stems, and pressings weren''t always made available to the public.',
  'https://www.youtube.com/watch?v=gYMkEMCHtJ4',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Country',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Country music grew out of rural Southern and Appalachian folk traditions and has splintered into many distinct sounds since.',
  E'Country''s roots go back to the 1920s, when Appalachian folk, gospel, and blues traditions combined with early commercial recording to create a genre built around storytelling, string instruments, and plainspoken vocals -- Hank Williams became one of its first true superstars in the late 1940s and early 1950s. Nashville became the genre''s commercial center by the mid-20th century, but the genre has never been one single sound: honky-tonk, bluegrass, the polished "Nashville Sound," outlaw country''s rougher 1970s reaction against that polish (Willie Nelson, Waylon Jennings), and the pop-leaning country of recent decades are all meaningfully different from each other.\n\nJohnny Cash and Dolly Parton both spent careers moving between and beyond those categories -- Cash''s outlaw-adjacent, gospel-influenced sound and Parton''s crossover into pop are reminders that "country" covers a lot of ground.\n\nBecause country has such a long, continuous commercial history, original pressings, reissues, and greatest-hits compilations from the same era can look very similar -- reading the fine print matters.',
  'Check whether a country LP is a "Greatest Hits" or compilation release before assuming it is a studio album -- labels released a huge number of country compilations, and they are often mistaken for rarer original albums.',
  'https://www.youtube.com/watch?v=FwiYC0SsQIc',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Reggae',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Reggae grew out of Jamaica''s ska and rocksteady scenes and carries deep cultural and political roots.',
  E'Reggae developed in Jamaica in the late 1960s, evolving out of the faster tempo of ska and the more relaxed rocksteady sound that followed it -- artists like Toots and the Maytals and Jimmy Cliff helped carry that transition. Its defining feature is the rhythm: an emphasis on the off-beat guitar or piano "skank," a heavy, prominent bassline, and a generally slower, deeper groove. Reggae became inseparable from Rastafari culture and its themes of spirituality and resistance, most famously carried worldwide by Bob Marley and the Wailers.\n\nJamaican studio culture produced an enormous number of singles built around shared "riddims" -- a single backing track that dozens of different artists and producers would record different vocals or instrumental versions over. This makes reggae collecting distinct: it is common and expected to own multiple records built on the exact same riddim.\n\nDub -- stripped-down, effects-heavy instrumental remixes pioneered by engineers like King Tubby and Lee "Scratch" Perry -- grew directly out of reggae studio culture and remains one of the genre''s most collected offshoots.',
  'Learn to recognize riddims, not just artists -- in reggae, the same instrumental backing track often appears across many different singles, and knowing the riddim helps you understand what you are actually looking at.',
  'https://www.youtube.com/watch?v=HNBCVM4KbUM',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: R&B',
  'Genre Education',
  'Everyone',
  'Beginner',
  'R&B has meant several different things across seven decades -- knowing the era tells you what sound to expect.',
  E'Rhythm and blues started as a 1940s-50s catch-all term for Black popular music blending blues, jazz, and gospel, and it became the direct foundation for soul music in the 1960s -- Aretha Franklin''s "Respect" is one of the era''s definitive statements. By the 1980s and 1990s, "R&B" had shifted to describe a different thing: polished, vocal-driven music blending soul tradition with synthesizers, drum machines, and increasingly, hip hop production, carried by artists like Whitney Houston, Boyz II Men, and Mary J. Blige -- the sound most people associate with the term today.\n\nThat later era of R&B is closely tied to New Jack Swing and to the rise of vocal-group and solo artist-driven records through the 1990s and 2000s, with production shifting again toward hip hop-influenced beats as the decades went on.\n\nBecause the term covers such a long span, "R&B" on a record bin divider could mean a 1950s doo-wop single, a 1960s soul album, or a 1990s vocal group record -- always check the actual era and sound before assuming what you are getting.',
  'When a record is labeled "R&B," check the release year first -- the term describes very different sounds depending on whether it is from the 1950s, the 1970s, or the 1990s.',
  'https://www.youtube.com/watch?v=U0yIf9Tkgu4',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: New Jack Swing',
  'Genre Education',
  'Everyone',
  'Beginner',
  'New Jack Swing fused R&B vocals with hip hop drum programming and defined the sound of late-80s and early-90s R&B.',
  E'New Jack Swing emerged in the late 1980s, largely credited to producer Teddy Riley, who combined smooth R&B vocal arrangements with the hard, syncopated drum machine programming of hip hop. Bobby Brown''s "My Prerogative" and groups like Bell Biv DeVoe and Guy (Riley''s own group) defined the genre''s commercial peak, bridging traditional R&B vocal groups and the hip hop production style that would come to dominate R&B in the following decades.\n\nThe genre had a relatively short but intense commercial run, roughly the late 1980s through the mid-1990s, and it shaped a huge amount of mainstream R&B and pop production during that window, well beyond the artists most directly associated with it.\n\nBecause New Jack Swing sits at the intersection of R&B and hip hop, records from this era are collected by fans of both genres, and its drum programming has continued to be referenced and sampled by producers long after the genre''s commercial peak passed.',
  'New Jack Swing is a relatively narrow window (roughly the late 1980s to mid-1990s) -- if you like the sound, search by that era specifically rather than just by artist, since many artists moved on to other styles afterward.',
  'https://www.youtube.com/watch?v=5cDLZqe735k',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Jazz',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Jazz is built on improvisation -- and its decades of reinvention are exactly what make it so deep to collect.',
  E'Jazz emerged in New Orleans in the early 1900s, blending blues, ragtime, and brass band traditions into a music defined by improvisation and swung rhythm, with Louis Armstrong among its first true stars. From there it moved through the big band swing era led by figures like Duke Ellington, then splintered hard: bebop in the mid-1940s (Charlie Parker, Dizzy Gillespie) stripped the music down to small, fast, harmonically complex combos as a direct reaction against swing''s commercial dance-band constraints. Cool jazz, hard bop, and modal jazz followed through the 1950s and 1960s, with Miles Davis and John Coltrane alone moving through several of these eras themselves.\n\nBecause improvisation is central to the genre, the same jazz standard can sound completely different from one recording to the next -- unlike a pop song, the "definitive version" of a jazz piece is often genuinely up for debate.\n\nLabel and pressing details matter enormously in jazz collecting. Blue Note, Impulse!, Prestige, and Verve are considered prestige labels with dedicated collector followings, and for many original jazz pressings, whether a copy is mono or stereo, and which specific pressing run it came from, can meaningfully change both the sound and the value.',
  'Learn to recognize a handful of jazz label logos on sight (Blue Note, Impulse!, Prestige) -- the label alone tells you a lot about the era and style before you even read the back cover.',
  'https://www.youtube.com/watch?v=rBrd_3VMC3c',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Blues',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Blues is the root system underneath most American popular music -- rock, soul, and R&B all grow out of it.',
  E'Blues developed in the rural American South in the late 1800s and early 1900s, growing out of African American work songs, spirituals, and field hollers. Its foundation -- the 12-bar structure, call-and-response phrasing, and bent, expressive "blue notes" -- became one of the most influential musical templates of the 20th century. Early blues was largely acoustic and regional: the raw, guitar-driven Mississippi Delta sound of Robert Johnson is one well-known strand, but Piedmont blues, Texas blues, and other regional styles all developed with their own distinct character.\n\nThe Great Migration carried blues north through the early-to-mid 20th century, and in Chicago it went electric: amplified guitar, harmonica, and full rhythm sections turned rural acoustic blues into the harder, louder urban blues sound of Muddy Waters and Howlin'' Wolf, much of it recorded for Chess Records. B.B. King carried that electric blues tradition into the following decades and became one of the genre''s most recognized global ambassadors.\n\nBlues collecting spans an enormous range, from extremely rare and valuable pre-war 78 rpm singles to widely available electric blues LPs from the 1960s onward -- knowing roughly which era and region you are looking at changes what you should expect to pay.',
  'Pre-war blues 78s are a completely different collecting world than postwar electric blues LPs -- if a seller calls something "rare blues," ask what era and format before assuming it is valuable.',
  'https://www.youtube.com/watch?v=oica5jG7FpU',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Soul',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Soul took gospel''s emotional intensity and R&B''s rhythm and turned it into one of the defining sounds of the 1960s.',
  E'Soul music emerged in the late 1950s and 1960s as gospel''s vocal power and emotional directness merged with rhythm and blues. It quickly split into distinct regional sounds that collectors still treat as separate categories: Motown, out of Detroit, favored polished, pop-oriented production behind artists like Smokey Robinson and Marvin Gaye, while Southern soul out of Stax Records in Memphis leaned grittier and more gospel-rooted, carried by Otis Redding and the duo Sam & Dave. Philadelphia soul arrived a bit later with lush, orchestral production that helped pave the way toward disco.\n\nSoul was deeply tied to its cultural moment -- the genre rose alongside the civil rights movement, and many soul records carried that context directly in their lyrics and performance, not just their sound.\n\nOne of the more unusual corners of soul collecting is Northern Soul, a UK phenomenon where collectors and DJs sought out obscure, often commercially unsuccessful American soul 45s specifically for their driving tempo and danceability -- turning overlooked US singles into highly valuable, sought-after import records decades later.',
  'Pay attention to the label name on soul 45s and LPs (Motown, Stax, Atlantic, Hi Records) -- in soul collecting, the label is often as strong a signal of sound and era as the artist name.',
  'https://www.youtube.com/watch?v=rTVjnBo96Ug',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Funk',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Funk stripped soul down to its rhythm section and built a groove-first genre that hip hop would later sample endlessly.',
  E'Funk grew directly out of soul in the mid-to-late 1960s, led largely by James Brown, who shifted the emphasis away from melody and toward rhythm -- famously "the one," a hard downbeat emphasis that turned the rhythm section itself into the star of the record. Syncopated basslines, tight horn sections, and extended, repetitive grooves replaced the verse-chorus song structure that dominated most other popular music of the era.\n\nGeorge Clinton''s Parliament-Funkadelic collective pushed funk in a more psychedelic, theatrical direction through the 1970s, while Sly and the Family Stone brought funk''s rhythmic ideas into a more integrated rock-and-soul sound that crossed over to mainstream radio. Funk''s influence stretched far beyond its own commercial era -- its basslines, drum breaks, and horn stabs became some of the single most sampled material in hip hop production starting in the late 1970s and continuing for decades after.\n\nBecause of that sampling history, funk collecting overlaps heavily with hip hop crate-digging culture. Obscure, small-label 45s that went nowhere commercially in the 1970s can command serious premiums today if they contain a drum break or bassline that producers and DJs have sought out.',
  'If a funk 45 has a stripped-down instrumental break in the middle, that is often exactly what made it valuable to sample-digging collectors -- check for "breakbeat" mentions before assuming an obscure single has no value.',
  'https://www.youtube.com/watch?v=XaNNPf1NqEk',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Metal',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Metal turned hard rock''s volume and darkness into a genre of its own, then kept splintering into faster and heavier offshoots.',
  E'Metal is generally traced to the late 1960s and early 1970s, with Black Sabbath often credited as the band that turned heavy, distorted, minor-key hard rock into something distinct from blues-based rock and roll. The genre spent the following decades constantly subdividing: the New Wave of British Heavy Metal in the late 1970s and early 1980s (Iron Maiden, Judas Priest) sharpened the sound and imagery, thrash metal in the 1980s (Metallica, Slayer) pushed tempo and aggression further, and death metal, black metal, and other extreme subgenres pushed further still through the 1980s and 1990s.\n\nEach metal subgenre tends to come with its own scene, visual identity, and collector culture, often more tightly knit and self-organized than mainstream rock -- independent labels, limited pressings, and tape-trading networks have historically been central to how metal spread, especially for its more extreme offshoots.\n\nMetal collecting today is heavily shaped by limited-run releases: colored vinyl variants, small pressing numbers, and label-specific editions are common practice in modern metal, which makes original pressings of foundational albums, and early independent-label releases especially, highly sought after.',
  'For extreme metal subgenres especially, check the pressing count and label -- small, independent-label runs are common, and knowing whether a copy is an original pressing versus a later reissue changes its value significantly.',
  'https://www.youtube.com/watch?v=0qanF-91aJo',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Punk',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Punk was a direct reaction against rock''s growing excess -- stripped down, fast, and built on a do-it-yourself ethic.',
  E'Punk emerged in the mid-1970s as a backlash against the increasingly polished, elaborate production of mainstream and progressive rock. The music itself stayed deliberately simple: short songs, fast tempos, minimal solos, and direct, often confrontational lyrics. Two scenes developed roughly in parallel with distinct character -- New York''s scene around bands like the Ramones (whose "Blitzkrieg Bop" became one of the genre''s signature anthems) leaned art-school and deadpan, while the UK scene around the Sex Pistols and The Clash carried more explicit class and political anger.\n\nThe genre''s do-it-yourself ethic was not just an attitude but a practical model: punk bands frequently recorded, pressed, and distributed their own 7-inch singles through independent labels rather than waiting on major-label deals, which is part of why so much punk history exists on small, self-released pressings rather than big commercial releases.\n\nHardcore punk emerged in the early 1980s as an even faster, more aggressive offshoot, largely built around independent scenes in cities across the US and UK. Because of punk''s independent, self-released roots, collecting the genre often means collecting DIY culture itself -- original 7-inch singles, hand-assembled sleeves, and scene ephemera like flyers and zines alongside the records.',
  'A lot of punk history exists only on small, independent 7-inch pressings -- if a punk record feels handmade or DIY, that is not a flaw, it is often exactly the point.',
  'https://www.youtube.com/watch?v=268C3N2dDYk',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Latin Music',
  'Genre Education',
  'Everyone',
  'Beginner',
  '"Latin music" is really a family of distinct national and regional traditions -- knowing the country tells you a lot about the sound.',
  E'"Latin music" covers an enormous range of distinct styles rooted in different countries and traditions: Cuban son and mambo, Puerto Rican and Nuyorican salsa, Dominican merengue and bachata, Colombian cumbia, Brazilian samba and bossa nova, and many more, each with its own rhythms, instrumentation, and history. Most of these traditions share roots in a mix of African rhythmic influence (carried through the Caribbean and Latin America via the slave trade), Spanish or Portuguese colonial musical tradition, and regional indigenous influence.\n\nSalsa, one of the most internationally recognized Latin genres, actually crystallized in New York City in the 1960s and 1970s, as Cuban son and related Afro-Cuban styles mixed with jazz in a scene led by Puerto Rican and Cuban musicians -- Celia Cruz, often called the "Queen of Salsa," and bandleader Tito Puente became two of the genre''s most enduring global figures, both closely associated with Fania Records, the label that defined the genre''s commercial peak.\n\nBecause "Latin" spans so many distinct national traditions, collecting it well usually means picking a country or specific style (Cuban son, Brazilian bossa nova, Colombian cumbia) to go deep on, rather than treating it as one broad category.',
  'When a record is labeled simply "Latin," check the country and specific style before assuming what you are getting -- Cuban son, Brazilian bossa nova, and Colombian cumbia sound very different from each other.',
  'https://www.youtube.com/watch?v=TAyX1O_xKhU',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Afrobeat and Afrobeats',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Afrobeat and Afrobeats are two different genres that share a name and a West African home -- worth knowing the difference.',
  E'Afrobeat, without the "s," refers to the genre pioneered by Nigerian musician Fela Kuti in the late 1960s and 1970s, blending jazz, funk, highlife, and traditional Yoruba music into long, politically charged, horn-driven compositions like "Zombie." It was explicitly political -- Fela Kuti used the music to criticize corruption and military rule in Nigeria, and the genre carries that activist history as part of its identity.\n\nAfrobeats, with the "s," is a different and more recent genre: a contemporary West African pop sound that emerged in the 2000s and 2010s, blending hip hop, dancehall, highlife, and other influences into a more commercially oriented, radio- and streaming-friendly style. Artists like Burna Boy, Wizkid, and Davido have carried Afrobeats to a massive global audience in the 21st century. It shares regional roots and some sonic DNA with Afrobeat, but it is a distinct genre with a different sound, era, and purpose.\n\nBecause the names are so close, sellers and buyers alike sometimes use them interchangeably -- worth double-checking which one a record or artist actually belongs to before assuming.',
  'Afrobeat (Fela Kuti-era, 1970s, political, jazz/funk-rooted) and Afrobeats (2000s-present, pop-oriented) are genuinely different genres despite the near-identical name -- always confirm which one you are looking at.',
  'https://www.youtube.com/watch?v=G2y_MUborpk',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Gospel',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Gospel is the root of soul, and its call-and-response tradition still echoes through most Black American popular music.',
  E'Gospel music grew out of the African American church tradition, combining spirituals, hymns, and the call-and-response structure long used in Black worship into a distinct recorded genre by the early-to-mid 20th century. Gospel quartets and powerful solo vocalists -- Mahalia Jackson, whose recording of "Take My Hand, Precious Lord" remains one of the genre''s best-known performances, is among the most famous -- built a tradition centered on vocal power, emotional testimony, and communal participation between singer and audience.\n\nGospel''s relationship to soul music is direct rather than just influential: many soul singers trained and performed in gospel churches and choirs before crossing into secular music, carrying gospel''s vocal techniques and emotional intensity with them. Sam Cooke''s move from gospel group the Soul Stirrers into secular soul music in the late 1950s is one of the clearest, most documented examples of that crossover.\n\nGospel collecting includes both major-label recordings by well-known artists and a huge body of regional, small-label, and church-affiliated releases -- local choirs and quartets recorded and pressed records independently across the country, which means there is a large and still-being-discovered body of regional gospel to explore.',
  'Regional and church-affiliated gospel labels produced a huge amount of material that never got wide distribution -- some of the most interesting gospel collecting is in small-label, local releases rather than major-label artists.',
  'https://www.youtube.com/watch?v=as1rsZenwNc',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Techno',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Techno was born in Detroit, not Europe -- a fact that surprises a lot of people given how associated the genre became with Berlin.',
  E'Techno emerged in Detroit in the mid-1980s, pioneered by Juan Atkins, Derrick May, and Kevin Saunderson -- often called the Belleville Three. Derrick May''s "Strings of Life," released under the name Rhythim is Rhythim, is one of the genre''s foundational tracks. Drawing heavily on the mechanical, futuristic sound of German group Kraftwerk along with funk and electro influences, Detroit techno favored a more stripped-down, repetitive, machine-driven sound than the disco-rooted warmth of Chicago house, even though the two genres developed around the same time and are frequently mentioned together.\n\nTechno found a massive audience in Europe, especially in Berlin, where the genre became closely tied to the city''s club culture, particularly after the fall of the Berlin Wall gave rise to a wave of new clubs and parties built around the sound. That European scene grew so large that many people now associate techno with Berlin first, even though its origins are unambiguously Detroit.\n\nTechno collecting prizes original Detroit-label pressings from the genre''s founding years, along with the white-label 12-inch singles that were central to how DJs discovered and played new tracks in clubs before wider release.',
  'When you hear "Detroit techno" versus "Berlin techno," that is a real distinction worth learning -- same broad genre, different scenes, eras, and sound.',
  'https://www.youtube.com/watch?v=YkboRsdt9tg',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Trance',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Trance is built around the build-up and the drop -- a genre engineered for a specific emotional peak on the dancefloor.',
  E'Trance developed in Germany in the early-to-mid 1990s as an offshoot of techno and house, distinguished by its emphasis on melody, atmosphere, and a clear emotional arc within each track. Where techno often stays repetitive and mechanical, trance is built around long, layered build-ups that release into a euphoric "drop" or climax -- a structure specifically designed to create a shared emotional peak on a packed dancefloor. Paul van Dyk''s "For An Angel" is one of the genre''s defining anthems and helped bring trance to a much wider audience in the late 1990s.\n\nThe genre grew alongside a strong DJ-driven club and festival culture through the late 1990s and 2000s, with producers and DJs like van Dyk, Armin van Buuren, and Tiesto becoming genre-defining figures largely through their live sets and mix compilations as much as individual singles.\n\nBecause trance is so tied to the DJ mix format, collecting the genre often means collecting mix CDs and 12-inch club pressings intended for beatmatching and extended sets, rather than albums meant to be played straight through at home.',
  'Trance tracks are often released as extended club mixes specifically for DJ use -- the radio edit and the full club mix can be meaningfully different lengths and structures on the same release.',
  'https://www.youtube.com/watch?v=1BUk1q-NKtY',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Drum and Bass',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Drum and bass grew out of the UK rave scene and carries a deep debt to Jamaican soundsystem culture.',
  E'Drum and bass (also called jungle in its early years) emerged in the UK in the early 1990s, evolving out of the breakbeat hardcore rave scene as producers pushed tempos faster and leaned harder into chopped, resampled breakbeats and heavy sub-bass. Goldie''s "Inner City Life" (1995) is one of the genre''s most celebrated tracks and helped bring drum and bass to a mainstream audience. The result was a genre that typically runs around 160 to 180 beats per minute, built on rapid, intricate drum programming paired with deep, dub-influenced basslines.\n\nThat bass emphasis is not incidental -- drum and bass owes a direct debt to Jamaican soundsystem and dub culture, carried into the UK through its large Caribbean diaspora communities, particularly in London. The genre''s focus on powerful, physical bass is a direct continuation of that soundsystem tradition, filtered through breakbeat and rave production techniques.\n\nDrum and bass culture developed heavily around pirate radio stations, white-label 12-inch singles, and London-centric club nights, especially in its formative years, which is part of why early jungle and drum and bass records can be difficult to trace and identify -- many were pressed in small runs with minimal label information.',
  'Early jungle and drum and bass white labels often carry minimal or no printed information -- if a 12-inch looks unmarked or handwritten, that was normal for the scene, not necessarily a bootleg.',
  'https://www.youtube.com/watch?v=i-P98B2skts',
  'Draft','No',now()::text,now()::text
);

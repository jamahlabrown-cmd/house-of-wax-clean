-- House Of Wax Knowledge Hub -- Genre Education draft batch 3
-- Inserts 8 new articles as Draft status. They will NOT appear publicly
-- until reviewed and published from Content Admin > Article Library.
-- Safe to run once; re-running will create duplicate rows (titles are not unique).

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) values
(
  'Genre Spotlight: Metal',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Metal turned hard rock''s volume and darkness into a genre of its own, then kept splintering into faster and heavier offshoots.',
  E'Metal is generally traced to the late 1960s and early 1970s, with Black Sabbath often credited as the band that turned heavy, distorted, minor-key hard rock into something distinct from blues-based rock and roll. The genre spent the following decades constantly subdividing: the New Wave of British Heavy Metal in the late 1970s and early 1980s (Iron Maiden, Judas Priest) sharpened the sound and imagery, thrash metal in the 1980s (Metallica, Slayer) pushed tempo and aggression further, and death metal, black metal, and other extreme subgenres pushed further still through the 1980s and 1990s.\n\nEach metal subgenre tends to come with its own scene, visual identity, and collector culture, often more tightly knit and self-organized than mainstream rock -- independent labels, limited pressings, and tape-trading networks have historically been central to how metal spread, especially for its more extreme offshoots.\n\nMetal collecting today is heavily shaped by limited-run releases: colored vinyl variants, small pressing numbers, and label-specific editions are common practice in modern metal, which makes original pressings of foundational albums, and early independent-label releases especially, highly sought after.',
  'For extreme metal subgenres especially, check the pressing count and label -- small, independent-label runs are common, and knowing whether a copy is an original pressing versus a later reissue changes its value significantly.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Punk',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Punk was a direct reaction against rock''s growing excess -- stripped down, fast, and built on a do-it-yourself ethic.',
  E'Punk emerged in the mid-1970s as a backlash against the increasingly polished, elaborate production of mainstream and progressive rock. The music itself stayed deliberately simple: short songs, fast tempos, minimal solos, and direct, often confrontational lyrics. Two scenes developed roughly in parallel with distinct character -- New York''s scene around bands like the Ramones leaned art-school and deadpan, while the UK scene around the Sex Pistols and The Clash carried more explicit class and political anger.\n\nThe genre''s do-it-yourself ethic was not just an attitude but a practical model: punk bands frequently recorded, pressed, and distributed their own 7-inch singles through independent labels rather than waiting on major-label deals, which is part of why so much punk history exists on small, self-released pressings rather than big commercial releases.\n\nHardcore punk emerged in the early 1980s as an even faster, more aggressive offshoot, largely built around independent scenes in cities across the US and UK. Because of punk''s independent, self-released roots, collecting the genre often means collecting DIY culture itself -- original 7-inch singles, hand-assembled sleeves, and scene ephemera like flyers and zines alongside the records.',
  'A lot of punk history exists only on small, independent 7-inch pressings -- if a punk record feels handmade or DIY, that is not a flaw, it is often exactly the point.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Latin Music',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Latin music is really a family of distinct national and regional traditions -- knowing the country tells you a lot about the sound.',
  E'"Latin music" covers an enormous range of distinct styles rooted in different countries and traditions: Cuban son and mambo, Puerto Rican and Nuyorican salsa, Dominican merengue and bachata, Colombian cumbia, Brazilian samba and bossa nova, and many more, each with its own rhythms, instrumentation, and history. Most of these traditions share roots in a mix of African rhythmic influence (carried through the Caribbean and Latin America via the slave trade), Spanish or Portuguese colonial musical tradition, and regional indigenous influence, combined in different proportions depending on the country.\n\nSalsa, one of the most internationally recognized Latin genres, actually crystallized in New York City in the 1960s and 1970s, as Cuban son and related Afro-Cuban styles mixed with jazz in a scene led by Puerto Rican and Cuban musicians in the city -- Fania Records became the genre''s defining commercial label during this period.\n\nBecause "Latin" spans so many distinct national traditions, collecting it well usually means picking a country or specific style (Cuban son, Brazilian bossa nova, Colombian cumbia) to go deep on, rather than treating it as one broad category.',
  'When a record is labeled simply "Latin," check the country and specific style before assuming what you are getting -- Cuban son, Brazilian bossa nova, and Colombian cumbia sound very different from each other.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Afrobeat and Afrobeats',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Afrobeat and Afrobeats are two different genres that share a name and a West African home -- worth knowing the difference.',
  E'Afrobeat, without the "s," refers to the genre pioneered by Nigerian musician Fela Kuti in the late 1960s and 1970s, blending jazz, funk, highlife, and traditional Yoruba music into long, politically charged, horn-driven compositions. It was explicitly political -- Fela Kuti used the music to criticize corruption and military rule in Nigeria, and the genre carries that activist history as part of its identity.\n\nAfrobeats, with the "s," is a different and more recent genre: a contemporary West African pop sound that emerged in the 2000s and 2010s, blending hip hop, dancehall, highlife, and other influences into a more commercially oriented, radio- and streaming-friendly style that has become hugely popular globally in the 21st century. It shares regional roots and some sonic DNA with Afrobeat, but it is a distinct genre with a different sound, era, and purpose.\n\nBecause the names are so close, sellers and buyers alike sometimes use them interchangeably -- worth double-checking which one a record or artist actually belongs to before assuming.',
  'Afrobeat (Fela Kuti-era, 1970s, political, jazz/funk-rooted) and Afrobeats (2000s-present, pop-oriented) are genuinely different genres despite the near-identical name -- always confirm which one you are looking at.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Gospel',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Gospel is the root of soul, and its call-and-response tradition still echoes through most Black American popular music.',
  E'Gospel music grew out of the African American church tradition, combining spirituals, hymns, and the call-and-response structure long used in Black worship into a distinct recorded genre by the early-to-mid 20th century. Gospel quartets and powerful solo vocalists -- Mahalia Jackson is among the most famous -- built a tradition centered on vocal power, emotional testimony, and communal participation between singer and audience.\n\nGospel''s relationship to soul music is direct rather than just influential: many soul singers trained and performed in gospel churches and choirs before crossing into secular music, carrying gospel''s vocal techniques and emotional intensity with them. Sam Cooke''s move from gospel group the Soul Stirrers into secular soul music in the late 1950s is one of the clearest, most documented examples of that crossover.\n\nGospel collecting includes both major-label recordings by well-known artists and a huge body of regional, small-label, and church-affiliated releases -- local choirs and quartets recorded and pressed records independently across the country, which means there is a large and still-being-discovered body of regional gospel to explore.',
  'Regional and church-affiliated gospel labels produced a huge amount of material that never got wide distribution -- some of the most interesting gospel collecting is in small-label, local releases rather than major-label artists.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Techno',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Techno was born in Detroit, not Europe -- a fact that surprises a lot of people given how associated the genre became with Berlin.',
  E'Techno emerged in Detroit in the mid-1980s, pioneered by Juan Atkins, Derrick May, and Kevin Saunderson -- often called the Belleville Three. Drawing heavily on the mechanical, futuristic sound of German group Kraftwerk along with funk and electro influences, Detroit techno favored a more stripped-down, repetitive, machine-driven sound than the disco-rooted warmth of Chicago house, even though the two genres developed around the same time and are frequently mentioned together.\n\nTechno found a massive audience in Europe, especially in Berlin, where the genre became closely tied to the city''s club culture, particularly after the fall of the Berlin Wall gave rise to a wave of new clubs and parties built around the sound. That European scene grew so large that many people now associate techno with Berlin first, even though its origins are unambiguously Detroit.\n\nTechno collecting prizes original Detroit-label pressings from the genre''s founding years, along with the white-label 12-inch singles that were central to how DJs discovered and played new tracks in clubs before wider release.',
  'When you hear "Detroit techno" versus "Berlin techno," that is a real distinction worth learning -- same broad genre, different scenes, eras, and sound.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Trance',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Trance is built around the build-up and the drop -- a genre engineered for a specific emotional peak on the dancefloor.',
  E'Trance developed in Germany in the early-to-mid 1990s as an offshoot of techno and house, distinguished by its emphasis on melody, atmosphere, and a clear emotional arc within each track. Where techno often stays repetitive and mechanical, trance is built around long, layered build-ups that release into a euphoric "drop" or climax -- a structure specifically designed to create a shared emotional peak on a packed dancefloor.\n\nThe genre grew alongside a strong DJ-driven club and festival culture through the late 1990s and 2000s, with certain producers and DJs becoming genre-defining figures largely through their live sets and mix compilations as much as individual singles.\n\nBecause trance is so tied to the DJ mix format, collecting the genre often means collecting mix CDs and 12-inch club pressings intended for beatmatching and extended sets, rather than albums meant to be played straight through at home.',
  'Trance tracks are often released as extended club mixes specifically for DJ use -- the radio edit and the full club mix can be meaningfully different lengths and structures on the same release.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Drum and Bass',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Drum and bass grew out of the UK rave scene and carries a deep debt to Jamaican soundsystem culture.',
  E'Drum and bass (also called jungle in its early years) emerged in the UK in the early 1990s, evolving out of the breakbeat hardcore rave scene as producers pushed tempos faster and leaned harder into chopped, resampled breakbeats and heavy sub-bass. The result was a genre that typically runs around 160 to 180 beats per minute, built on rapid, intricate drum programming paired with deep, dub-influenced basslines.\n\nThat bass emphasis is not incidental -- drum and bass owes a direct debt to Jamaican soundsystem and dub culture, carried into the UK through its large Caribbean diaspora communities, particularly in London. The genre''s focus on powerful, physical bass is a direct continuation of that soundsystem tradition, filtered through breakbeat and rave production techniques.\n\nDrum and bass culture developed heavily around pirate radio stations, white-label 12-inch singles, and London-centric club nights, especially in its formative years, which is part of why early jungle and drum and bass records can be difficult to trace and identify -- many were pressed in small runs with minimal label information.',
  'Early jungle and drum and bass white labels often carry minimal or no printed information -- if a 12-inch looks unmarked or handwritten, that was normal for the scene, not necessarily a bootleg.',
  'Draft','No',now()::text,now()::text
);

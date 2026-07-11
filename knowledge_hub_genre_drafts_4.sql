-- House Of Wax Knowledge Hub -- Genre Education draft batch 4
-- Disco, K-pop, Indie/Alternative, Classical.
-- Inserts 4 new articles as Draft status, each with named artists
-- throughout and a representative official YouTube video via video_url.
-- Safe to run once; re-running will create duplicate rows (titles are not unique).

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,video_url,status,featured,created_at,updated_at) values
(
  'Genre Spotlight: Disco',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Disco grew out of underground club culture in the early 1970s and left behind the format DJs still use today: the 12-inch single.',
  E'Disco emerged in the early 1970s out of New York City''s underground club scene, rooted in Black, Latino, and gay communities and drawing on funk, soul, and Latin dance music. Its sound layered a steady four-on-the-floor beat under lush orchestral strings and horns -- Donna Summer''s "I Feel Love," produced by Giorgio Moroder with an entirely synthesized backing track, pushed the genre in a more electronic direction that would go on to influence house and techno. Chic, led by Nile Rodgers and Bernard Edwards, brought some of the genre''s most sophisticated musicianship, while Gloria Gaynor''s "I Will Survive" became one of disco''s defining anthems.\n\nThe genre crossed into full mainstream domination with the Bee Gees and the 1977 Saturday Night Fever soundtrack, but that same visibility fed a backlash -- most infamously "Disco Demolition Night" at Chicago''s Comiskey Park in 1979, where a stadium promotion to blow up disco records turned into a riot.\n\nDisco''s most lasting technical contribution to record collecting might be the 12-inch single itself: engineer Tom Moulton is widely credited with pioneering the extended dance remix pressed onto a 12-inch disc specifically for club DJs, a format that house, techno, and hip hop all inherited directly from disco club culture.',
  'If you find a 12-inch disco single labeled "Disco Mix" or "Extended Version," that longer, DJ-oriented format is part of what makes disco collecting distinct from collecting the same song''s 7-inch radio release.',
  'https://www.youtube.com/watch?v=TszOGKfugXk',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: K-pop',
  'Genre Education',
  'Everyone',
  'Beginner',
  'K-pop''s trainee-and-idol system and its distinctive physical album culture make it a genuinely different kind of collecting.',
  E'Modern K-pop is often traced to Seo Taiji and Boys, whose 1992 debut fused American hip hop and rock with Korean pop and is widely considered the starting point of the industry as it exists today. South Korean entertainment companies -- SM, YG, and JYP among the biggest -- built a distinctive "idol" system around it: performers train for years in vocals, dance, and performance before debuting in a group. Early groups like H.O.T. and S.E.S. built the template in the 1990s, and BoA carried it across Asia in the early 2000s.\n\nThe genre''s global breakthrough came in stages: Girls'' Generation and Wonder Girls expanded K-pop''s reach across Asia in the late 2000s, PSY''s "Gangnam Style" became the genre''s first true global viral moment in 2012, and BTS and BLACKPINK carried K-pop into the world''s biggest pop charts and stadiums through the 2010s and 2020s.\n\nK-pop physical album collecting looks different from most Western vinyl collecting: albums are often released in multiple cover "versions," bundled with photocards, posters, and other collectible inserts, closer in spirit to trading-card culture than traditional record collecting -- though dedicated vinyl releases for K-pop artists have grown as the genre''s global audience has.',
  'K-pop albums are frequently released in several different cover "versions" with different photocard inserts -- if you are collecting a specific release, check which version you are actually being offered.',
  'https://www.youtube.com/watch?v=cGc_NfiTxng',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Indie and Alternative Rock',
  'Genre Education',
  'Everyone',
  'Beginner',
  '"Alternative" describes a sound and a radio era; "indie" describes a way of releasing music -- the two overlap but are not the same thing.',
  E'"Alternative rock" emerged as a radio and marketing term in the 1980s for guitar-based rock that sat outside the mainstream pop charts, built largely through American college radio. R.E.M. and the UK''s The Smiths were among the defining voices of that 1980s college-rock era, and Nirvana''s Nevermind broke the alternative label into full mainstream visibility in 1991, pulling grunge and a wave of guitar bands onto mainstream radio and MTV alongside it.\n\n"Indie," by contrast, more precisely describes an independent-label, do-it-yourself approach to releasing music rather than one specific sound -- Pixies and Sonic Youth built underground reputations through independent labels in the 1980s and early 1990s, and a 2000s indie rock revival brought bands like The Strokes, Arctic Monkeys, and Vampire Weekend back into mainstream attention while staying rooted in that independent-label identity.\n\nBecause indie culture is built around specific labels as much as specific artists, collectors often follow labels themselves -- Merge, Matador, and Sub Pop each built distinct identities collectors track closely, and limited vinyl runs are common practice, a direct continuation of the genre''s small-label roots.',
  'In indie rock, the label can matter as much as the artist -- collectors often follow specific independent labels (Merge, Matador, Sub Pop) the way they might follow a band.',
  'https://www.youtube.com/watch?v=xwtdhWltSIg',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Classical Music',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Classical collecting is as much about who performed the piece as who composed it -- the same symphony can be a completely different record twice over.',
  E'"Classical music" spans centuries of distinct eras: the Baroque period (Bach, Vivaldi, roughly 1600-1750), the Classical period proper (Mozart, Haydn, roughly 1750-1820), the Romantic era that Beethoven''s later work helped usher in (followed by Chopin, Brahms, and Tchaikovsky through the 1800s), and 20th-century modern composers like Stravinsky who pushed the tradition further still.\n\nThe detail that most distinguishes classical collecting from other genres is that a recording is defined as much by its performer as its composer. Beethoven''s Symphony No. 5 conducted by Herbert von Karajan with the Berlin Philharmonic and the same symphony conducted by Leonard Bernstein with the New York Philharmonic are collected as genuinely different, distinct records -- the composition is identical, but the interpretation, tempo, and orchestral character can differ enormously.\n\nCertain labels built their reputations specifically around recording and mastering quality -- Deutsche Grammophon and Decca are two of the best known -- and classical collectors often prize a specific label''s pressing of a performance as much as the performance itself, since sound engineering quality varies significantly across releases of the same piece.',
  'When shopping for classical vinyl, the conductor and orchestra listed matter as much as the composer -- two pressings of "the same" symphony can be very different listening experiences.',
  'https://www.youtube.com/watch?v=9aDEq3u5huA',
  'Draft','No',now()::text,now()::text
);

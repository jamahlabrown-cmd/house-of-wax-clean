-- House Of Wax Knowledge Hub -- Genre Education draft batch 2
-- Inserts 4 new articles as Draft status. They will NOT appear publicly
-- until reviewed and published from Content Admin > Article Library.
-- Safe to run once; re-running will create duplicate rows (titles are not unique).

insert into knowledge_posts (title,category,audience,level,summary,body,house_tip,status,featured,created_at,updated_at) values
(
  'Genre Spotlight: Jazz',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Jazz is built on improvisation -- and its decades of reinvention are exactly what make it so deep to collect.',
  E'Jazz emerged in New Orleans in the early 1900s, blending blues, ragtime, and brass band traditions into a music defined by improvisation and swung rhythm. From there it moved through the big band swing era of the 1930s and 1940s, then splintered hard: bebop in the mid-1940s (Charlie Parker, Dizzy Gillespie) stripped the music down to small, fast, harmonically complex combos as a direct reaction against swing''s commercial dance-band constraints. Cool jazz, hard bop, and modal jazz followed through the 1950s and 1960s, with Miles Davis alone moving through several of these eras himself.\n\nBecause improvisation is central to the genre, the same jazz standard can sound completely different from one recording to the next -- unlike a pop song, the "definitive version" of a jazz piece is often genuinely up for debate. That is part of why jazz collectors care so much about specific sessions, personnel, and dates, not just the song title.\n\nLabel and pressing details matter enormously in jazz collecting. Blue Note, Impulse!, Prestige, and Verve are considered prestige labels with dedicated collector followings, and for many original jazz pressings, whether a copy is mono or stereo, and which specific pressing run it came from, can meaningfully change both the sound and the value.',
  'Learn to recognize a handful of jazz label logos on sight (Blue Note, Impulse!, Prestige) -- the label alone tells you a lot about the era and style before you even read the back cover.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Blues',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Blues is the root system underneath most American popular music -- rock, soul, and R&B all grow out of it.',
  E'Blues developed in the rural American South in the late 1800s and early 1900s, growing out of African American work songs, spirituals, and field hollers. Its foundation -- the 12-bar structure, call-and-response phrasing, and bent, expressive "blue notes" -- became one of the most influential musical templates of the 20th century. Early blues was largely acoustic and regional: the raw, guitar-driven Mississippi Delta sound of Robert Johnson is one well-known strand, but Piedmont blues, Texas blues, and other regional styles all developed with their own distinct character.\n\nThe Great Migration carried blues north through the early-to-mid 20th century, and in Chicago it went electric: amplified guitar, harmonica, and full rhythm sections turned rural acoustic blues into the harder, louder urban blues sound of Muddy Waters and Howlin'' Wolf, much of it recorded for Chess Records. That electric Chicago blues sound fed directly into the birth of rock and roll in the 1950s.\n\nBlues collecting spans an enormous range, from extremely rare and valuable pre-war 78 rpm singles to widely available electric blues LPs from the 1960s onward -- knowing roughly which era and region you are looking at changes what you should expect to pay.',
  'Pre-war blues 78s are a completely different collecting world than postwar electric blues LPs -- if a seller calls something "rare blues," ask what era and format before assuming it is valuable.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Soul',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Soul took gospel''s emotional intensity and R&B''s rhythm and turned it into one of the defining sounds of the 1960s.',
  E'Soul music emerged in the late 1950s and 1960s as gospel''s vocal power and emotional directness merged with rhythm and blues. It quickly split into distinct regional sounds that collectors still treat as separate categories: Motown, out of Detroit, favored polished, pop-oriented production aimed squarely at the charts, while Southern soul out of Stax Records in Memphis and Muscle Shoals in Alabama leaned grittier, rawer, and more directly rooted in gospel and blues. Philadelphia soul arrived a bit later with lush, orchestral production that helped pave the way toward disco.\n\nSoul was deeply tied to its cultural moment -- the genre rose alongside the civil rights movement, and many soul records carried that context directly in their lyrics and performance, not just their sound. That cultural weight is part of why soul collecting is not just about the music but about the labels, cities, and moments that produced it.\n\nOne of the more unusual corners of soul collecting is Northern Soul, a UK phenomenon where collectors and DJs sought out obscure, often commercially unsuccessful American soul 45s specifically for their driving tempo and danceability -- turning overlooked US singles into highly valuable, sought-after import records decades later.',
  'Pay attention to the label name on soul 45s and LPs (Motown, Stax, Atlantic, Hi Records) -- in soul collecting, the label is often as strong a signal of sound and era as the artist name.',
  'Draft','No',now()::text,now()::text
),
(
  'Genre Spotlight: Funk',
  'Genre Education',
  'Everyone',
  'Beginner',
  'Funk stripped soul down to its rhythm section and built a groove-first genre that hip hop would later sample endlessly.',
  E'Funk grew directly out of soul in the mid-to-late 1960s, led largely by James Brown, who shifted the emphasis away from melody and toward rhythm -- famously "the one," a hard downbeat emphasis that turned the rhythm section itself into the star of the record. Syncopated basslines, tight horn sections, and extended, repetitive grooves replaced the verse-chorus song structure that dominated most other popular music of the era, with tracks often built to stretch out and breathe rather than resolve quickly.\n\nGeorge Clinton''s Parliament-Funkadelic collective pushed funk in a more psychedelic, theatrical direction through the 1970s, while artists across the decade kept the genre''s rhythmic core intact even as the production around it evolved. Funk''s influence stretched far beyond its own commercial era -- its basslines, drum breaks, and horn stabs became some of the single most sampled material in hip hop production starting in the late 1970s and continuing for decades after.\n\nBecause of that sampling history, funk collecting overlaps heavily with hip hop crate-digging culture. Obscure, small-label 45s that went nowhere commercially in the 1970s can command serious premiums today if they contain a drum break or bassline that producers and DJs have sought out.',
  'If a funk 45 has a stripped-down instrumental break in the middle, that is often exactly what made it valuable to sample-digging collectors -- check for "breakbeat" mentions before assuming an obscure single has no value.',
  'Draft','No',now()::text,now()::text
);

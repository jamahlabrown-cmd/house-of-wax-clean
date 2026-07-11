-- House Of Wax Knowledge Hub -- second genre publish wave
-- Publishes the remaining 14 Genre Education articles that were left as
-- Draft after the first publish wave (Rock, Rap and Hip Hop, Jazz, Soul,
-- Blues, Reggae, Country, R&B, Disco, Funk). This wave covers the rest
-- of the 24 genre articles written this round.
-- Matches on title only (no status filter) so it's safe to re-run.

update knowledge_posts set status='Published', updated_at=now()::text
where title in (
  'Genre Spotlight: Eurodance',
  'Genre Spotlight: House',
  'Genre Spotlight: New Jack Swing',
  'Genre Spotlight: Metal',
  'Genre Spotlight: Punk',
  'Genre Spotlight: Latin Music',
  'Genre Spotlight: Afrobeat and Afrobeats',
  'Genre Spotlight: Gospel',
  'Genre Spotlight: Techno',
  'Genre Spotlight: Trance',
  'Genre Spotlight: Drum and Bass',
  'Genre Spotlight: K-pop',
  'Genre Spotlight: Indie and Alternative Rock',
  'Genre Spotlight: Classical Music'
);

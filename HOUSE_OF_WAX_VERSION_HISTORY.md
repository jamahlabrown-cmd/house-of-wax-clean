# House Of Wax Version History

## Current version

V25.12 COMBINED ARTIST TITLE SEARCH

Main purpose:

- Artist and title fields now work together.
- Combined artist + title search runs before fallback searches.
- Artist-only results are penalized when title is present.
- Smart Search still presents one recommended best match.

## Recent versions

### V25.12 Combined Artist + Title Search

Added:

- combined_search_terms
- lookup_itunes_combined_search
- lookup_musicbrainz_combined_search
- lookup_discogs_combined_search
- token_overlap_score
- stronger score_release_match
- combined artist/title diagnostics

Changed:

- Search prioritizes Artist + Title.
- Search tries quoted Artist + quoted Title.
- Search tries Title + Artist.
- Search tries Barcode + Artist + Title.
- Fallback broad search runs only if combined results are thin.
- Best-match scoring gives more weight when both artist and title match.
- Artist-only results are penalized when a title was provided.

### V25.11 Smart Best-Match Search

Added:

- One internal Smart Search button.
- No multiple browser windows.
- Search completes inside House Of Wax.
- App chooses one recommended best match.
- Use recommended match button.
- Backup links remain only as fallback.

This is the preferred search direction.

### V25.10 One-Button Universal Search

This version opened multiple external windows. This was rejected by the founder.

Do not return to this approach.

### V25.9 Clickable Search Buttons

Made backup search links clickable, but the founder clarified that the desired behavior was not many links or tabs.

### V25.8 Source Health Key Fix

Fixed duplicate Streamlit key crash from Source Health Check button.

### V25.7 Source Health + Universal Search

Added source health check and universal search backup links.

### V25.6 Broad Music Search

Added broader Discogs, Apple/iTunes, and MusicBrainz search.

### V25.5 Search Fallback Upgrade

Added artist/title fallback search.

### V25.4 Barcode Lookup Diagnostics

Added barcode diagnostics and troubleshooting.

### V25 Release Database

Added House Of Wax internal release database:

- how_releases
- how_release_sources
- how_release_corrections

Purpose:

- Build House Of Wax’s own reference database over time.
- Save release metadata.
- Allow corrections.
- Improve future search quality.

# Clue writing style guide

## General tone

- One or two sentences per clue. Plain, factual, slightly playful is fine —
  this is a game, not an encyclopedia excerpt. Rephrase in your own words
  rather than copying article prose verbatim (avoids both title leakage and
  copyright-adjacent verbatim lifting).
- Never use the article's title, display title, or an obvious redirect,
  anywhere in the clue text. `scripts/db_add_clue.py` hard-blocks exact
  substring matches, but also avoid near-misses (e.g. spelling out an
  acronym the title uses) — use your judgment beyond what the script checks.
- Write for a general audience: assume the player is curious but doesn't
  necessarily know the domain.

## `reveal_rank_hint` defaults (1 = obscure/first, 7 = revealing/last)

These are starting points — adjust per article based on how identifying a
particular fact actually is, since the same clue_type can be more or less
revealing depending on the subject.

| clue_type | typical rank |
|---|---|
| `categories` | 1-2 |
| `etymology` | 1-2 |
| `long_section_title` | 2-3 |
| `creation_year` | 2-3 |
| `langlinks_count` | 2-3 |
| `wikisource_excerpt` | 3 |
| `wikivoyage_fact` | 3 |
| `dyk_or_notable_fact` | 3-4 |
| `pageviews` | 3-4 |
| `top_citation` | 4-5 |
| `wikidata_fact` | 4-5 |
| `incoming_links` | 5 |
| `infobox_fact` | 5-6 |
| `commons_image` | 6-7 |

The actual reveal order is computed by `backend/app/lib/clue_selection.py`
from these hints plus a per-day random jitter, then frozen — this table just
sets reasonable defaults, it doesn't need to be exact.

## Per-type notes

- **categories**: pick genuinely obscure/small categories, not "Living
  people" or decade-birth categories. Two categories in one clue is fine
  ("filed under X and Y").
- **commons_image**: prefer a detail, artifact, location, or context photo
  over a face/portrait or anything with a name caption baked into the
  filename shown to the user.
- **infobox_fact**: pick a field that's interesting but not the name itself
  — a date, a numeric fact, a role, a location.
- **wikidata_fact**: phrase as a fact, not a Wikidata property dump ("has
  been recognized for contributions to X" rather than "P106: Q...").
- **pageviews / creation_year / langlinks_count**: these exist as low-leakage
  fallbacks to reach the 5-clue minimum when other types don't apply — keep
  them factual and light, they're rarely the most interesting clue in the
  set.
- **top_citation**: double-check the citation's own title/author name
  doesn't itself give away the subject.

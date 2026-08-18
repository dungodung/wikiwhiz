# Candidate article selection & clue-material sourcing

## Selecting a candidate article

Prefer articles that are rich enough to support 5-7 distinct, non-trivial
clues without repeating information. In rough priority order:

1. **Prefer `Category:Featured_articles` or `Category:Good_articles`** over
   `list=random` — these are pre-vetted for depth, sourcing, and stability
   (unlikely to be substantially rewritten between authoring and play).
   Query via `action=query&list=categorymembers&cmtitle=Category:Featured_articles&cmnamespace=0&cmlimit=500`,
   paginating with `cmcontinue` as needed.
2. **Length**: roughly 1500-8000 words of prose. Shorter articles usually
   can't support 5-7 non-repetitive clues; much longer articles are fine but
   take longer to mine for material.
3. **Has an infobox** (needed for the `infobox_fact` clue type) — check via
   `action=parse&prop=wikitext&section=0` and look for a `{{Infobox` template,
   or `action=parse&prop=parsetree` for a more robust check.
4. **Has at least one Commons image** — `action=query&prop=pageimages|images`.
5. **Has a Wikidata item with several statements** — `action=query&prop=pageprops`
   to get the `wikibase_item` QID, then `wbgetentities?ids=QID&props=claims`
   on www.wikidata.org. A handful of claims (occupation, date, location,
   notable work, etc.) is enough to support `wikidata_fact`.
6. **Topic diversity**: vary across people, places, works, organisms,
   events, concepts, etc. rather than clustering the pool around one domain
   — check `--list-existing` output for what's already well-represented.

### Editorial exclusions (judgment call, not automatable)

Skip candidates that are graphic (violent deaths, atrocities in vivid
detail), about recent tragedies or ongoing crises, or politically charged in
a way likely to make the puzzle feel like a statement rather than a game.
When in doubt, pick a different candidate — there's no shortage of good
options in the FA/GA categories.

## Sourcing material per clue type

| clue_type | Where to get it |
|---|---|
| `commons_image` | `Special:FilePath/{filename}?width=500` (see `commons-file-resolution` skill). Prefer a later/less-revealing image over the lead photo — a landscape, artifact, or detail shot rather than a portrait/logo that gives away the answer immediately. |
| `dyk_or_notable_fact` | Check if the article has run on DYK ([Wikipedia:Did_you_know_archive](https://en.wikipedia.org/wiki/Wikipedia:Did_you_know_archive)) or an On This Day slot ([Wikipedia:Selected_anniversaries](https://en.wikipedia.org/wiki/Wikipedia:Selected_anniversaries)). If neither is findable quickly, fall back to a striking sentence from later in the article (not the lead). |
| `wikidata_fact` | `wbgetentities?ids=QID&props=claims\|labels&languages=en` on www.wikidata.org. Pick a claim that's interesting but not identity-revealing on its own (e.g. "occupation: theoretical physicist" is more revealing than "employer: a specific obscure institute"). |
| `infobox_fact` | Parse the infobox wikitext/parsetree for a field that's factual but not the subject's name. |
| `categories` | `action=query&prop=categories&cllimit=max`, then `action=query&prop=categoryinfo&titles=...` to find the **smallest** (least populated) 2 categories, excluding anything containing the article's own title or an overly generic category (e.g. "Living people", "1879 births"). |
| `etymology` | Look up the term on en.wiktionary.org — only use if a real etymology section exists; skip the clue type otherwise (see `wiktionary-and-wikisource` skill). |
| `wikisource_excerpt` | Only if a clearly related English Wikisource page exists (e.g. a primary text by/about the subject). Skip otherwise. |
| `wikivoyage_fact` | Only for geographic topics (article has `prop=coordinates`). Check en.wikivoyage.org for a matching page. |
| `pageviews` | `wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/all-agents/{article}/monthly/...` — phrase as a relative fact ("gets several thousand views a month") rather than a precise number that could be searched. |
| `top_citation` | The most-cited or most distinctive reference in the article (see `wikipedia-citations` skill) — check the reference's own title doesn't leak the answer. |
| `incoming_links` | `prop=linkshere&lhnamespace=0&lhlimit=max` — report the rough count and 2-3 non-revealing example linking articles. |
| `long_section_title` | `action=parse&prop=sections` — pick a longer, distinctive, non-generic heading (avoid "History", "References", "See also"). |
| `creation_year` | `prop=revisions&rvdir=newer&rvlimit=1&rvprop=timestamp` — the article's first-revision year. Low-leakage fallback clue. |
| `langlinks_count` | `prop=langlinks&lllimit=max`, count the results — "has an article in N other languages." Low-leakage fallback clue. |

All Action API calls need a descriptive `User-Agent` header — see the
`wikimedia-api-access` skill and `backend/app/lib/mediawiki_api.py`'s
`WIKIWHIZ_USER_AGENT` config.

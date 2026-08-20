# Candidate article selection & clue-material sourcing

## Selecting a candidate article

The board shows a flat row of tiles: letters are guessable, and space, dash,
comma, and parentheses each show up as their own fixed, revealed tile (see
`backend/app/lib/slot_pattern.py`) -- word boundaries and a parenthetical
disambiguator like "Mercury (element)" are both fine and visible on the
board. Everything else (quotation marks, periods, colons, apostrophes,
digits) is stripped, which can normalize awkwardly for titles that lean on
it heavily (e.g. a title that's mostly digits, or an apostrophe-heavy name)
-- prefer titles where the letters/kept-punctuation still read naturally
once other punctuation is gone.

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
| `incoming_links` | **Prefer the Wiki Replica for an exact count** (see below) — `prop=linkshere&lhnamespace=0&lhlimit=max` caps at 500 for anonymous API calls, so any well-linked mainstream article (i.e. most Featured/Good articles, which this skill is told to prefer) just reports "500+" regardless of whether the true count is 600 or 60,000 — a clue that doesn't discriminate at all. Report the *exact* number when you have it ("linked from 4,827 other articles"), only falling back to the API's capped "500+" phrasing when replica access isn't available in this environment. Also pick 2-3 non-revealing example linking articles (from either source). |
| `outgoing_links` | Same 500-cap problem applies to `pllimit=max` for a links-heavy article (e.g. one with large "See also"/list sections) — prefer the Wiki Replica for an exact count here too if this ever becomes its own clue type; not currently in `CLUE_TYPES`. |
| `long_section_title` | `action=parse&prop=sections` — pick a longer, distinctive, non-generic heading (avoid "History", "References", "See also"). |
| `creation_year` | `prop=revisions&rvdir=newer&rvlimit=1&rvprop=timestamp` — the article's first-revision year. Low-leakage fallback clue. |
| `langlinks_count` | `prop=langlinks&lllimit=max`, count the results — "has an article in N other languages." Low-leakage fallback clue. Same 500-cap risk as `incoming_links` in principle (rarely actually hit in practice, since Wikipedia has ~300 language editions total) — prefer the Wiki Replica when available: `SELECT COUNT(*) FROM langlinks WHERE ll_from = <PAGEID>`. |
| `edit_count` | Wiki Replica only — see "`edit_count` / `distinct_editor_count`" section below. Not a fallback; a genuinely interesting first-tier clue. |
| `distinct_editor_count` | Wiki Replica only — see "`edit_count` / `distinct_editor_count`" section below. Not a fallback; a genuinely interesting first-tier clue. |

All Action API calls need a descriptive `User-Agent` header — see the
`wikimedia-api-access` skill and `backend/app/lib/mediawiki_api.py`'s
`WIKIWHIZ_USER_AGENT` config.

## Querying the Wiki Replica directly (for exact counts)

If this machine has SSH access configured to the Toolforge bastion (check
`~/.ssh/config` or ask the user), query `enwiki_p` on the Wiki Replicas
directly instead of the capped API calls above. This is the same read-only
mirror `backend/app/lib/wiki_replica.py` uses at runtime, just queried ad
hoc here rather than through that module (which is built to run *inside* a
Toolforge container, not from an arbitrary dev machine during authoring).

```
ssh <toolforge-username>@login.toolforge.org "become <toolname> -- mariadb \
  --defaults-file=/data/project/<toolname>/replica.my.cnf \
  -h enwiki.analytics.db.svc.wikimedia.cloud enwiki_p -e '<QUERY>'"
```

Exact incoming-link count (namespace 0 only), given the article's pageid:

```sql
SELECT COUNT(*) FROM page p_target
JOIN linktarget lt ON lt.lt_namespace = p_target.page_namespace AND lt.lt_title = p_target.page_title
JOIN pagelinks pl ON pl.pl_target_id = lt.lt_id AND pl.pl_from_namespace = 0
WHERE p_target.page_id = <PAGEID> AND p_target.page_namespace = 0;
```

If SSH access isn't available in this environment, don't block on it — fall
back to the capped API count and phrase the clue as an inequality rather
than implying precision ("linked from over 500 other articles").

## Diversify clue types -- don't default to the same easy six every time

A live spot-check of this project's first content batch found **every
single article** used the exact same six clue types (`categories`,
`long_section_title`, `creation_year`, `langlinks_count`, `incoming_links`,
`dyk_or_notable_fact`) and **none** used `commons_image`, `wikidata_fact`,
`infobox_fact`, `etymology`, `wikisource_excerpt`, `wikivoyage_fact`,
`pageviews`, or `top_citation` — despite the style guide already calling
several of the overused ones low-leakage fallbacks meant to fill gaps, not
go-to defaults. That's a real miss, not a hypothetical risk: gathering the
richer types takes more digging per article (an infobox parse, a Wikidata
claims lookup, checking for a DYK/Wikisource/Wikivoyage match), and it's
easy to lazily reach for the cheap API calls instead.

For every article, **attempt at least 3 of the "richer" types before
falling back to fill remaining slots with the low-leakage ones**:
`commons_image`, `wikidata_fact`, `infobox_fact`, `etymology` (if
applicable), `wikisource_excerpt` (if applicable), `wikivoyage_fact` (if
geographic), `dyk_or_notable_fact`, `top_citation`, `edit_count`,
`distinct_editor_count`. Only reach for `pageviews`, `creation_year`,
`langlinks_count`, or `incoming_links` to fill out the remaining slots —
never as the first three picks — and vary *which* of those fallbacks you use
across articles too, rather than always reaching for the same pair.

## `edit_count` / `distinct_editor_count` (Wiki Replica only)

Both need the Wiki Replica connection described above (see "Querying the
Wiki Replica directly") — there's no reasonably cheap Action API equivalent
for either at the scale a well-established FA/GA article's revision history
reaches (thousands to tens of thousands of revisions; `prop=revisions` caps
at 500/5000 per call).

```sql
-- total revisions
SELECT COUNT(*) FROM revision WHERE rev_page = <PAGEID>;

-- distinct editors (registered + anonymous both count; an anonymous edit's
-- rev_actor still gets its own actor_id per IP, so this slightly
-- overcounts truly-unique anonymous humans -- fine for an approximate
-- "over N" clue, not meant to be exact)
SELECT COUNT(DISTINCT rev_actor) FROM revision WHERE rev_page = <PAGEID>;
```

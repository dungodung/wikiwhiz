#!/usr/bin/env python3
"""One-off content maintenance: replace the initial 10-article batch's
capped/lazy incoming_links and langlinks_count clue text with exact Wiki
Replica counts, and add a 7th, genuinely new-type clue to each of the 8
future-scheduled articles from that batch (the other 2 -- already live or
played -- are left untouched, since editing what a player has already seen
is exactly what the admin API's locked-article guard exists to prevent).

Run once locally against the dev DB to verify, then again (unmodified) as a
Toolforge job against production. Safe to re-run: UPDATEs are idempotent,
and the INSERT is skipped if a clue of that type already exists for the
article (so a second run doesn't add an 8th clue).

Numbers were pulled once from the Wiki Replica (enwiki_p) via SSH -- see
.claude/skills/wikiwhiz-content-author/references/candidate_criteria.md for
the query pattern -- not computed live by this script, since it has no
replica/API access of its own and this is a one-time fix, not a recurring
job.
"""

import sys

from _db import session_scope

from backend.app.lib.clue_selection import compute_clue_order
from backend.app.models.article import Article
from backend.app.models.clue import Clue
from backend.app.models.daily_challenge import DailyChallenge

# pageid -> {existing incoming_links/langlinks_count clue text fixes, plus
# the new 7th clue to add}
REFRESH = {
    70983: {  # Great Barrier Reef
        "incoming_links_text": "It's linked from 2,222 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 135 other language Wikipedias.",
        "new_clue": ("infobox_fact", 6, "Its UNESCO World Heritage-listed protected area covers about 34.87 million hectares."),
    },
    5094570: {  # Great Wall of China
        "incoming_links_text": "It's linked from 1,192 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 165 other language Wikipedias.",
        "new_clue": ("infobox_fact", 6, "Adding up all its sections, its total length comes to more than 21,000 kilometers."),
    },
    18079: {  # Leonardo da Vinci
        "incoming_links_text": "It's linked from 3,591 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 235 other language Wikipedias.",
        "new_clue": ("wikidata_fact", 5, "Wikidata lists several students associated with this person, including Salaì and Francesco Melzi."),
    },
    17914: {  # Ludwig van Beethoven
        "incoming_links_text": "It's linked from 5,689 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 210 other language Wikipedias.",
        "new_clue": ("wikidata_fact", 5, "Wikidata credits Johann Sebastian Bach and Joseph Haydn, among others, as influences on this person's work."),
    },
    22780: {  # Octopus
        "incoming_links_text": "It's linked from 1,700 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 105 other language Wikipedias.",
        "new_clue": ("distinct_editor_count", 3, "Its Wikipedia article has been edited by over 2,700 different registered and anonymous contributors."),
    },
    23312: {  # Penicillin
        "incoming_links_text": "It's linked from 1,575 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 105 other language Wikipedias.",
        "new_clue": ("edit_count", 3, "Its Wikipedia article has been revised more than 4,800 times."),
    },
    24544: {  # Photosynthesis
        "incoming_links_text": "It's linked from 3,227 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 150 other language Wikipedias.",
        "new_clue": ("distinct_editor_count", 3, "Its Wikipedia article has been edited by over 2,500 different contributors."),
    },
    19285924: {  # Titanic
        "incoming_links_text": "It's linked from 1,797 other English Wikipedia articles.",
        "langlinks_text": "It has sister articles in over 135 other language Wikipedias.",
        "new_clue": ("infobox_fact", 6, "According to its infobox, it carried 20 lifeboats — enough for 1,178 people, well short of everyone aboard."),
    },
}


def main() -> int:
    with session_scope() as session:
        for pageid, spec in REFRESH.items():
            article = session.query(Article).filter_by(wiki_pageid=pageid).first()
            if not article:
                print(f"SKIP: no article with pageid={pageid}", file=sys.stderr)
                continue

            challenge = (
                session.query(DailyChallenge).filter_by(article_id=article.id).first()
            )
            if challenge is None:
                print(f"SKIP: {article.display_title} isn't scheduled", file=sys.stderr)
                continue

            incoming = (
                session.query(Clue).filter_by(article_id=article.id, clue_type="incoming_links").first()
            )
            if incoming:
                incoming.clue_text = spec["incoming_links_text"]

            langlinks = (
                session.query(Clue).filter_by(article_id=article.id, clue_type="langlinks_count").first()
            )
            if langlinks:
                langlinks.clue_text = spec["langlinks_text"]

            new_type, new_rank, new_text = spec["new_clue"]
            existing_new = (
                session.query(Clue).filter_by(article_id=article.id, clue_type=new_type).first()
            )
            if not existing_new:
                session.add(
                    Clue(
                        article_id=article.id,
                        clue_type=new_type,
                        reveal_rank_hint=new_rank,
                        clue_text=new_text,
                        is_title_leaking=False,
                    )
                )
            session.flush()

            clue_rows = [
                {"id": c.id, "reveal_rank_hint": c.reveal_rank_hint}
                for c in session.query(Clue).filter_by(article_id=article.id, is_title_leaking=False).all()
            ]
            challenge.clue_order = compute_clue_order(clue_rows, seed=challenge.id)

            print(f"OK: {article.display_title} -> {len(clue_rows)} clues, clue_order refreshed")

    return 0


if __name__ == "__main__":
    sys.exit(main())

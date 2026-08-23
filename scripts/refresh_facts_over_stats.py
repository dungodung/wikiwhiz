#!/usr/bin/env python3
"""One-off content maintenance: retroactively apply the "facts before
stats" preference (see .claude/skills/wikiwhiz-content-author/references/
candidate_criteria.md) to the 9 worst-offending unplayed articles from
before that rule existed -- the 4 that had 4 stat-type clues out of 6-7
total, and the 5 carrying the redundant edit_count+distinct_editor_count
pair on the same article. Each swap replaces one weak/redundant stat clue's
type+text in place; the clue's id and its slot in the article's
daily_challenges.clue_order are unchanged, so (unlike
refresh_initial_batch_clues.py, which added a new clue) no reveal-order
recomputation is needed here.

Safe to re-run: every UPDATE is keyed by clue id, so re-running just
reapplies the same text.
"""

import sys

from _db import session_scope

from backend.app.lib.clue_guard import leaks_title
from backend.app.models.article import Article
from backend.app.models.clue import Clue

# clue id -> (new_type, new_reveal_rank_hint, new_text)
REPLACEMENTS = {
    52: ("etymology", 2, "Its common English name comes from Greek roots meaning 'eight' and 'foot'."),
    58: ("etymology", 2, "Its name derives from the mould genus that produces it, itself named after a Latin word for 'paintbrush', describing the shape of its spore-bearing structures."),
    64: ("wikidata_fact", 4, "Wikidata classifies this process as a subclass of cell metabolism."),
    63: ("wikidata_fact", 4, "Wikidata lists three sub-processes as parts of this process, including the Calvin cycle."),
    150: ("etymology", 2, "The word used to describe this event was reportedly favored by officials at the time because it sounded less alarming than 'panic' or 'crisis', the terms used for earlier downturns."),
    87: ("wikidata_fact", 4, "Wikidata lists four children for this person, including one son and a pair of twins."),
    101: ("etymology", 2, "The group's name is often credited to one member as a pun blending an insect name with the word 'beat', a nod to the music style they played."),
    107: ("infobox_fact", 6, "Its musical score was composed by Max Steiner."),
    114: ("infobox_fact", 6, "Its taxobox lists a global conservation status of 'Vulnerable', with a more severe regional status in parts of Europe."),
    143: ("infobox_fact", 6, "Its infobox lists formal training at the Royal Academy of Fine Arts in Antwerp."),
}


def main() -> int:
    with session_scope() as session:
        for clue_id, (new_type, new_rank, new_text) in REPLACEMENTS.items():
            clue = session.get(Clue, clue_id)
            if clue is None:
                print(f"SKIP: no clue with id={clue_id}", file=sys.stderr)
                continue
            article = session.get(Article, clue.article_id)
            if leaks_title(new_text, article):
                print(f"ABORT: replacement for clue {clue_id} leaks {article.display_title}'s title", file=sys.stderr)
                return 1

            old_type = clue.clue_type
            clue.clue_type = new_type
            clue.reveal_rank_hint = new_rank
            clue.clue_text = new_text
            print(f"OK: clue {clue_id} ({article.display_title}) {old_type} -> {new_type}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

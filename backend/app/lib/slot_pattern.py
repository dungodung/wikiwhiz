"""Turn a display title into a Wheel-of-Fortune-style slot pattern.

The pattern is computed once, at article-insert time, and stored as JSON on
Article.slot_pattern. The frontend renders it directly with zero title logic
of its own: letters are hidden until the winning reveal, punctuation renders
literally, and word gaps get a visible space.
"""

import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[^\sA-Za-z0-9]")


def tokenize_title_to_slots(display_title: str) -> list[dict]:
    slots: list[dict] = []
    words = display_title.split(" ")
    for i, word in enumerate(words):
        if i > 0:
            slots.append({"type": "space"})
        for match in _TOKEN_RE.finditer(word):
            token = match.group(0)
            if re.match(r"^[A-Za-z0-9]+$", token):
                slots.append({"type": "word", "len": len(token)})
            else:
                slots.append({"type": "punct", "char": token})
    return slots

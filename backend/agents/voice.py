"""Patterns that make writing read as machine-made, shared by the writer prompt, the reviewer and the lint step.

Prompts alone don't hold: models drift back to these habits, so drafts are also checked in code and anything
found goes back to the writer with the exact phrase quoted. No checker can promise a text passes an "AI
detector" (they misfire on human writing too); the aim is writing that sounds like this one person.
"""

import re

# (pattern, what to tell the writer). Patterns are case-insensitive.
_PHRASES: list[tuple[str, str]] = [
    # formula hooks and reframes
    (r"\b(?:don't|doesn't|do not|does not) care (?:about|if|whether)\b[^.?!]*[.?!]\s+(?:they|it|he|she|we) cares? about\b",
     "the 'X don't care about A. They care about B.' formula"),
    (r"\b(?:it'?s|this is|that'?s) not (?:just )?(?:about )?[^.,;]{1,60}[,;:—–-]+\s*(?:it'?s|this is|that'?s)\b", "the 'it's not X, it's Y' reframe"),
    (r"\bnot (?:just )?(?:a|an) [^.,;]{1,40}[,;—–-]+\s*but (?:a|an)\b", "the 'not a X, but a Y' reframe"),
    (r"(?:^|[.!?]\s+|\n)instead of [^.]{3,120}?,", "an 'Instead of X, Y' turn"),
    (r"\bhere(?:'s| is| are) (?:how|why|what|the thing|the truth|the kicker|the catch)\b", "signposting ('Here's how/why/what')"),
    (r"\b(?:the truth is|the reality is|let that sink in|read that again|spoiler alert|plot twist|but here's the thing)\b", "a stock dramatic line"),
    (r"\b(?:in today's|in an era of|in a world where|fast-paced|ever-evolving|ever-changing)\b", "a stock opener"),
    # words that mark corporate / model prose
    (r"\b(?:delve|delves|delving|leverag(?:e|es|ed|ing)|harness(?:es|ed|ing)?|unlock(?:s|ed|ing)?|empower(?:s|ed|ing)?|elevat(?:e|es|ed|ing)|"
     r"seamless(?:ly)?|robust|pivotal|crucial|game[- ]changer|game[- ]changing|transformative|tapestry|realm|landscape|"
     r"pinpoint(?:s|ed|ing)?|bottom[- ]line|actionable insights?|key takeaways?|deep dive|navigate the|embark(?:s|ed|ing)?|"
     r"foster(?:s|ed|ing)?|synerg(?:y|ies)|paradigm|holistic|cutting[- ]edge|supercharge|streamline)\b", "corporate or AI-flavoured wording"),
    (r"\b(?:in conclusion|in summary|to sum up|ultimately|furthermore|moreover|additionally)\b", "essay connectors"),
    (r"—", "em dashes (use a full stop or a comma)"),
]
_COMPILED = [(re.compile(p, re.IGNORECASE), why) for p, why in _PHRASES]

# A last line that is a stock "engage with me" question ("How do you...?", "What's your take?"), not a specific one.
_ENGAGEMENT_ENDING = re.compile(
    r"^(?:how do you|how are you|how have you|how would you|what's your|what is your|what are your|what do you think|"
    r"what would you|have you ever|do you agree|agree or disagree|are you|which (?:one|of these)|curious|thoughts)\b[^?]*\?\s*$",
    re.IGNORECASE,
)
_HASHTAGS_ONLY = re.compile(r"^(?:#\S+\s*)+$")


def ai_tells(text: str, limit: int = 6) -> list[str]:
    """Issues for the writer, each quoting the offending phrase. Empty when nothing stands out."""
    issues: list[str] = []
    for pattern, why in _COMPILED:
        found = [re.sub(r"\s+", " ", m.group(0)).strip(" .!?\n") for m in pattern.finditer(text)]
        if not found:
            continue
        if why.startswith("em dashes"):
            issues.append(f"Reads as machine-written: {len(found)} {why}.")
        else:
            quoted = ", ".join(f"'{f[:70]}'" for f in dict.fromkeys(found))
            issues.append(f"Reads as machine-written: {why}: {quoted}. Say it the way the author would say it out loud.")
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip() and not _HASHTAGS_ONLY.match(ln.strip())]
    if lines and _ENGAGEMENT_ENDING.match(lines[-1]):
        issues.append(
            f"Ends on a generic engagement question ('{lines[-1][:80]}'). End on the point itself, or ask only a question "
            "the author genuinely wants answered."
        )
    return issues[:limit]


HUMAN_VOICE = (
    "WRITE LIKE THIS PERSON, NOT LIKE A TEMPLATE:\n"
    "- Speak from the author's own experience: first person, a specific moment, a number or a mistake from their work, "
    "an opinion they'd defend in an argument.\n"
    "- Vary the rhythm. Mix short and long sentences and paragraphs; not every paragraph is one or two lines.\n"
    "- Plain words a person says out loud: 'use' not 'leverage', 'find' not 'pinpoint', 'important' not 'crucial'.\n"
    "- No formulas: no 'X don't care about A, they care about B', no 'It's not X, it's Y', no 'Here's how/why', no "
    "'Instead of X, Y' turn, no 'The truth is', no rule-of-three lists for rhythm.\n"
    "- No em dashes. No essay connectors (Moreover, Furthermore, Ultimately, In conclusion).\n"
    "- Not every post needs a numbered list, a reframe or a question. Use a list only when the content really is a "
    "sequence. End where the thought ends; ask a question only if the author would genuinely want the answers.\n"
    "- Leave a little texture: an aside, a half-formed doubt, a concrete name or tool. Perfectly balanced, "
    "evenly paced prose is what reads as generated."
)

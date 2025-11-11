# livekit_interrupt_filter.py
import re
from typing import Iterable

# Basic filler tokens (expand as needed)
FILLER_TOKENS = {
    "uh", "um", "umm", "hmm", "erm", "ah", "oh", "uhh", "uhm", "huh", "mm"
}

# Command words that should always be forwarded
COMMAND_WORDS = {
    "stop", "wait", "pause", "cancel", "no", "stop that", "hold on", "don't", "dont"
}

# Confidence threshold below which short utterances may be considered filler
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

_token_re = re.compile(r"[a-zA-Z']+")


def _tokenize(text: str) -> Iterable[str]:
    return (t.lower() for t in _token_re.findall(text or ""))


def contains_command(text: str) -> bool:
    """
    Return True if the text contains a command-like word/phrase.
    """
    if not text:
        return False
    txt = text.lower()
    # check for multi-word commands first
    for cmd in COMMAND_WORDS:
        if cmd in txt:
            return True
    # token-level check (e.g. "stop" or "pause")
    for t in _tokenize(text):
        if t in COMMAND_WORDS:
            return True
    return False


def is_filler_only(text: str, confidence: float, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> bool:
    """
    Return True when `text` is considered filler-only.

    Heuristics:
      - If all tokens are in FILLER_TOKENS, consider filler.
      - For single-token utterances with low confidence, treat as filler.
      - Short transcripts (1-2 tokens) that are filler-like are considered filler.
    """
    if not text or not text.strip():
        return True

    tokens = list(_tokenize(text))
    if not tokens:
        return True

    # If any command present -> not filler-only
    if contains_command(text):
        return False

    # If every token is a filler token -> filler
    if all(t in FILLER_TOKENS for t in tokens):
        return True

    # Single token with low confidence -> consider filler
    if len(tokens) == 1 and confidence < threshold:
        return True

    # Two tokens which are filler-ish (like "uh hmm") -> filler
    if len(tokens) <= 2 and all(len(t) <= 3 for t in tokens) and confidence < (threshold + 0.15):
        return True

    return False

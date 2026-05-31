from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, Iterable, List, Tuple


_NON_WORD_PATTERN = re.compile(r'[^\w\s]')


@lru_cache(maxsize=20000)
def normalize_network_text(text: str) -> str:
    raw = (text or '').strip()
    if not raw:
        return ''
    return _NON_WORD_PATTERN.sub('', raw)


@lru_cache(maxsize=20000)
def tokenize_network_text(text: str) -> tuple[str, ...]:
    normalized = normalize_network_text(text)
    if not normalized:
        return ()
    return tuple(word for word in normalized.split() if len(word) > 1)


def messages_related(content1: str, content2: str) -> bool:
    if not content1 or not content2:
        return False

    words1 = set(tokenize_network_text(content1))
    words2 = set(tokenize_network_text(content2))
    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    union = len(words1 | words2)
    return (overlap / union) > 0.2 if union > 0 else False


def calculate_user_similarity(contents1: Iterable[str], contents2: Iterable[str]) -> float:
    words1 = set()
    words2 = set()

    for content in contents1:
        words1.update(tokenize_network_text(str(content or '')))
    for content in contents2:
        words2.update(tokenize_network_text(str(content or '')))

    if not words1 or not words2:
        return 0.0

    intersection = len(words1 & words2)
    union = len(words1 | words2)
    return intersection / union if union > 0 else 0.0


def calc_pair_similarity(pair: Tuple[str, str], user_contents: Dict[str, List[str]]) -> tuple[Tuple[str, str], float]:
    qq1, qq2 = pair
    contents1 = user_contents.get(qq1, [])
    contents2 = user_contents.get(qq2, [])

    if len(contents1) < 2 or len(contents2) < 2:
        return pair, 0.0

    similarity = calculate_user_similarity(contents1, contents2)
    return pair, similarity

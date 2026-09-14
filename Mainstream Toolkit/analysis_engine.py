"""Offline chapter analysis helpers for the Streamlit manuscript tool."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import exp
from typing import Iterable


STOP_WORDS = {
    "able",
    "about",
    "after",
    "again",
    "against",
    "all",
    "almost",
    "along",
    "also",
    "although",
    "always",
    "and",
    "any",
    "among",
    "another",
    "are",
    "around",
    "back",
    "because",
    "been",
    "before",
    "behind",
    "being",
    "below",
    "between",
    "both",
    "but",
    "can",
    "could",
    "did",
    "does",
    "done",
    "down",
    "else",
    "each",
    "even",
    "every",
    "few",
    "for",
    "from",
    "had",
    "has",
    "have",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "into",
    "its",
    "just",
    "like",
    "may",
    "might",
    "more",
    "most",
    "much",
    "must",
    "not",
    "off",
    "one",
    "only",
    "our",
    "out",
    "other",
    "over",
    "own",
    "put",
    "said",
    "same",
    "she",
    "should",
    "some",
    "still",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "through",
    "too",
    "under",
    "until",
    "upon",
    "was",
    "were",
    "why",
    "very",
    "who",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "yes",
    "you",
    "your",
}


SENSORY_CUES = {
    "visual": {
        "black",
        "blue",
        "bright",
        "color",
        "dark",
        "glare",
        "gleam",
        "glimmer",
        "glow",
        "green",
        "light",
        "look",
        "moon",
        "red",
        "saw",
        "see",
        "shadow",
        "shimmer",
        "silver",
        "stare",
        "sun",
        "watch",
        "white",
        "window",
    },
    "sound": {
        "bell",
        "breath",
        "clatter",
        "cry",
        "echo",
        "hum",
        "laugh",
        "music",
        "quiet",
        "ring",
        "silence",
        "sound",
        "thunder",
        "voice",
        "whisper",
    },
    "touch": {
        "ache",
        "cold",
        "fingers",
        "grip",
        "hand",
        "heat",
        "pressure",
        "rough",
        "skin",
        "soft",
        "touch",
        "warm",
    },
    "scent": {
        "ash",
        "blood",
        "cedar",
        "perfume",
        "rain",
        "salt",
        "scent",
        "smell",
        "smoke",
        "sweat",
    },
    "taste": {
        "bitter",
        "honey",
        "metal",
        "salt",
        "sour",
        "sweet",
        "taste",
        "wine",
    },
}





THEME_CUES = {
    "desire and restraint": {
        "almost",
        "desire",
        "forbidden",
        "longing",
        "need",
        "restraint",
        "tempt",
        "want",
    },
    "power and control": {
        "command",
        "control",
        "force",
        "order",
        "permission",
        "power",
        "refuse",
        "rule",
    },
    "trust and vulnerability": {
        "confess",
        "honest",
        "open",
        "safe",
        "secret",
        "trust",
        "truth",
        "vulnerable",
    },
    "danger and survival": {
        "blood",
        "danger",
        "dead",
        "escape",
        "fear",
        "kill",
        "risk",
        "survive",
    },
    "memory and grief": {
        "ghost",
        "grief",
        "lost",
        "memory",
        "mourn",
        "remember",
        "scar",
    },
    "identity and transformation": {
        "become",
        "change",
        "choice",
        "face",
        "mask",
        "name",
        "self",
        "transform",
    },
}


ACTION_CUES = {
    "argue",
    "break",
    "choose",
    "confess",
    "decide",
    "escape",
    "fight",
    "find",
    "hide",
    "leave",
    "lie",
    "promise",
    "refuse",
    "reveal",
    "run",
    "threaten",
}


COMMON_CAPITALIZED = {
    "A",
    "After",
    "And",
    "As",
    "At",
    "Before",
    "But",
    "Chapter",
    "For",
    "From",
    "He",
    "Her",
    "His",
    "I",
    "If",
    "In",
    "It",
    "Its",
    "My",
    "No",
    "Of",
    "On",
    "One",
    "She",
    "That",
    "The",
    "Then",
    "They",
    "This",
    "To",
    "We",
    "When",
    "With",
    "You",
}


@dataclass(frozen=True)
class EvidenceGroup:
    label: str
    count: int
    evidence: list[str]


@dataclass(frozen=True)
class ChapterAnalysis:
    title: str
    word_count: int
    sentence_count: int
    reading_minutes: int
    main_ideas: list[str]
    summary: list[str]
    imagery: list[EvidenceGroup]
    signals: dict[str, float]
    key_scene_elements: dict[str, list[str] | int]
    themes_and_motifs: list[EvidenceGroup]


def analyze_chapter(markdown_text: str, title: str = "Untitled") -> ChapterAnalysis:
    """Analyze one chapter of Markdown and return UI-ready findings."""

    plain_text = strip_markdown(markdown_text)
    sentences = split_sentences(plain_text)
    words = tokenize_words(plain_text)
    word_count = len(words)
    headings = extract_headings(markdown_text)
    keyword_counts = significant_terms(words)
    main_ideas = extract_main_ideas(headings, keyword_counts)
    summary = summarize_sentences(sentences, keyword_counts)
    imagery = extract_imagery(sentences, plain_text)
    from narrative_engine import analyze_passage
    signals = analyze_passage(markdown_text)["scores"]

    return ChapterAnalysis(
        title=title,
        word_count=word_count,
        sentence_count=len(sentences),
        reading_minutes=max(1, round(word_count / 230)) if word_count else 0,
        main_ideas=main_ideas,
        summary=summary,
        imagery=imagery,
        signals=signals,
        key_scene_elements=extract_key_scene_elements(markdown_text, plain_text, sentences),
        themes_and_motifs=extract_themes_and_motifs(sentences, plain_text),
    )


def strip_markdown(markdown_text: str) -> str:
    text = re.sub(r"```.*?```", " ", markdown_text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[>\-\*\+]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_`~]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_headings(markdown_text: str) -> list[str]:
    headings = []
    for match in re.finditer(r"^(#{1,6})\s+(.+?)\s*$", markdown_text, flags=re.MULTILINE):
        heading = re.sub(r"[*_`~]+", "", match.group(2)).strip()
        if heading:
            headings.append(heading)
    return headings


def split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    sentences = [chunk.strip() for chunk in chunks if len(chunk.strip()) > 2]
    return sentences


def tokenize_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]{1,}", text.lower())


def significant_terms(words: Iterable[str], limit: int = 24) -> Counter[str]:
    clean_words = [
        word.strip("'")
        for word in words
        if len(word.strip("'")) > 2 and word.strip("'") not in STOP_WORDS
    ]
    return Counter(clean_words).most_common(limit)


def extract_main_ideas(headings: list[str], keyword_counts: list[tuple[str, int]]) -> list[str]:
    ideas: list[str] = []
    for heading in headings[:4]:
        ideas.append(f"Scene focus: {heading}")

    for word, count in keyword_counts[:8]:
        if count > 1:
            ideas.append(f"Repeated emphasis: {word} ({count})")

    if not ideas and keyword_counts:
        ideas = [f"Emerging focus: {word}" for word, _ in keyword_counts[:5]]

    return ideas[:8]


def summarize_sentences(
    sentences: list[str], keyword_counts: list[tuple[str, int]], max_sentences: int = 3
) -> list[str]:
    if not sentences:
        return []
    if len(sentences) <= max_sentences:
        return [shorten(sentence) for sentence in sentences]

    keyword_weight = {word: score for word, score in keyword_counts[:12]}
    scored = []
    for index, sentence in enumerate(sentences):
        sentence_words = tokenize_words(sentence)
        score = sum(keyword_weight.get(word, 0) for word in sentence_words)
        if index == 0:
            score += 3
        if any(cue in sentence.lower() for cue in ACTION_CUES):
            score += 2
        scored.append((score, index, sentence))

    chosen = sorted(sorted(scored, reverse=True)[:max_sentences], key=lambda item: item[1])
    return [shorten(sentence) for _, _, sentence in chosen]


def extract_imagery(sentences: list[str], plain_text: str) -> list[EvidenceGroup]:
    groups = []
    for label, terms in SENSORY_CUES.items():
        count = count_terms(plain_text, terms)
        evidence = evidence_for_terms(sentences, terms)
        groups.append(EvidenceGroup(label=label, count=count, evidence=evidence))
    return sorted(groups, key=lambda group: group.count, reverse=True)


def sentence_contains_terms(sentence: str, terms: set[str]) -> bool:
    lowered = sentence.lower()
    return any(term in lowered for term in terms)


def extract_key_scene_elements(
    markdown_text: str, plain_text: str, sentences: list[str]
) -> dict[str, list[str] | int]:
    headings = extract_headings(markdown_text)
    characters = extract_capitalized_phrases(plain_text)
    locations = extract_location_phrases(plain_text)
    scene_beats = [
        shorten(sentence)
        for sentence in sentences
        if any(cue in sentence.lower() for cue in ACTION_CUES)
    ][:5]
    repeated_images = [
        f"{word} ({count})"
        for word, count in significant_terms(tokenize_words(plain_text), limit=18)
        if count > 1
    ][:8]
    dialogue_lines = [
        line.strip()
        for line in markdown_text.splitlines()
        if '"' in line or "\u201c" in line or "\u201d" in line
    ]

    return {
        "scene_headings": headings[:8],
        "likely_characters": characters[:10],
        "likely_locations": locations[:8],
        "scene_beats": scene_beats,
        "repeated_images": repeated_images,
        "dialogue_line_count": len(dialogue_lines),
    }


def extract_themes_and_motifs(sentences: list[str], plain_text: str) -> list[EvidenceGroup]:
    groups = []
    for label, terms in THEME_CUES.items():
        count = count_terms(plain_text, terms)
        if count:
            groups.append(
                EvidenceGroup(
                    label=label,
                    count=count,
                    evidence=evidence_for_terms(sentences, terms, max_items=2),
                )
            )
    return sorted(groups, key=lambda group: group.count, reverse=True)


def extract_capitalized_phrases(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}\b", text)
    counts = Counter(
        candidate
        for candidate in candidates
        if candidate not in COMMON_CAPITALIZED
        and not candidate.startswith(("Chapter ", "Scene "))
        and len(candidate) > 2
    )
    return [name for name, _ in counts.most_common(12)]


def extract_location_phrases(text: str) -> list[str]:
    matches = re.findall(
        r"\b(?:at|inside|into|near|outside|through|under|within)\s+"
        r"(?:the\s+)?([A-Za-z][A-Za-z'-]*(?:\s+[A-Za-z][A-Za-z'-]*){0,3})",
        text,
        flags=re.IGNORECASE,
    )
    counts = Counter(
        phrase.strip(" .,!?:;").lower()
        for phrase in matches
        if phrase and phrase.lower() not in STOP_WORDS
    )
    return [phrase for phrase, _ in counts.most_common(10)]


def evidence_for_terms(
    sentences: list[str], terms: set[str], max_items: int = 3
) -> list[str]:
    evidence = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(term in lowered for term in terms):
            evidence.append(shorten(sentence))
        if len(evidence) >= max_items:
            break
    return evidence


def count_terms(text: str, terms: set[str]) -> int:
    lowered = text.lower()
    total = 0
    for term in terms:
        if " " in term:
            total += len(re.findall(re.escape(term), lowered))
        else:
            total += len(re.findall(rf"\b{re.escape(term)}(?:s|ed|ing)?\b", lowered))
    return total


def shorten(text: str, max_length: int = 260) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if len(clean) <= max_length:
        return clean
    return clean[: max_length - 3].rstrip() + "..."

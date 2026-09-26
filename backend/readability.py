"""
Rule-based readability and plain-language checks.

No external dependencies and no network calls — this runs instantly and is
meant to catch the mechanical issues (long sentences, passive voice, grade
level) before the more expensive AI pass looks for procedural ambiguity.
"""
import re

VOWELS = "aeiouy"

IRREGULAR_PAST_PARTICIPLES = {
    "done", "made", "seen", "known", "given", "taken", "shown", "written",
    "broken", "chosen", "spoken", "driven", "worn", "torn", "sent", "kept",
    "held", "found", "left", "built", "set", "put", "brought", "bought",
    "installed", "removed",
}

BE_VERBS = {"is", "are", "was", "were", "be", "been", "being"}


def count_syllables(word: str) -> int:
    word = re.sub(r"[^a-z]", "", word.lower())
    if not word:
        return 0
    syllables = 0
    prev_was_vowel = False
    for ch in word:
        is_vowel = ch in VOWELS
        if is_vowel and not prev_was_vowel:
            syllables += 1
        prev_was_vowel = is_vowel
    if word.endswith("e") and syllables > 1:
        syllables -= 1
    return max(syllables, 1)


def split_sentences(text: str):
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def split_words(sentence: str):
    return re.findall(r"[A-Za-z']+", sentence)


def detect_passive_sentences(sentences):
    passive = []
    for s in sentences:
        words = split_words(s.lower())
        for i, w in enumerate(words):
            if w in BE_VERBS:
                window = words[i + 1: i + 4]
                if any(w2.endswith("ed") or w2 in IRREGULAR_PAST_PARTICIPLES for w2 in window):
                    passive.append(s.strip())
                    break
    return passive


def analyze_readability(text: str, long_sentence_threshold: int = 25):
    sentences = split_sentences(text)
    if not sentences:
        return {
            "flesch_kincaid_grade": 0.0,
            "avg_sentence_length": 0.0,
            "passive_voice_sentences": [],
            "long_sentences": [],
        }

    total_words = 0
    total_syllables = 0
    long_sentences = []

    for s in sentences:
        words = split_words(s)
        n_words = len(words)
        total_words += n_words
        total_syllables += sum(count_syllables(w) for w in words)
        if n_words >= long_sentence_threshold:
            long_sentences.append(s.strip())

    n_sentences = len(sentences)
    words_per_sentence = total_words / n_sentences if n_sentences else 0.0
    syllables_per_word = total_syllables / total_words if total_words else 0.0

    fk_grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    fk_grade = round(max(fk_grade, 0.0), 2)

    return {
        "flesch_kincaid_grade": fk_grade,
        "avg_sentence_length": round(words_per_sentence, 1),
        "passive_voice_sentences": detect_passive_sentences(sentences),
        "long_sentences": long_sentences,
    }

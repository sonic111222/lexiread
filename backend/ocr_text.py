"""Repair English text returned by the Windows OCR engine.

The bundled frequency list is lemma-oriented, so this module adds regular
inflections plus a small set of irregular forms. Corrections are intentionally
conservative: numbers, abbreviations, proper nouns and apostrophe words are
left alone unless the OCR output is clearly malformed.
"""
from __future__ import annotations

import gzip
import json
import re
import unicodedata
from functools import lru_cache
from .config import BUNDLED_DATA_DIR

WORD_LIST_PATH = BUNDLED_DATA_DIR / "words_frequency.txt"
ECDICT_PATH = BUNDLED_DATA_DIR / "ecdict_subset.json.gz"

# Common forms missing from the lemma-oriented ECDICT subset. They protect
# correct text from being "corrected" into a different word.
_CORE_WORDS = """
a an i
is are was were am be been being have has had having do does did done doing
will would shall should can could may might must ought need dare used
go goes went gone going make makes made making say says said saying
take takes took taken taking come comes came coming see sees saw seen seeing
get gets got gotten getting know knows knew known knowing think thinks thought thinking
buy buys bought buying bring brings brought bringing find finds found finding
leave leaves left leaving feel feels felt feeling keep keeps kept keeping
hold holds held holding stand stands stood standing understand understands understood understanding
write writes wrote written writing read reads reading speak speaks spoke spoken speaking
run runs ran running eat eats ate eaten eating give gives gave given giving
fall falls fell fallen falling meet meets met meeting pay pays paid paying
sell sells sold selling send sends sent sending build builds built building
hear hears heard hearing lose loses lost losing win wins won winning
catch catches caught catching teach teaches taught teaching fight fights fought fighting
fly flies flew flown flying draw draws drew drawn drawing grow grows grew grown growing
throw throws threw thrown throwing bear bears bore born bearing beat beats beaten beating
become becomes became becoming begin begins began begun beginning break breaks broke broken breaking
choose chooses chose chosen choosing drive drives drove driven driving rise rises rose risen rising
wear wears wore worn wearing spend spends spent spending lend lends lent lending
hang hangs hung hanging dig digs dug digging lead leads led leading flee flees fled fleeing
seek seeks sought seeking shake shakes shook shaken shaking sing sings sang sung singing
swim swims swam swum swimming steal steals stole stolen stealing hide hides hid hidden hiding
bite bites bit bitten biting ride rides rode ridden riding sleep sleeps slept sleeping
sweep sweeps swept sweeping weep weeps wept weeping deal deals dealt dealing
mean means meant meaning forget forgets forgot forgotten forgetting
cannot
sit sits sat sitting set sets setting put puts putting let lets letting
cut cuts cutting hit hits hitting shut shuts shutting spread spreads spreading
cost costs costing hurt hurts hurting quit quits quitting
""".split()

_DIGIT_LOOKALIKES = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "6": "b", "7": "t", "8": "b", "9": "g", "|": "i"}
)
_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
# Letters commonly confused by OCR, plus the letters most often dropped or
# inserted. Kept small so two-edit searches stay fast on long passages.
_SUBSTITUTES = {
    "a": "eou",
    "b": "hp",
    "c": "eos",
    "d": "cl",
    "e": "acou",
    "f": "tv",
    "g": "qy",
    "h": "bn",
    "i": "elrtnm",
    "j": "i",
    "k": "c",
    "l": "it",
    "m": "nrwu",
    "n": "mru",
    "o": "ace",
    "p": "bq",
    "q": "g",
    "r": "lmn",
    "s": "cz",
    "t": "filr",
    "u": "no",
    "v": "fuwy",
    "w": "vur",
    "x": "rs",
    "y": "iv",
    "z": "s",
}
_INSERTABLE = "aeiourlntsy"

_LOWERCASE_WORDS = frozenset("""
a an the and or but not so if as of to in on at by for from with without
is are was were am be been being do does did have has had
it its this that these those they them their there then than
we our you your he she his her him me my
when while because although though however therefore moreover
often always usually sometimes also just only even still
""".split())

_PUNCTUATION = {
    "，": ",",
    "、": ",",
    "：": ":",
    "；": ";",
    "！": "!",
    "？": "?",
    "。": ".",
    "．": ".",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}


def _canonical(word: str) -> str:
    """Fold common OCR confusions into one spelling for lookups."""
    text = unicodedata.normalize("NFKC", word).lower().translate(_DIGIT_LOOKALIKES)
    text = re.sub(r"[^a-z']", "", text)
    text = text.replace("rn", "m").replace("cl", "d").replace("vv", "w").replace("ri", "n")
    text = text.replace("l", "i")
    if len(text) > 4 and text.endswith("mng"):
        text = text[:-3] + "ning"
    elif len(text) > 4 and text.endswith("mg"):
        text = text[:-2] + "ing"
    if len(text) > 5 and text.startswith("mt"):
        text = "int" + text[2:]
    return text


def _ends_cvc(word: str) -> bool:
    if len(word) < 3:
        return False
    first, middle, last = word[-3], word[-2], word[-1]
    return first not in "aeiou" and middle in "aeiou" and last not in "aeiouwxy"


def _inflections(word: str) -> set[str]:
    forms = {word}
    if len(word) < 2:
        return forms
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.update({word + "es", word + "s"})
    elif word.endswith("y") and word[-2] not in "aeiou":
        forms.add(word[:-1] + "ies")
    else:
        forms.add(word + "s")
    if word.endswith("e"):
        forms.update({word + "d", word[:-1] + "ing"})
    elif word.endswith("y") and word[-2] not in "aeiou":
        forms.update({word[:-1] + "ied", word + "ing"})
    else:
        forms.update({word + "ed", word + "ing"})
        if _ends_cvc(word) or word.endswith("l"):
            forms.update({word + word[-1] + "ed", word + word[-1] + "ing"})
    if len(word) <= 9:
        if word.endswith("y") and word[-2] not in "aeiou":
            forms.update({word[:-1] + "ier", word[:-1] + "iest"})
        elif word.endswith("e"):
            forms.update({word + "r", word + "st"})
        else:
            forms.update({word + "er", word + "est"})
            if _ends_cvc(word) or word.endswith("l"):
                forms.update({word + word[-1] + "er", word + word[-1] + "est"})
    return {form for form in forms if form.isalpha() and len(form) <= 22}


@lru_cache(maxsize=1)
def _forms() -> dict[str, tuple[str, int]]:
    try:
        words = WORD_LIST_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        words = []
    ranks: dict[str, int] = {}
    for index, word in enumerate(words):
        word = word.strip().lower()
        if word.isalpha():
            ranks.setdefault(word, index)
    for word in _CORE_WORDS:
        ranks.setdefault(word, 20000)

    forms: dict[str, tuple[str, int]] = {}
    for word, rank in ranks.items():
        for form in _inflections(word):
            key = _canonical(form)
            current = forms.get(key)
            if key and (current is None or rank < current[1]):
                forms[key] = (form, rank)

    # ECDICT ships exact plural/past/participle forms (including irregulars
    # such as ring -> rang/rung). They are far more reliable than heuristics.
    try:
        with gzip.open(ECDICT_PATH, "rt", encoding="utf-8") as stream:
            entries = json.load(stream)
        for word, entry in entries.items():
            rank = ranks.get(word.lower())
            if rank is None:
                continue
            for part in str(entry.get("exchange") or "").split("/"):
                key, separator, value = part.partition(":")
                if not separator or key not in {"s", "p", "d", "i", "3", "r", "t"}:
                    continue
                for form in value.split(","):
                    form = form.strip().lower()
                    if not form.isalpha() or len(form) > 22:
                        continue
                    folded = _canonical(form)
                    current = forms.get(folded)
                    if folded and (current is None or rank < current[1]):
                        forms[folded] = (form, rank)
    except (OSError, ValueError):
        pass
    return forms


def _known(word: str) -> tuple[str, int] | None:
    return _forms().get(_canonical(word))


def _is_word(word: str) -> bool:
    hit = _known(word)
    return bool(hit and hit[0].lower() == word.lower())


def _edits1(word: str, alphabet: str = _ALPHABET) -> set[str]:
    splits = [(word[:index], word[index:]) for index in range(len(word) + 1)]
    output: set[str] = set()
    for left, right in splits:
        if right:
            output.add(left + right[1:])
            if len(right) > 1:
                output.add(left + right[1] + right[0] + right[2:])
            for char in alphabet:
                output.add(left + char + right[1:])
        for char in alphabet:
            output.add(left + char + right)
    return output


def _edits1_confused(word: str) -> set[str]:
    splits = [(word[:index], word[index:]) for index in range(len(word) + 1)]
    output: set[str] = set()
    for left, right in splits:
        if right:
            output.add(left + right[1:])
            if len(right) > 1:
                output.add(left + right[1] + right[0] + right[2:])
            for char in _SUBSTITUTES.get(right[0], ""):
                output.add(left + char + right[1:])
        for char in _INSERTABLE:
            output.add(left + char + right)
    return output


def _restore_case(original: str, word: str, at_sentence_start: bool) -> str:
    if original.isupper() and len(original) > 1:
        return word.upper()
    if original[:1].isupper():
        return word.capitalize()
    return word


@lru_cache(maxsize=8192)
def _correct_token(token: str, at_sentence_start: bool = False, normalize_case: bool = True) -> str:
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9'’\-]*", token):
        return token
    if "-" in token or "'" in token or "’" in token:
        return token
    lower = token.lower()
    if normalize_case and lower in _LOWERCASE_WORDS:
        if token.isupper():
            return lower.capitalize() if at_sentence_start else lower
        if at_sentence_start:
            return token
        return lower
    if len(token) < 3:
        return token
    if token.isupper() and len(token) <= 4:
        return token
    # Leave normal Capitalised words alone mid-sentence: they are usually names,
    # places or product names that must not be swapped for a common word.
    if token[0].isupper() and token[1:].islower() and not at_sentence_start:
        return token

    folded = _canonical(token)
    if not folded:
        return token

    exact = _forms().get(folded)
    if exact:
        return _restore_case(token, exact[0], at_sentence_start)

    proper_case = token[0].isupper() and token[1:].islower()
    lower = token.lower()
    signature = (
        any(char.isdigit() for char in token)
        or any(char.isupper() for char in token[1:])
        or lower.endswith(("mg", "mng"))
        or (len(lower) > 5 and lower.startswith("mt"))
    )
    # Unknown Capitalised words are usually names or places. Only run fuzzy
    # repair on them when the spelling itself proves OCR damage. Lowercase
    # words need either a confusion signature, a longer length, or a rare
    # final "w" (as in OCR's "memow" for "memory").
    allow_repair = (not proper_case or signature) and (
        signature or len(folded) >= 7 or folded.endswith("w")
    )
    if not allow_repair:
        return token

    split = None
    if len(folded) >= 6:
        for index in range(2, len(folded) - 1):
            left, right = folded[:index], folded[index:]
            left_hit, right_hit = _forms().get(left), _forms().get(right)
            if not left_hit or not right_hit or max(left_hit[1], right_hit[1]) > 12000:
                continue
            score = left_hit[1] + right_hit[1]
            if split is None or score < split[0]:
                split = (score, left_hit, right_hit)

    found: list[tuple[int, int, str]] = []
    for candidate in _edits1(folded):
        hit = _forms().get(candidate)
        if hit and abs(len(candidate) - len(folded)) <= 1:
            found.append((1, hit[1], hit[0]))
    best_one = min((item[1] for item in found if item[0] == 1), default=10**9)
    if (not found or best_one > 4000) and len(folded) >= 5:
        for first in _edits1_confused(folded):
            for second in _edits1_confused(first):
                hit = _forms().get(second)
                if hit and hit[1] <= 8000 and abs(len(second) - len(folded)) <= 1:
                    found.append((2, hit[1], hit[0]))
    found.sort(key=lambda item: (item[0], item[1]))
    fuzzy = found[0] if found else None
    if fuzzy and fuzzy[0] == 1 and fuzzy[1] > 4000:
        alternatives = [
            item for item in found
            if item[0] == 2 and (item[1] <= 2500 or item[1] * 3 < fuzzy[1])
        ]
        if alternatives:
            fuzzy = min(alternatives, key=lambda item: item[1])

    if split:
        _score, left_hit, right_hit = split
        fuzzy_wins = fuzzy is not None and (
            fuzzy[0] == 1 or (fuzzy[0] == 2 and fuzzy[1] * 2 < min(left_hit[1], right_hit[1]))
        )
        # A function word boundary is a strong signal ("of" + "unfamiliar").
        if min(left_hit[1], right_hit[1]) <= 100 or not fuzzy_wins:
            return _restore_case(token, left_hit[0], at_sentence_start) + " " + right_hit[0]

    if fuzzy is None:
        return token
    cost, _rank, word = fuzzy
    if cost == 2 and _rank > 8000:
        return token
    if token[0].isupper() and token[1:].islower() and at_sentence_start:
        return word.capitalize()
    return _restore_case(token, word, at_sentence_start)


@lru_cache(maxsize=1)
def _protected_words() -> frozenset[str]:
    """Words that must never be swallowed by a merge."""
    try:
        lines = WORD_LIST_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    top = {line.strip().lower() for line in lines[:300] if line.strip().isalpha()}
    return frozenset(top | set(_CORE_WORDS))


def _merge_split_words(text: str) -> str:
    for _ in range(2):
        matches = list(re.finditer(r"[A-Za-z]+[’']?[A-Za-z]*", text))
        output: list[str] = []
        last = 0
        changed = False
        index = 0
        while index < len(matches) - 1:
            first, second = matches[index], matches[index + 1]
            between = text[first.end(): second.start()]
            if not between.isspace() or "\n" in between:
                index += 1
                continue
            left, right = first.group(0), second.group(0)
            left_key, right_key = _canonical(left), _canonical(right)
            # Never merge an option marker ("B") or a one-letter word. A
            # one-letter prefix only joins a longer fragment ("P assage").
            if len(right_key) == 1:
                index += 1
                continue
            if len(left_key) == 1 and (left_key in "ai" or (left[:1].isupper() and len(right_key) < 4)):
                index += 1
                continue
            combined = _forms().get(_canonical(left + right))
            left_hit = _forms().get(left_key) if _is_word(left) else None
            right_hit = _forms().get(right_key) if _is_word(right) else None
            should_merge = False
            if combined:
                rank = combined[1]
                if len(left_key) == 1 and left_key not in "ai":
                    should_merge = True
                elif not right_hit and len(right_key) <= 3:
                    should_merge = True
                elif (
                    right_hit
                    and len(right_key) <= 3
                    and right_key not in _protected_words()
                    and rank < right_hit[1]
                    and rank < 15000
                ):
                    should_merge = True
                elif left_key == "can" and right_key == "not":
                    should_merge = True
            else:
                # Adjacent lowercase fragments that are not a dictionary word
                # ("follo ving", "con finn"). Never merge across Capitalised
                # names/abbreviations such as "visited St" or "Smith visited".
                both_lower = left[:1].islower() and right[:1].islower()
                single_prefix = len(left_key) == 1 and left_key not in "ai" and right[:1].islower()
                if both_lower or single_prefix:
                    both_known = bool(left_hit and right_hit)
                    short_pair = (
                        both_known
                        and min(len(left_key), len(right_key)) <= 3
                        and left_key not in _protected_words()
                        and right_key not in _protected_words()
                    )
                    right_is_function = bool(right_hit and right_key in _protected_words())
                    if (not both_known or short_pair) and not right_is_function:
                        repaired = _correct_token(left + right, True)
                        if repaired and " " not in repaired and repaired.lower() != (left + right).lower():
                            output.append(text[last:first.start()])
                            output.append(repaired)
                            last = second.end()
                            changed = True
                            index += 2
                            continue
            if should_merge:
                output.append(text[last:first.start()])
                output.append(_restore_case(left + right, combined[0], True))
                last = second.end()
                changed = True
                index += 2
                continue
            index += 1
        output.append(text[last:])
        text = "".join(output)
        if not changed:
            break
    return text


def _join_fragments(text: str) -> str:
    """Remove bullet/pause marks inserted inside a word by OCR."""
    pattern = re.compile(r"([A-Za-z]{2,})(\s*)([、·•∙])(\s*)([A-Za-z]{2,})")

    def repl(match: re.Match) -> str:
        left, right = match.group(1), match.group(5)
        if _is_word(left) and _is_word(right):
            return match.group(0)
        return left + right

    return pattern.sub(repl, text)


def _normalize_punctuation(text: str) -> str:
    text = _join_fragments(text)
    for chinese, latin in _PUNCTUATION.items():
        escaped = re.escape(chinese)
        text = re.sub(
            r"(?<=[A-Za-z0-9\"')\]])" + escaped + r"(?=\s|[A-Za-z0-9\"'(\[]|$)",
            latin,
            text,
        )
        text = re.sub(r"(?<=[A-Za-z0-9])\s*" + escaped + r"(?=\s)", latin, text)
    # Full-width ASCII letters/digits.
    text = re.sub(r"[\uff10-\uff19\uff21-\uff3a\uff41-\uff5a]", lambda m: chr(ord(m.group(0)) - 0xFEE0), text)
    text = re.sub(r"[ \t]+([,.;:!?])", r"\1", text)
    text = re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"^([A-D])\s*[·•∙.,，、]\s*", r"\1. ", text, flags=re.M)
    text = re.sub(r"^(\d{1,2})\s*[，、．·•∙,]\s*(?!\d)", r"\1. ", text, flags=re.M)
    text = re.sub(
        r"(^|[.!?]\s+)(\d{1,2})\s*[，,、]\s*(?=[A-Z\"'])",
        lambda match: f"{match.group(1)}{match.group(2)}. ",
        text,
        flags=re.M,
    )
    text = re.sub(r"\bt['’](?=[A-Za-z]{2,})", '"', text)
    return text


def _split_merged_options(text: str) -> str:
    """Separate options that OCR glued onto one line: 'A. x B. y'."""
    lines: list[str] = []
    for line in text.splitlines():
        if re.match(r"^[A-D][.)]\s+", line):
            line = re.sub(
                r"\s+([B-D0])[.)]?\s+(?=[A-Za-z])",
                lambda match: "\n" + ("D" if match.group(1) == "0" else match.group(1)) + ". ",
                line,
            )
        lines.append(line)
    return "\n".join(lines)


def correct_text(text: str) -> str:
    """Normalise punctuation and repair OCR word errors, line by line."""
    trailing_newline = "\n" if text.endswith("\n") else ""
    text = _normalize_punctuation(text)
    text = _split_merged_options(text)
    text = _merge_split_words(text)
    output: list[str] = []
    for line in text.splitlines():
        pieces: list[str] = []
        position = 0
        tokens = list(re.finditer(r"[A-Za-z][A-Za-z0-9'’\-]*", line))
        capitals = sum(1 for match in tokens if match.group(0)[:1].isupper())
        title_case = len(tokens) >= 2 and capitals / len(tokens) >= 0.6
        for index, match in enumerate(tokens):
            pieces.append(line[position: match.start()])
            before = line[: match.start()].rstrip()
            at_start = not before or bool(re.search(r"[.!?\"')\]]\s*$", before))
            next_capital = index + 1 < len(tokens) and tokens[index + 1].group(0)[:1].isupper()
            keep_case = title_case or (match.group(0)[:1].isupper() and next_capital)
            pieces.append(_correct_token(match.group(0), at_start, normalize_case=not keep_case))
            position = match.end()
        pieces.append(line[position:])
        output.append("".join(pieces))
    return "\n".join(output) + trailing_newline


def score_text(text: str) -> float:
    """Score an OCR candidate: real words plus retained letter coverage."""
    tokens = re.findall(r"[A-Za-z][A-Za-z']*", text)
    if not tokens:
        return 0.0
    known = sum(1 for token in tokens if _canonical(token) in _forms())
    ratio = known / len(tokens)
    letters = len(re.findall(r"[A-Za-z]", text))
    return known * (0.5 + ratio) + min(1.0, letters / 900.0) * 2.0

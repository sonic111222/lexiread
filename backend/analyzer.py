"""Rule-based exam parsing and study-material extraction.

The goal here is not to guess exam answers. It turns noisy OCR text into a
clean reading view and produces reliable local study material: useful words,
phrases, key sentences and question-navigation hints. AI adds translations and
explanations on top when the learner configures a model.
"""
from __future__ import annotations

import math
import re
from collections import Counter, OrderedDict
from typing import Iterable, Optional

WORD_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*")
QUESTION_START_RE = re.compile(r"^\s*(?:Q\s*)?(\d{1,2})\s*[.)、:]\s*(.*)$", re.I)
QUESTION_ANY_RE = re.compile(r"^\s*(?:Q\s*)?(\d{1,2})\s*[.)、:]\s*", re.I)
OPTION_LABEL_RE = re.compile(r"(?:^|(?<=\s))\(?([A-H])\)?\s*[.)、:]\s*", re.I)
OPTION_LINE_RE = re.compile(r"^\s*\(?([A-H])\)?\s*[.)、:]\s*(.*)$", re.I)
BLANK_RE = re.compile(r"(?:_{2,}\s*\d{1,2}\s*_{2,}|_{2,}|…{2,}|\(\s*\)|\[\s*\])")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[\"'“”‘’(]?[A-Z0-9])")

STOPWORDS = {
    "a", "about", "above", "across", "after", "again", "against", "all", "almost", "along",
    "already", "also", "although", "always", "am", "among", "an", "and", "another", "any",
    "anyone", "anything", "are", "around", "as", "at", "back", "be", "became", "because",
    "become", "becomes", "been", "before", "being", "below", "best", "better", "between",
    "both", "but", "by", "can", "cannot", "could", "did", "do", "does", "doing", "done",
    "down", "during", "each", "either", "else", "enough", "even", "ever", "every", "few",
    "first", "for", "from", "further", "get", "gets", "getting", "go", "goes", "going",
    "gone", "got", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "however", "i", "if", "in", "into", "is", "it", "its",
    "itself", "just", "keep", "kept", "last", "later", "least", "less", "let", "like",
    "likely", "little", "long", "made", "make", "makes", "making", "many", "may", "me",
    "might", "more", "most", "mostly", "much", "must", "my", "myself", "near", "need",
    "needs", "never", "new", "next", "no", "nor", "not", "now", "of", "off", "often",
    "on", "once", "one", "only", "or", "other", "others", "otherwise", "our", "ours",
    "ourselves", "out", "over", "own", "perhaps", "put", "quite", "rather", "really",
    "said", "same", "say", "says", "see", "seem", "seemed", "seems", "she", "should",
    "since", "so", "some", "someone", "something", "sometimes", "still", "such", "take",
    "taken", "takes", "taking", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "thing", "things", "think", "this",
    "those", "though", "through", "thus", "to", "today", "together", "too", "toward",
    "towards", "two", "under", "until", "up", "upon", "us", "use", "used", "uses",
    "using", "very", "was", "way", "ways", "we", "well", "went", "were", "what", "when",
    "where", "whether", "which", "while", "who", "whole", "whom", "whose", "why", "will",
    "with", "within", "without", "would", "yes", "yet", "you", "your", "yours",
    "yourself", "yourselves", "according", "answer", "answers", "article", "blank",
    "blanks", "choose", "closest", "complete", "correct", "directions", "false",
    "following", "incorrect", "mainly", "meaning", "option", "options", "paragraph",
    "paragraphs", "passage", "probably", "question", "questions", "read", "reading",
    "sentence", "sentences", "text", "true", "word", "words", "write", "writer",
}

TEST_INSTRUCTION_PREFIXES = (
    "read the following",
    "read the passage",
    "choose the best",
    "complete the",
    "in this section",
    "directions:",
    "the passage below",
    "answer the questions",
)

FUNCTION_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "by",
    "for", "with", "from", "as", "that", "this", "these", "those", "is", "are", "was",
    "were", "be", "been", "being", "it", "its", "we", "our", "you", "your", "they",
    "their", "he", "she", "his", "her", "not", "no", "so", "than", "too", "very",
    "can", "could", "will", "would", "should", "may", "might", "must", "do", "does",
    "did", "have", "has", "had", "about", "into", "over", "under", "after", "before",
    "between", "through", "during", "without", "within", "up", "down", "out", "off",
    "also", "only", "more", "most", "such", "when", "where", "which", "who", "whom",
    "whose", "what", "why", "how", "there", "here", "them", "us", "me", "my", "mine",
    "each", "both", "either", "neither", "other", "another", "some", "any", "all",
}

ELEMENTARY_WORDS = {
    "able", "about", "afternoon", "again", "age", "ago", "air", "animal", "answer", "apple",
    "area", "ask", "baby", "back", "bad", "bag", "ball", "bank", "bed", "big", "bird",
    "black", "blue", "boat", "body", "book", "box", "boy", "bread", "breakfast", "bring",
    "brother", "brown", "bus", "buy", "call", "car", "cat", "chair", "child", "children",
    "city", "class", "clean", "clock", "close", "clothes", "cloud", "coat", "cold", "color",
    "come", "computer", "cook", "cool", "country", "cup", "cut", "dad", "day", "desk",
    "dinner", "dog", "door", "down", "draw", "dress", "drink", "drive", "ear", "early",
    "earth", "easy", "eat", "egg", "eight", "evening", "eye", "face", "family", "far",
    "farm", "fast", "father", "few", "field", "find", "fine", "finger", "fire", "first",
    "fish", "five", "floor", "flower", "fly", "food", "foot", "for", "four", "free",
    "friend", "from", "fruit", "full", "fun", "game", "garden", "get", "girl", "give",
    "glad", "glass", "go", "good", "grass", "great", "green", "grow", "hair", "half",
    "hand", "happy", "hard", "hat", "have", "head", "hear", "help", "here", "high",
    "hill", "home", "hope", "horse", "hot", "hour", "house", "how", "hundred", "ice",
    "idea", "ill", "important", "interest", "into", "job", "jump", "keep", "key", "kid",
    "kind", "king", "kitchen", "know", "lake", "land", "large", "last", "late", "learn",
    "leave", "left", "leg", "lesson", "let", "letter", "life", "light", "like", "line",
    "listen", "little", "live", "long", "look", "lot", "love", "low", "lunch", "make",
    "man", "many", "map", "may", "meat", "meet", "milk", "mind", "minute", "miss", "mom",
    "money", "month", "moon", "more", "morning", "mother", "mountain", "mouth", "move",
    "music", "name", "near", "need", "never", "new", "news", "next", "night", "nine",
    "no", "north", "nose", "note", "now", "number", "old", "one", "open", "or", "orange",
    "other", "out", "page", "paper", "parent", "park", "part", "party", "pass", "pay",
    "pen", "pencil", "people", "person", "phone", "picture", "place", "plan", "plant",
    "play", "please", "point", "poor", "put", "question", "quick", "quickly", "rain",
    "read", "reading", "ready", "red", "remember", "rest", "rice", "rich", "ride",
    "right", "river", "road", "room", "run", "sad", "same", "say", "school", "sea",
    "see", "sell", "send", "seven", "she", "ship", "shoe", "shop", "short", "show",
    "sing", "sister", "sit", "six", "sleep", "slow", "slowly", "small", "smile", "snow",
    "so", "some", "son", "song", "soon", "sound", "speak", "stand", "star", "start",
    "stay", "stop", "street", "strong", "student", "study", "sun", "table", "take",
    "talk", "tall", "tea", "teach", "teacher", "tell", "ten", "text", "texts", "thank",
    "that", "the", "their", "them", "then", "there", "these", "they", "thing", "think",
    "this", "those", "three", "time", "today", "tomorrow", "too", "town", "tree", "try",
    "turn", "two", "under", "up", "use", "very", "walk", "wall", "want", "warm", "wash",
    "watch", "water", "way", "we", "wear", "week", "well", "west", "what", "when",
    "where", "which", "white", "who", "why", "wide", "will", "wind", "window", "winter",
    "with", "woman", "women", "word", "words", "work", "world", "write", "wrong", "year",
    "yellow", "yes", "yesterday", "you", "young",
}
ELEMENTARY_WORDS |= {
    "families", "images", "moment", "moments", "pictures", "remember", "somewhere",
    "stories", "story", "thousands", "understand",
}

GENERIC_HEADINGS = {
    "reading comprehension",
    "reading",
    "passage",
    "cloze",
    "cloze test",
    "reading passage",
    "english reading",
    "阅读理解",
    "完形填空",
}

PHRASE_BANK = [
    "as a result", "on the other hand", "in addition", "for example", "for instance",
    "in fact", "of course", "at the same time", "by contrast", "in contrast",
    "in conclusion", "to sum up", "in other words", "on average", "in particular",
    "rather than", "instead of", "due to", "because of", "according to", "as well as",
    "such as", "so that", "even though", "as long as", "in order to", "be able to",
    "be likely to", "be used to", "be interested in", "be based on", "be aware of",
    "take part in", "play a role in", "play a part in", "make a difference",
    "make sense", "make sure", "make use of", "take advantage of", "come up with",
    "look forward to", "pay attention to", "focus on", "depend on", "rely on",
    "deal with", "refer to", "result in", "result from", "lead to", "contribute to",
    "belong to", "consist of", "insist on", "worry about", "think about", "care about",
    "find out", "figure out", "point out", "carry out", "give up", "take up", "set up",
    "bring about", "break down", "turn out", "work out", "go through", "look for",
    "look after", "look into", "put off", "pick up", "hold on", "show up", "stand out",
    "run out of", "keep up with", "catch up with", "get along with", "get rid of",
    "in terms of", "regardless of", "thanks to", "apart from", "along with",
    "together with", "far from", "close to", "next to", "in front of", "in the end",
    "at first", "at last", "once again", "more and more", "less and less",
    "no longer", "as soon as", "ever since", "by the time", "in time", "on time",
    "at least", "at most", "in general", "in short", "after all", "above all",
    "at all", "more than", "less about", "willing to", "take time to", "slow down",
    "calm down", "throw away", "pass down", "pass on", "in a world", "in this sense",
    "a growing number of", "a number of", "the ability to", "that is why",
    "from generation to generation", "one generation to the next", "call for",
]

QUESTION_TYPES = {
    "main": (
        "主旨大意",
        "关注首段、末段和每段首句。正确选项通常能覆盖全文，而不是只概括某一段或某个细节。",
    ),
    "detail": (
        "细节理解",
        "先圈出题干里的名词、时间、数字和动作，再回原文找同义改写。警惕偷换对象、范围和时态。",
    ),
    "infer": (
        "推理判断",
        "答案通常不在原文原句中。用原文事实只推一步，排除文中未提及或推得过远的选项。",
    ),
    "vocab": (
        "词义猜测",
        "把选项代回原句，结合上下句的逻辑关系、感情色彩和并列结构判断，不要只凭生词表印象。",
    ),
    "attitude": (
        "观点态度",
        "圈出评价性形容词、情态动词和转折词，区分作者态度与文中人物的态度。",
    ),
    "structure": (
        "篇章结构",
        "先给每段写一个 3–5 字的小标题，再看段落之间是并列、递进、转折还是因果。",
    ),
    "cloze": (
        "完形填空",
        "先通读全文把握主线，再从句意、固定搭配和语法形式三个层面排除。注意空格前后的介词、连词和主谓一致。",
    ),
    "matching": (
        "信息匹配",
        "用题干中的专有名词、数字或独特表达快速定位，再核对选项是否完整对应原文信息。",
    ),
}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u200b", "")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_heading(line: str) -> bool:
    clean = line.strip().strip(":").lower()
    if clean in GENERIC_HEADINGS:
        return True
    return bool(re.match(r"^(passage|part|section|unit)\s+[0-9ivxa-z]+", line, re.I))


def _find_question_zone(lines: list[str]) -> int:
    candidates = [i for i, line in enumerate(lines) if QUESTION_START_RE.match(line)]
    if not candidates:
        return -1
    for idx in candidates:
        line = lines[idx]
        if len(OPTION_LABEL_RE.findall(line)) >= 2:
            return idx
        window = [l for l in lines[idx + 1: idx + 10] if l.strip()]
        if any(OPTION_LINE_RE.match(l) for l in window):
            return idx
        # A run of numbered questions without options (short answer / cloze stems).
        numbered = sum(1 for l in lines[idx: idx + 60] if QUESTION_START_RE.match(l))
        if numbered >= 2 and idx >= max(0, len(lines) // 3):
            return idx
        rest = QUESTION_START_RE.match(line).group(2) if QUESTION_START_RE.match(line) else ""
        if (
            idx >= len(lines) * 0.55
            and (
                "?" in rest
                or re.match(
                    r"^(what|why|how|which|who|whom|where|when|according|the author|the passage|"
                    r"it can be|we can|from the|in the)",
                    rest.strip(),
                    re.I,
                )
            )
        ):
            return idx
    # Fall back to the last question-looking line if the text clearly looks like a quiz.
    return candidates[0] if len(candidates) > 1 else -1


def _split_option_chunks(text: str) -> Optional[tuple[str, list[dict]]]:
    matches = list(OPTION_LABEL_RE.finditer(text))
    if len(matches) < 2:
        return None
    stem = text[: matches[0].start()].strip()
    options = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[match.end(): end].strip(" \t,;")
        if value:
            options.append({"label": match.group(1).upper(), "text": value})
    if len(options) < 2:
        return None
    return stem, options


def _parse_questions(lines: list[str]) -> list[dict]:
    questions: list[dict] = []
    current: Optional[dict] = None
    current_option: Optional[dict] = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^questions?\s+\d+", line, re.I):
            continue
        q_match = QUESTION_START_RE.match(line)
        if q_match:
            number = int(q_match.group(1))
            rest = q_match.group(2).strip()
            # Ignore a numbered line that is clearly an instruction.
            if re.match(r"^(?:points?|marks?|minute|min\.)", rest, re.I):
                continue
            current_option = None
            inline = _split_option_chunks(rest)
            option_only = OPTION_LINE_RE.match(rest)
            if inline:
                stem, options = inline
                current = {"number": number, "stem": stem, "options": options}
            elif option_only:
                current = {
                    "number": number,
                    "stem": "",
                    "options": [{"label": option_only.group(1).upper(), "text": option_only.group(2).strip()}],
                }
            else:
                current = {"number": number, "stem": rest, "options": []}
            questions.append(current)
            continue

        if current is None:
            continue

        inline_on_line = _split_option_chunks(line)
        if inline_on_line and not inline_on_line[0] and len(inline_on_line[1]) >= 2:
            # A line like "A. red B. blue C. green D. black".
            current["options"].extend(inline_on_line[1])
            current_option = current["options"][-1]
            continue

        option_match = OPTION_LINE_RE.match(line)
        if option_match:
            label = option_match.group(1).upper()
            content = option_match.group(2).strip()
            current_option = {"label": label, "text": content}
            current["options"].append(current_option)
            continue

        inline = _split_option_chunks(line)
        if inline and len(inline[1]) >= 2:
            stem, options = inline
            if not current["stem"]:
                current["stem"] = stem
            current["options"].extend(options)
            current_option = current["options"][-1] if current["options"] else None
            continue

        # Continuation of the last option or of the question stem.
        if current_option is not None:
            current_option["text"] = f"{current_option['text']} {line}".strip()
        else:
            current["stem"] = f"{current['stem']} {line}".strip()

    # Normalise and deduplicate option labels.
    for question in questions:
        seen = set()
        clean_options = []
        for option in question.get("options", []):
            label = option["label"].upper()
            text = re.sub(r"\s+", " ", option["text"]).strip()
            if label in seen or not text:
                continue
            seen.add(label)
            clean_options.append({"label": label, "text": text})
        question["options"] = sorted(clean_options, key=lambda item: item["label"])
        question["stem"] = re.sub(r"\s+", " ", question.get("stem", "")).strip()
    return questions


def _extract_content_words(text: str) -> list[str]:
    words = []
    for token in WORD_RE.findall(text):
        lower = token.lower()
        if lower in STOPWORDS or len(lower) < 3:
            continue
        words.append(lower)
    return words


def _split_sentences(text: str) -> list[str]:
    protected = re.sub(
        r"\b(Mr|Mrs|Ms|Dr|Prof|St|Jr|Sr|etc|e\.g|i\.e|vs|a\.m|p\.m)\.", r"\1<DOT>", text
    )
    parts = SENTENCE_SPLIT_RE.split(protected)
    result = []
    for part in parts:
        part = part.replace("<DOT>", ".").strip()
        if len(WORD_RE.findall(part)) >= 3:
            result.append(part)
    return result


def _sentence_records(paragraphs: list[str]) -> list[dict]:
    records = []
    for p_index, paragraph in enumerate(paragraphs, 1):
        for sentence in _split_sentences(paragraph):
            records.append({"sentence": sentence, "paragraph": p_index, "words": len(WORD_RE.findall(sentence))})
    return records


def _find_title_and_instructions(lines: list[str]) -> tuple[str, list[str], list[str]]:
    title = ""
    instructions: list[str] = []
    body_start = 0

    for idx, line in enumerate(lines):
        clean = line.strip()
        if not clean:
            continue
        lower = clean.lower().rstrip(":")
        is_instruction = lower.startswith(TEST_INSTRUCTION_PREFIXES)
        is_generic = _is_heading(clean) and lower not in {"cloze test", "cloze"}
        if is_instruction:
            instructions.append(clean)
            body_start = idx + 1
            continue
        if is_generic and not title:
            instructions.append(clean)
            body_start = idx + 1
            continue
        if not title and not QUESTION_START_RE.match(clean):
            words = WORD_RE.findall(clean)
            looks_like_title = (
                len(words) <= 14
                and len(clean) <= 110
                and not re.search(r"[.!?]$", clean)
                and not clean.endswith(":")
                and not _is_heading(clean)
            )
            # OCR occasionally merges a title with the first sentence. In that
            # case keep the whole line in the body instead of losing content.
            if looks_like_title:
                title = clean.strip("\"' ")
                body_start = idx + 1
                continue
        break

    body = lines[body_start:]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return title, instructions, body


def _clean_stem(stem: str) -> str:
    stem = re.sub(r"\s+", " ", stem).strip()
    stem = re.sub(r"^\s*[.、]\s*", "", stem)
    return stem


def _classify_question(question: dict, cloze: bool) -> tuple[str, str, str]:
    if cloze:
        return ("cloze", *QUESTION_TYPES["cloze"])
    stem = question.get("stem", "").lower()
    if re.search(r"\b(main idea|mainly about|mainly discuss|best title|primary purpose|purpose of|mainly concerned)", stem):
        return ("main", *QUESTION_TYPES["main"])
    if re.search(r"\b(closest in meaning|most nearly means|refers? to|stand for|the word .* mean)", stem):
        return ("vocab", *QUESTION_TYPES["vocab"])
    if re.search(r"\b(infer|imply|implies|suggest|learn from|can be concluded|conclusion can)", stem):
        return ("infer", *QUESTION_TYPES["infer"])
    if re.search(r"\b(attitude|tone|feel about|view of)", stem):
        return ("attitude", *QUESTION_TYPES["attitude"])
    if re.search(r"\b(structure|organi[sz]ed|order of|development of the passage)", stem):
        return ("structure", *QUESTION_TYPES["structure"])
    if re.search(r"\b(according to|why|what|which|who|when|where|how|because|mention|true|false|except)\b", stem):
        return ("detail", *QUESTION_TYPES["detail"])
    return ("matching", *QUESTION_TYPES["matching"])


def _blank_contexts(paragraphs: list[str]) -> list[dict]:
    contexts: list[dict] = []
    for p_index, paragraph in enumerate(paragraphs, 1):
        for match in BLANK_RE.finditer(paragraph):
            before = paragraph[max(0, match.start() - 180): match.start()]
            after = paragraph[match.end(): match.end() + 180]
            # Approximate the sentence around the blank.
            left_bound = max(before.rfind("."), before.rfind("?"), before.rfind("!"), before.rfind(";"))
            right_candidates = [p for p in (after.find("."), after.find("?"), after.find("!"), after.find(";")) if p >= 0]
            right_bound = min(right_candidates) if right_candidates else len(after)
            prefix = before[left_bound + 1:].strip()
            suffix = after[: right_bound + 1].strip()
            sentence = re.sub(r"\s+", " ", f"{prefix} ______ {suffix}").strip()
            sentence = re.sub(r"\s+([,.;:!?])", r"\1", sentence)
            number = None
            embedded_number = re.search(r"\d{1,2}", match.group(0))
            if embedded_number:
                number = int(embedded_number.group(0))
            else:
                number_match = re.search(r"(\d{1,2})\s*$", before[-6:])
                if number_match:
                    number = int(number_match.group(1))
            contexts.append(
                {
                    "blank_index": len(contexts) + 1,
                    "number": number,
                    "paragraph": p_index,
                    "context": sentence,
                }
            )
    return contexts


def _evidence_for_question(question: dict, sentences: list[dict], cloze_context: Optional[dict], q_type: str = "") -> dict:
    if cloze_context:
        return {
            "keywords": _extract_content_words(question.get("stem", ""))[:5],
            "evidence": [
                {
                    "sentence": cloze_context["context"],
                    "paragraph": cloze_context["paragraph"],
                    "matched": [],
                    "score": 1.0,
                }
            ],
        }

    stem_words = _extract_content_words(question.get("stem", ""))
    option_words = _extract_content_words(" ".join(o["text"] for o in question.get("options", [])))
    keyword_scores: OrderedDict[str, int] = OrderedDict()
    for word in stem_words:
        keyword_scores[word] = keyword_scores.get(word, 0) + 3
    for word in option_words:
        keyword_scores[word] = keyword_scores.get(word, 0) + 1
    keywords = sorted(keyword_scores, key=lambda w: (-keyword_scores[w], -len(w)))[:7]

    if q_type in ("main", "structure") and sentences:
        picks = [sentences[0]]
        last = sentences[-1]
        if last is not sentences[0]:
            picks.append(last)
        return {
            "keywords": keywords,
            "evidence": [
                {
                    "sentence": record["sentence"],
                    "paragraph": record["paragraph"],
                    "matched": [],
                    "score": 0.5,
                }
                for record in picks
            ],
        }

    scored = []
    for record in sentences:
        sent_words = set(_extract_content_words(record["sentence"]))
        stem_hits = [w for w in stem_words if w in sent_words]
        option_hits = [w for w in option_words if w in sent_words]
        score = len(stem_hits) * 2.0 + len(option_hits) * 0.45
        if score > 0:
            scored.append(
                {
                    "sentence": record["sentence"],
                    "paragraph": record["paragraph"],
                    "matched": sorted(set(stem_hits + option_hits), key=lambda w: -len(w))[:6],
                    "score": round(score, 2),
                }
            )
    scored.sort(key=lambda item: item["score"], reverse=True)
    # Avoid returning almost identical overlapping sentences.
    unique: list[dict] = []
    best_score = scored[0]["score"] if scored else 0
    for item in scored:
        if item is not scored[0] and item["score"] < max(1.0, best_score * 0.45):
            continue
        if any(item["sentence"][:80] in existing["sentence"] or existing["sentence"][:80] in item["sentence"] for existing in unique):
            continue
        unique.append(item)
        if len(unique) == 2:
            break
    return {"keywords": keywords, "evidence": unique}


def _focus_vocabulary(text: str, sentences: list[dict], blanks: list[dict], limit: int = 14) -> list[dict]:
    counts: Counter[str] = Counter()
    display: dict[str, str] = {}
    first_sentence: dict[str, str] = {}
    first_pos: dict[str, int] = {}
    for match in WORD_RE.finditer(text):
        token = match.group(0)
        lower = token.lower()
        if len(lower) < 4 or lower in STOPWORDS:
            continue
        if lower in ELEMENTARY_WORDS and len(lower) <= 7:
            continue
        if lower.isdigit():
            continue
        counts[lower] += 1
        display.setdefault(lower, token)
        first_pos.setdefault(lower, match.start())

    blank_words: set[str] = set()
    for blank in blanks:
        blank_words.update(_extract_content_words(blank["context"]))

    for record in sentences:
        for match in WORD_RE.finditer(record["sentence"]):
            lower = match.group(0).lower()
            if lower in counts and lower not in first_sentence:
                first_sentence[lower] = record["sentence"]

    scored = []
    for word, count in counts.items():
        if word in STOPWORDS:
            continue
        if word in ELEMENTARY_WORDS and len(word) <= 7:
            continue
        score = count * 2.0 + min(len(word), 12) * 0.45
        if word in ELEMENTARY_WORDS:
            score -= 3.0
        if word in blank_words:
            score += 1.2
        if re.search(r"(tion|sion|ment|ness|ity|ous|ive|ful|less|able|ible|al)$", word):
            score += 0.6
        if word.isalpha() and len(word) >= 8:
            score += 0.5
        scored.append((score, count, word))
    scored.sort(key=lambda item: (-item[0], item[2]))
    results = []
    used_roots: set[str] = set()
    for score, count, word in scored:
        root = re.sub(r"(ing|ed|es|s|ly)$", "", word)
        if root in used_roots:
            continue
        used_roots.add(root)
        results.append(
            {
                "word": display.get(word, word),
                "lookup": word,
                "count": count,
                "context": _clean_blank_markers(first_sentence.get(word, "")),
                "score": round(score, 2),
                "priority": "high" if score >= 7 else "normal",
            }
        )
        if len(results) >= limit:
            break
    return results


def _clean_blank_markers(text: str) -> str:
    return re.sub(r"(?:_{2,}\s*\d{0,2}\s*_{2,}|_{2,})", "______", text)


def _sentence_around(text: str, start: int, end: int) -> str:
    left_candidates = [text.rfind(mark, 0, start) for mark in (".", "?", "!", ";")]
    left = max(left_candidates)
    right_candidates = [pos for pos in (text.find(mark, end) for mark in (".", "?", "!", ";")) if pos >= 0]
    right = min(right_candidates) if right_candidates else min(len(text), end + 160)
    sentence = re.sub(r"\s+", " ", text[left + 1: right + 1]).strip()
    return _clean_blank_markers(sentence) or _clean_blank_markers(re.sub(r"\s+", " ", text[start:end]).strip())


def _ngram_phrases(text: str, limit: int = 8) -> list[dict]:
    """Extract repeated two-word collocations such as "slow reading"."""
    tokens = [(m.group(0), m.start(), m.end()) for m in WORD_RE.finditer(text)]
    buckets: dict[str, dict] = {}
    for i in range(len(tokens) - 1):
        prev, nxt = tokens[i], tokens[i + 1]
        between = text[prev[2]: nxt[1]]
        if not re.fullmatch(r"[\s'’\-]*", between):
            continue
        words = [prev[0], nxt[0]]
        lower_words = [word.lower() for word in words]
        if any(word in FUNCTION_WORDS for word in lower_words):
            continue
        if any(len(word) < 3 for word in words):
            continue
        normalized = " ".join(lower_words)
        entry = buckets.setdefault(
            normalized,
            {
                "phrase": text[prev[1]: nxt[2]],
                "normalized": normalized,
                "count": 0,
                "context": _sentence_around(text, prev[1], nxt[2]),
                "position": prev[1],
                "kind": "高频搭配",
            },
        )
        entry["count"] += 1

    candidates = []
    for entry in buckets.values():
        if entry["count"] < 2:
            continue
        words = entry["normalized"].split()
        content_len = sum(len(word) for word in words)
        score = entry["count"] * 2.4 + content_len / 4
        entry["score"] = round(score, 2)
        candidates.append(entry)
    candidates.sort(key=lambda item: (-item["score"], -item["count"], item["position"]))
    return candidates[:limit]


def _find_phrases(text: str) -> list[dict]:
    found = []
    for phrase in PHRASE_BANK:
        pattern = re.compile(r"(?<![A-Za-z])" + re.escape(phrase).replace(r"\ ", r"\s+") + r"(?![A-Za-z])", re.I)
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        found.append(
            {
                "phrase": matches[0].group(0),
                "normalized": phrase,
                "count": len(matches),
                "context": _sentence_around(text, matches[0].start(), matches[0].end()),
                "position": matches[0].start(),
                "kind": "固定短语",
                "score": 3.0 + len(matches) * 1.5,
            }
        )

    curated = {item["normalized"] for item in found}
    for item in _ngram_phrases(text, limit=8):
        if any(item["normalized"] in phrase or phrase in item["normalized"] for phrase in curated):
            continue
        found.append(item)

    found.sort(key=lambda item: (-item.get("score", 0), -item["count"], item["position"]))
    # Remove phrases that are fully contained in a longer, equally frequent phrase.
    pruned = []
    for item in found:
        if any(
            item is not other
            and item["normalized"] in other["normalized"]
            and len(other["normalized"]) > len(item["normalized"])
            and other["count"] >= item["count"]
            for other in found
        ):
            continue
        pruned.append(item)
    return pruned[:12]


def _key_sentences(sentences: list[dict], limit: int = 6) -> list[dict]:
    markers = {
        "however": ("转折句", "转折之后往往是作者真正的观点。"),
        "but": ("转折句", "转折之后的信息常是命题重点。"),
        "although": ("让步句", "让步之后的主句承载核心观点。"),
        "yet": ("转折句", "转折之后的信息常是命题重点。"),
        "therefore": ("结论句", "注意由前文推出的结论。"),
        "thus": ("结论句", "这是由前文逻辑推出的结果。"),
        "in conclusion": ("结论句", "文章收束处常概括主旨。"),
        "as a result": ("因果句", "注意原因与结果的对应关系。"),
        "because": ("因果句", "原因往往是细节题和推断题的依据。"),
        "in fact": ("观点句", "作者用事实强化或修正前面的说法。"),
        "the main": ("主旨句", "直接概括文章的核心观点。"),
        "important": ("观点句", "作者明确强调的内容值得关注。"),
        "suggest": ("观点句", "研究或作者的建议常对应推断题。"),
        "show": ("观点句", "证据所支持的观点常是考点。"),
        "means": ("观点句", "解释性内容常对应词义或推断题。"),
        "for example": ("例证句", "例子服务于其前后的观点。"),
        "for instance": ("例证句", "例子服务于其前后的观点。"),
        "on the other hand": ("对比句", "对比双方的观点差异是常考点。"),
    }
    scored = []
    last_paragraph = max((record["paragraph"] for record in sentences), default=1)
    for index, record in enumerate(sentences):
        sentence = record["sentence"]
        lower = sentence.lower()
        score = 0.0
        label = ""
        reason = ""
        for marker, (candidate_label, candidate_reason) in markers.items():
            if re.search(r"\b" + re.escape(marker), lower):
                score += 1.6
                if not label:
                    label, reason = candidate_label, candidate_reason
        if record["paragraph"] == 1 and index < 2:
            score += 1.7
            label = label or "开篇句"
            reason = reason or "开篇常交代背景或引出主题。"
        if record["paragraph"] == last_paragraph:
            score += 1.1
        if record["words"] >= 28:
            score += 0.9
            label = label or "长难句"
            reason = reason or "句子较长，先找主干，再逐层加入修饰成分。"
        if "?" in sentence:
            score -= 1.0
        if score <= 0:
            continue
        scored.append(
            {
                "sentence": sentence,
                "paragraph": record["paragraph"],
                "label": label or "关键句",
                "reason_zh": reason or "该句包含重要信息或逻辑信号词。",
                "score": round(score, 2),
                "word_count": record["words"],
            }
        )
    scored.sort(key=lambda item: (-item["score"], item["paragraph"]))
    result = []
    seen = set()
    for item in scored:
        key = item["sentence"][:60].lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    result.sort(key=lambda item: item["paragraph"])
    return result


def _difficulty(text: str) -> dict:
    words = WORD_RE.findall(text)
    sentences = [s for s in _split_sentences(text) if len(WORD_RE.findall(s)) >= 3]
    if not words:
        return {"label": "未评估", "score": 0, "reading_minutes": 1}
    avg_word = sum(len(word) for word in words) / len(words)
    long_ratio = sum(1 for word in words if len(word) >= 8) / len(words)
    avg_sentence = len(words) / max(1, len(sentences))
    score = avg_word * 1.05 + long_ratio * 8.5 + min(avg_sentence, 36) / 10
    if score < 7.4:
        label = "基础 · A2–B1"
    elif score < 8.6:
        label = "中级 · B1–B2"
    elif score < 9.7:
        label = "中高级 · CET-4"
    elif score < 10.8:
        label = "进阶 · CET-6"
    else:
        label = "挑战 · 考研/雅思"
    return {
        "label": label,
        "score": round(score, 2),
        "reading_minutes": max(1, math.ceil(len(words) / 180)),
    }


def analyze(text: str, override_title: str = "") -> dict:
    """Parse OCR/pasted text into a reading sheet plus local study material."""
    raw = _clean_text(text)
    if not raw:
        raise ValueError("没有可分析的文本。")
    lines = raw.split("\n")
    question_zone_index = _find_question_zone(lines)
    if question_zone_index >= 0:
        passage_lines = lines[:question_zone_index]
        question_lines = lines[question_zone_index:]
    else:
        passage_lines = lines
        question_lines = []

    preliminary_questions = _parse_questions(question_lines) if question_lines else []
    cloze_contexts = _blank_contexts([p for p in re.split(r"\n{2,}", "\n".join(passage_lines)) if p.strip()])
    empty_stems = sum(1 for q in preliminary_questions if not q.get("stem"))
    cloze = bool(preliminary_questions) and (
        empty_stems >= max(1, len(preliminary_questions) * 0.5)
        or (len(cloze_contexts) >= 2 and empty_stems >= 1)
    )

    kind = "cloze" if cloze else ("reading" if preliminary_questions else "text")
    detected_title, instructions, body_lines = _find_title_and_instructions(passage_lines)
    title = (override_title or detected_title or "").strip()
    if not title:
        title = "完形填空精读" if cloze else "阅读精读"

    # Group body lines into paragraphs. Blank lines are strong paragraph breaks.
    paragraphs: list[str] = []
    current: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            continue
        if _is_instruction_line(stripped):
            if current:
                paragraphs.append(" ".join(current).strip())
                current = []
            instructions.append(stripped)
            continue
        if _is_heading(stripped) and current:
            paragraphs.append(" ".join(current).strip())
            current = []
        current.append(stripped)
    if current:
        paragraphs.append(" ".join(current).strip())
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p.strip()]
    if not paragraphs and raw:
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n{2,}", raw) if p.strip()]

    passage_text = "\n\n".join(paragraphs)
    sentences = _sentence_records(paragraphs)
    # Recompute the blank contexts against the final, cleaned paragraphs so
    # paragraph numbers line up with what the learner sees.
    cloze_contexts = _blank_contexts(paragraphs)
    all_context_text = passage_text

    contexts_by_number = {}
    for idx, context in enumerate(cloze_contexts, 1):
        contexts_by_number[context.get("number") or idx] = context

    questions = []
    for q in preliminary_questions:
        stem = _clean_stem(q.get("stem", ""))
        q_type, type_label, strategy = _classify_question({**q, "stem": stem}, cloze)
        cloze_context = contexts_by_number.get(q["number"]) if cloze else None
        evidence = _evidence_for_question({**q, "stem": stem}, sentences, cloze_context, q_type)
        questions.append(
            {
                "number": q["number"],
                "stem": stem,
                "options": q["options"],
                "context": (cloze_context or {}).get("context", ""),
                "type": q_type,
                "type_label": type_label,
                "strategy_zh": strategy,
                "keywords": evidence["keywords"],
                "evidence": evidence["evidence"],
                "local_hint": (
                    "查看空格所在句的搭配与语法关系，再用选项逐一还原。"
                    if cloze
                    else "先看定位词，再回到原文核对同义改写；本地模式不判断答案。"
                ),
            }
        )

    # For cloze questions without a matched blank context, offer the nearest one.
    if cloze and questions:
        for idx, q in enumerate(questions):
            if not q["context"] and cloze_contexts:
                fallback = cloze_contexts[min(idx, len(cloze_contexts) - 1)]
                q["context"] = fallback["context"]
                if not q["evidence"]:
                    q["evidence"] = [{"sentence": fallback["context"], "paragraph": fallback["paragraph"], "matched": [], "score": 0.5}]

    vocabulary = _focus_vocabulary(all_context_text, sentences, cloze_contexts)
    phrases = _find_phrases(passage_text)
    keys = _key_sentences(sentences)
    stats_words = WORD_RE.findall(passage_text)
    stats = {
        "word_count": len(stats_words),
        "unique_words": len({w.lower() for w in stats_words}),
        "sentence_count": len(sentences),
        "paragraph_count": len(paragraphs),
        "question_count": len(questions),
        "vocabulary_count": len(vocabulary),
        "phrase_count": len(phrases),
        "key_sentence_count": len(keys),
        "reading_minutes": _difficulty(passage_text)["reading_minutes"],
        "difficulty": _difficulty(passage_text),
    }

    return {
        "kind": kind,
        "title": title,
        "detected_title": detected_title,
        "instructions": _dedupe(instructions),
        "paragraphs": [{"index": i + 1, "text": p} for i, p in enumerate(paragraphs)],
        "plain_passage": passage_text,
        "questions": questions,
        "vocabulary": vocabulary,
        "phrases": phrases,
        "key_sentences": keys,
        "stats": stats,
        "raw_text": raw,
    }


def _is_instruction_line(line: str) -> bool:
    lower = line.lower().lstrip()
    return lower.startswith(TEST_INSTRUCTION_PREFIXES) or lower.startswith("directions:")


def _dedupe(items: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            output.append(item.strip())
    return output

"""Original demo material bundled with the app."""
from __future__ import annotations

READING = {
    "id": "reading",
    "label": "阅读真题示例",
    "kind": "阅读",
    "title": "The Quiet Power of Reading Slowly",
    "subtitle": "说明文 · 4 题",
    "text": """The Quiet Power of Reading Slowly

In a world that rewards speed, reading slowly can feel almost rebellious. We skim headlines, scroll through captions, and measure our progress by the number of books we finish. Yet a growing number of researchers argue that the most valuable reading is not fast or efficient at all. It is deliberate, unhurried, and willing to linger.

Consider what happens when you read a difficult poem slowly. You notice how a single word echoes another, how a comma changes the rhythm, and how an image returns three lines later. These connections do not appear to the eye that races ahead. They emerge only when attention has time to settle. In this sense, slow reading is less about moving through a text than about allowing a text to move through you.

Slow reading also strengthens empathy. Studies of readers of literary fiction suggest that people who take time to imagine a character's inner life become better at recognizing emotions in others. When we rush, characters become labels; when we slow down, they become people. The same habit can shape how patiently we listen to a friend or a stranger.

This is not an argument against reading widely or quickly when the situation calls for it. A train timetable, after all, does not require contemplation. But if we reserve our full attention only for practical tasks, we may lose the ability to sit with complexity. The reward of slow reading is not simply more information. It is a richer relationship with language, with other people, and with our own thoughts.

1. What is the main idea of the passage?
A. Reading quickly is always less useful than reading slowly.
B. Slow reading helps us understand texts and people more deeply.
C. Researchers disagree about how many books people should read.
D. Literature should be read more often than practical texts.

2. The word "deliberate" in paragraph 1 is closest in meaning to ______.
A. unhurried and intentional
B. difficult and confusing
C. fast and automatic
D. private and secret

3. Why does the author mention "a train timetable" in paragraph 4?
A. To prove that practical reading is not important.
B. To give an example of a text that does not need slow reading.
C. To suggest that people should avoid reading timetables.
D. To show that all texts require the same attention.

4. What can be inferred from the passage?
A. People who read quickly cannot feel empathy.
B. Slow reading can influence how we treat other people.
C. Literary fiction is more valuable than news articles.
D. The author believes that speed is never useful.
""",
}

CLOZE = {
    "id": "cloze",
    "label": "完形填空示例",
    "kind": "完形",
    "title": "Why We Keep Old Photographs",
    "subtitle": "夹叙夹议 · 5 空",
    "text": """Why We Keep Old Photographs

Most of us have a box of old photographs somewhere in the house. We rarely open it, __1__ we would never throw it away. Why do these images matter so much?

A photograph captures more than a face. It holds a moment that would otherwise be __2__. Looking at an old picture, we do not simply remember what happened; we also remember how we felt. The image becomes a doorway __3__ the past.

Researchers say that recalling happy memories can improve our mood. __4__, photographs also help families pass stories from one generation to the next. A child who listens to these stories begins to understand where they come from.

In a digital age, we take thousands of pictures but print very few. Perhaps that is __5__ we should slow down and choose the images we truly want to keep.

1. A. and    B. but    C. so    D. or
2. A. forgotten    B. forget    C. forgetting    D. forgets
3. A. at    B. by    C. to    D. from
4. A. However    B. Therefore    C. Besides    D. Instead
5. A. what    B. which    C. why    D. where
""",
}

SAMPLES = [READING, CLOZE]


def sample_list() -> list[dict]:
    return [
        {
            "id": item["id"],
            "label": item["label"],
            "kind": item["kind"],
            "title": item["title"],
            "subtitle": item["subtitle"],
        }
        for item in SAMPLES
    ]


def get_sample(sample_id: str) -> dict | None:
    return next((item for item in SAMPLES if item["id"] == sample_id), None)

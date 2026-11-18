import json
import re

from .model import MODEL_CARD, MODEL_NAME, ROOT, get_detector, signal

KINDS = {
    "general": "General writing",
    "application": "Application answer",
    "cover-letter": "Cover letter",
    "recruiter": "Recruiter note",
}
PROFILE_PATH = ROOT / "voice-profile.json"
MAX_DRAFT_CHARS = 16000
MIN_WORDS = 50
SHORT_WORDS = 100
WORD = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*")
SENTENCE = re.compile(r"[^.!?\n]+(?:[.!?]+(?=\s|$)|(?=\n|$))")
FORMULAIC = re.compile(
    r"\b(?:I am writing to express (?:my )?interest|I firmly believe|"
    r"proven track record|uniquely positioned|seamlessly aligns?|"
    r"in today['’]s (?:rapidly|fast)[ -](?:evolving|paced)|"
    r"drive meaningful impact|dynamic team|results-driven professional|"
    r"passion for excellence|I would welcome the opportunity to|"
    r"in the ever[ -]evolving landscape of|a testament to the power of|"
    r"it is (?:worth noting|important to note) that)\b",
    re.IGNORECASE,
)
OWNERSHIP = re.compile(r"\b(?:I|my|me)\b", re.IGNORECASE)
NUMBER = re.compile(r"\b\d+(?:[.,]\d+)?(?:%|\b)")


def load_profile():
    try:
        return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def word_count(text):
    return len(WORD.findall(text))


def writing_feedback(text, kind, words):
    notes = []
    if kind != "general" and "\u2014" in text:
        notes.append(
            {
                "title": "Replace em dashes",
                "detail": "Use a period or comma where it reads naturally in your voice.",
            }
        )
    phrases = list(dict.fromkeys(match.group().lower() for match in FORMULAIC.finditer(text)))
    if phrases:
        quoted = ", ".join(f"“{phrase}”" for phrase in phrases[:4])
        notes.append(
            {
                "title": "Swap stock wording for specifics",
                "detail": f"Look at {quoted}. See where a clear claim, specific action, or example would say more.",
            }
        )
    for match in SENTENCE.finditer(text):
        sentence = match.group().strip()
        if word_count(sentence) >= 34:
            opening = " ".join(WORD.findall(sentence)[:7])
            notes.append(
                {
                    "title": "Break up a long sentence",
                    "detail": f"The sentence starting “{opening}…” has {word_count(sentence)} words. Try giving each main idea its own sentence.",
                }
            )
            break

    if kind == "recruiter":
        if not re.match(r"^\s*(?:hi|hey|hello|dear)\b", text, re.IGNORECASE):
            notes.append(
                {
                    "title": "Open the note like an email",
                    "detail": "A short first-name greeting fits how you usually reach out to recruiters.",
                }
            )
        if not re.search(r"\b(?:thanks|thank you|let me know|available|free to|talk soon)\b", text, re.I):
            notes.append(
                {
                    "title": "Give the reader a next step",
                    "detail": "Close with a quick thank-you or give them an easy way to respond.",
                }
            )
    elif kind in {"application", "cover-letter"} and words >= 35:
        if not OWNERSHIP.search(text):
            notes.append(
                {
                    "title": "Make your contribution clear",
                    "detail": "If the prompt is about experience, say what you personally did and what happened next.",
                }
            )
        if not NUMBER.search(text) and words >= 65:
            notes.append(
                {
                    "title": "Check for a concrete result",
                    "detail": "If the prompt calls for proof, add one real outcome you can discuss in an interview. Use a number if you know it.",
                }
            )

    return notes


def review_draft(draft, kind="general"):
    if not isinstance(draft, str) or not draft.strip():
        raise ValueError("Enter a draft to review.")
    if len(draft) > MAX_DRAFT_CHARS:
        raise ValueError(f"Enter no more than {MAX_DRAFT_CHARS:,} characters.")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("Unknown review type.")

    draft = draft.strip()
    words = word_count(draft)
    detection = {
        "model": MODEL_NAME, "model_card": MODEL_CARD, "score": None,
        "signal": None, "method": None, "passages": [], "note": "",
    }
    if words < MIN_WORDS:
        detection["note"] = f"AI screening starts at {MIN_WORDS} words. Shorter drafts still get writing feedback."
    else:
        score, method, passages = get_detector().evaluate(draft)
        detection.update(
            score=score,
            method=method,
            passages=passages,
            signal=signal(score) if score is not None else None,
        )
        if words < SHORT_WORDS:
            detection["note"] = "Use extra caution with estimates on drafts under 100 words."
        elif method == "weighted_passages":
            detection["note"] = "The overall score is weighted by the number of tokens in each passage."

    return {
        "kind": kind,
        "words": words,
        "characters": len(draft),
        "detector": detection,
        "voice_notes": writing_feedback(draft, kind, words),
    }

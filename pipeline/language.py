"""
Hindi, Marathi and Hinglish: read the question in code, search in English, answer in kind.

Many VNIT students would rather ask "hostel ki fees kitni hai?" or ask in
Devanagari. VNIT's documents are in English, and so is the search index (its
embedding model and keyword index were built on English text), so a question
searched as written finds little. Claude or ChatGPT would simply translate; a
translation call would cost a second LLM request per question on a free tier.
Instead:

- the language is detected in code: Devanagari script is Hindi or Marathi
  (told apart by a few very common words of each), and Latin-script Hindi
  ("Hinglish") by words like kitni, kya, hai, kab, kaise;
- the first search runs on English keywords made in code: a small glossary of
  the words students use for fees, hostels, exams and so on, plus whatever is
  already in Latin letters or digits (programme names, years, amounts);
- the agent is told the student's language, searches again in English if it
  needs to, and writes the answer in the student's language with every number,
  amount, date and email exactly as in the sources, so the verifier can still
  check them.
"""
import re

ENGLISH, HINDI, MARATHI, HINGLISH = "en", "hi", "mr", "hinglish"
NAMES = {HINDI: "Hindi", MARATHI: "Marathi", HINGLISH: "Hinglish (Hindi in Latin letters)"}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_MARATHI_WORDS = {"आहे", "आहेत", "काय", "किती", "कसे", "कसा", "कशी", "कधी", "मला", "आणि", "साठी",
                  "नाही", "कुठे", "सांगा", "पाहिजे", "मिळेल", "होते", "आम्ही", "तुम्ही", "किंवा"}
_HINDI_WORDS = {"है", "हैं", "क्या", "कितनी", "कितना", "कितने", "कैसे", "कब", "मुझे", "और", "के",
                "की", "का", "नहीं", "लिए", "कहाँ", "कहां", "बताइए", "बताओ", "चाहिए", "होगा",
                "मिलेगा", "मिलेगी", "होती", "होता", "हम", "आप"}
_HINGLISH_STRONG = {"kitni", "kitna", "kitne", "kya", "hai", "hain", "kab", "kaise", "kaisa",
                    "kahan", "kaha", "mujhe", "batao", "bataiye", "chahiye", "milega", "milegi",
                    "nahi", "liye", "lagegi", "lagega", "padegi", "hota", "hoti", "karna", "karne",
                    "hoga", "hogi", "hoge", "shuru", "kaun", "kidhar", "milta", "milti", "dena"}
_HINGLISH_WEAK = {"ka", "ki", "ke", "ko", "aur", "mein", "se", "kar", "wala", "wali", "bhi", "toh"}

_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z.&/-]*|\d[\d,./-]*")
_WORD = re.compile(r"[ऀ-ॿ]+|[A-Za-z]+")


def detect(text: str) -> str:
    """ENGLISH, HINDI, MARATHI or HINGLISH, in code."""
    text = text or ""
    if _DEVANAGARI.search(text):
        words = set(_WORD.findall(text))
        marathi = len(words & _MARATHI_WORDS)
        hindi = len(words & _HINDI_WORDS)
        return MARATHI if marathi > hindi else HINDI
    words = [w.lower() for w in _WORD.findall(text)]
    strong = sum(1 for w in words if w in _HINGLISH_STRONG)
    weak = sum(1 for w in words if w in _HINGLISH_WEAK)
    return HINGLISH if strong >= 1 and strong + weak >= 2 else ENGLISH


# Words students use, in Devanagari, and the English a VNIT document uses.
# Longer phrases first, so "शिक्षण शुल्क" becomes "tuition fee", not "fee".
_GLOSSARY = [
    ("शिक्षण शुल्क", "tuition fee"), ("ट्यूशन फीस", "tuition fee"), ("ट्यूशन", "tuition"),
    ("अंतिम तिथि", "last date"), ("अंतिम तारीख", "last date"), ("शेवटची तारीख", "last date"),
    ("आखिरी तारीख", "last date"), ("पहले वर्ष", "first year"), ("प्रथम वर्ष", "first year"),
    ("पहिल्या वर्षाच्या", "first year"), ("पहिल्या वर्षा", "first year"), ("पहला साल", "first year"),
    ("शैक्षणिक कैलेंडर", "academic calendar"), ("शैक्षणिक दिनदर्शिका", "academic calendar"),
    ("फीस", "fee"), ("फ़ीस", "fee"), ("शुल्क", "fee"), ("फी", "fee"),
    ("छात्रावास", "hostel"), ("हॉस्टल", "hostel"), ("होस्टल", "hostel"), ("वसतिगृह", "hostel"),
    ("मेस", "mess"), ("परीक्षा", "exam"), ("छात्रवृत्ति", "scholarship"), ("शिष्यवृत्ती", "scholarship"),
    ("स्कॉलरशिप", "scholarship"), ("प्रवेश", "admission"), ("प्लेसमेंट", "placement"),
    ("पैकेज", "package"), ("कंपनियाँ", "companies"), ("कंपनियां", "companies"), ("कंपन्या", "companies"),
    ("कंपनी", "company"), ("बी.टेक", "B.Tech"), ("बी. टेक", "B.Tech"), ("बीटेक", "B.Tech"),
    ("एम.टेक", "M.Tech"), ("एम. टेक", "M.Tech"), ("एमटेक", "M.Tech"), ("बी.आर्क", "B.Arch"),
    ("बीआर्क", "B.Arch"), ("पीएचडी", "PhD"), ("एमबीए", "MBA"), ("एम.एससी", "M.Sc"), ("एमएससी", "M.Sc"),
    ("लड़कियों", "girls"), ("लड़कियां", "girls"), ("लड़कियाँ", "girls"), ("मुलींच्या", "girls"),
    ("मुलींसाठी", "girls"), ("मुली", "girls"), ("लड़कों", "boys"), ("लड़के", "boys"),
    ("मुलांच्या", "boys"), ("मुलांसाठी", "boys"), ("तारीख", "date"), ("तिथि", "date"),
    ("कब", "when"), ("कधी", "when"), ("छुट्टी", "holiday"), ("सुट्टी", "holiday"), ("अवकाश", "holiday"),
    ("होली", "Holi"), ("होळी", "Holi"), ("दिवाली", "Diwali"), ("दिवाळी", "Diwali"),
    ("निदेशक", "Director"), ("संचालक", "Director"), ("कुलसचिव", "Registrar"), ("रजिस्ट्रार", "Registrar"),
    ("डीन", "Dean"), ("अधिष्ठाता", "Dean"), ("विभाग", "department"), ("सीटें", "seats"),
    ("जागा", "seats"), ("ईमेल", "email"), ("फोन", "phone"), ("नियम", "rules"),
    ("उपस्थिति", "attendance"), ("उपस्थिती", "attendance"), ("कैलेंडर", "calendar"),
    ("सेमेस्टर", "semester"), ("सत्र", "semester"), ("भुगतान", "payment"), ("भरणा", "payment"),
    ("कैसे", "how to"), ("कसे", "how to"), ("कितनी", "how much"), ("किती", "how much"),
    ("कितने", "how many"), ("कौन", "who"), ("कोण", "who"),
]


def english_keywords(text: str, lang: str) -> str:
    """The question as English search words, made in code (no LLM call).

    Hinglish keeps its English words and drops the Hindi function words; Hindi
    and Marathi keep anything in Latin letters or digits and translate the
    glossary's words. If nothing is left, the question is searched as written.
    """
    if lang == HINGLISH:
        words = [w for w in re.findall(r"[\w.&/-]+", text)
                 if w.lower() not in _HINGLISH_STRONG | _HINGLISH_WEAK]
        return " ".join(words).strip() or text
    if lang not in (HINDI, MARATHI):
        return text
    found, rest = [], text
    for word, english in _GLOSSARY:
        if word in rest:
            found.append((rest.index(word), english))
            rest = rest.replace(word, " ")
    found += [(rest.index(m), m) for m in _LATIN_WORD.findall(rest)]
    words = [w for _pos, w in sorted(found)]
    deduped = list(dict.fromkeys(words))
    return " ".join(deduped).strip() or text


def instruction(lang: str) -> str:
    """The planner's line for a question not in English ("" for English)."""
    if lang == ENGLISH:
        return ""
    script = "in Latin letters, as they wrote" if lang == HINGLISH else "in Devanagari script"
    return (f"The student wrote in {NAMES[lang]}. VNIT's documents and your search tools are in "
            "English, so search with English keywords. Write the answer in "
            f"{NAMES[lang].split(' (')[0]} {script}, but keep every number, fee amount, date, "
            "email address, phone number and document title exactly as in the passages, with "
            "ordinary digits 0-9.")


_GREETING = re.compile(r"^\s*(नमस्ते|नमस्कार|प्रणाम|राम राम)[\s!।.,?]*$")
_THANKS = re.compile(r"^\s*(धन्यवाद|शुक्रिया|आभार|थँक्स|थैंक्स|bahut dhanyavaad|dhanyavaad|shukriya)[\s!।.,?]*$",
                     re.I)


def chat_kind(text: str):
    """"greeting" or "thanks" for a short Hindi/Marathi message of that kind, else None."""
    if _GREETING.match(text or ""):
        return "greeting"
    if _THANKS.match(text or ""):
        return "thanks"
    return None


REPLIES = {
    (HINDI, "greeting"): (
        "नमस्ते! मैं VNIT नागपुर का सहायक हूँ। प्रवेश, फीस, हॉस्टल, छात्रवृत्ति, परीक्षा, प्लेसमेंट या "
        "विभागों के बारे में पूछिए। मैं VNIT की अपनी वेबसाइट और दस्तावेज़ों से, स्रोत के लिंक के साथ, "
        "उत्तर देता हूँ।"),
    (MARATHI, "greeting"): (
        "नमस्कार! मी VNIT नागपूरचा सहाय्यक आहे. प्रवेश, शुल्क, वसतिगृह, शिष्यवृत्ती, परीक्षा, प्लेसमेंट "
        "किंवा विभागांबद्दल विचारा. मी VNIT च्या स्वतःच्या वेबसाइट आणि कागदपत्रांमधून, स्रोताच्या "
        "लिंकसह उत्तर देतो."),
    (HINGLISH, "greeting"): (
        "Namaste! Main VNIT Nagpur ka assistant hoon. Admission, fees, hostel, scholarship, exams, "
        "placements ya departments ke baare mein poochiye. Main VNIT ki apni website aur documents "
        "se, source ke link ke saath, jawab deta hoon."),
    (HINDI, "thanks"): "आपका स्वागत है। VNIT के बारे में कुछ और पूछना हो तो कभी भी पूछिए।",
    (MARATHI, "thanks"): "आपले स्वागत आहे. VNIT बद्दल आणखी काही विचारायचे असल्यास कधीही विचारा.",
    (HINGLISH, "thanks"): "Aapka swagat hai. VNIT ke baare mein kuch aur poochna ho toh kabhi bhi poochiye.",
}

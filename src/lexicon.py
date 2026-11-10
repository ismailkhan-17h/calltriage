from rapidfuzz import fuzz

NUKTA = "\u093c"

# (term, violation_type). Extend with your own variants.
LEXICON = [
    # Hinglish (Roman)
    ("ghar aa jaunga", "threat"), ("ghar aa jayenge", "threat"),
    ("dekh lena", "threat"), ("dekh lunga", "threat"), ("dekh lenge", "threat"),
    ("police ko bata", "threat"), ("jail", "threat"), ("badnaam", "threat"),
    ("family ko bata", "family_disclosure"), ("ghar walon ko bata", "family_disclosure"),
    ("office mein bata", "family_disclosure"), ("padosi", "family_disclosure"),
    ("bewakoof", "abuse"), ("harami", "abuse"), ("kamina", "abuse"),
    ("interest maaf", "false_promise"), ("guarantee", "false_promise"),
    ("no interest", "false_promise"),
    # Hindi (Devanagari)
    ("घर आ जाऊंगा", "threat"), ("घर आ जाऊँगा", "threat"), ("घर आ जाउंगा", "threat"),
    ("देख लेना", "threat"), ("देख लूंगा", "threat"), ("वरना देख", "threat"),
    ("पुलिस", "threat"), ("जेल", "threat"), ("बदनाम", "threat"),
    ("फैमिली को बता", "family_disclosure"), ("फैमिली को सब बता", "family_disclosure"),
    ("परिवार को बता", "family_disclosure"), ("परिवार को सब बता", "family_disclosure"),
    ("घर वालों को बता", "family_disclosure"),
    ("बेवकूफ", "abuse"), ("कमीना", "abuse"), ("हरामी", "abuse"),
    ("इंटरेस्ट माफ", "false_promise"), ("ब्याज माफ", "false_promise"),
    ("गारंटी", "false_promise"),
        # More Hindi threats
    ("जान से", "threat"), ("मार दूंगा", "threat"), ("मार दूँगा", "threat"),
    ("तोड़ दूंगा", "threat"), ("छोड़ूंगा नहीं", "threat"), ("छोडूंगा नहीं", "threat"),
    ("उठवा लूंगा", "threat"), ("mar dunga", "threat"), ("chhodunga nahi", "threat"),
    # Kannada (starter, please verify against your real transcript)
    ("ಕೊಲ್ಲ", "threat"), ("ಹೊಡೆಯ", "threat"), ("ಬಿಡಲ್ಲ", "threat"),
    ("ಮನೆಗೆ ಬರ", "threat"), ("ಪೊಲೀಸ್", "threat"), ("ಜೈಲು", "threat"),
    ("ಕುಟುಂಬಕ್ಕೆ ಹೇಳ", "family_disclosure"), ("ಮನೆಯವರಿಗೆ ಹೇಳ", "family_disclosure"),
    # Tanglish / Tamil
    ("veetuku varuven", "threat"), ("paathukren", "threat"), ("paathukkaren", "threat"),
    ("family ku solven", "family_disclosure"), ("veetla solven", "family_disclosure"),
    ("வீட்டுக்கு வருவேன்", "threat"), ("பார்த்துக்கறேன்", "threat"),
    ("வட்டி தள்ளுபடி", "false_promise"),

]


def _norm(s):
    return s.lower().replace(NUKTA, "")


def scan_segments(segments, threshold=88):
    """Rule-based hits: [{type, seg, quote, reason}]"""
    hits, seen = [], set()
    for i, seg in enumerate(segments):
        text = _norm(seg["text"])
        for term, vtype in LEXICON:
            t = _norm(term)
            if t in text:
                matched = True
            elif len(t) >= 8:
                matched = fuzz.partial_ratio(t, text) >= threshold
            else:
                matched = False
            if matched and (vtype, i) not in seen:
                seen.add((vtype, i))
                hits.append({"type": vtype, "seg": i, "quote": seg["text"],
                             "reason": f"lexicon match: '{term}'"})
    return hits
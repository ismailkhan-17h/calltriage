import json
import ollama
from src.lexicon import scan_segments

MODEL = "qwen2.5:3b"
WEIGHTS = {"threat": 35, "family_disclosure": 25, "abuse": 25,
           "false_promise": 20, "pressure": 10}

PROMPT = """You audit debt-collection phone calls (Hindi/Tamil/English mixed).
The transcript is split into numbered segments. Speakers are not labelled; infer them.
Return ONLY JSON in this shape:
{"violations":[{"type":"threat|abuse|false_promise|family_disclosure|pressure","seg":0,"quote":"words from that segment","reason":"short"}],
"promises":[{"speaker":"agent|borrower","commitment":"short","seg":0}],
"sentiment":"positive|neutral|negative",
"summary":"one sentence"}
Rules: flag only what is really in the text. If nothing, use empty lists.
Threat = visiting home, harm, police/legal intimidation. family_disclosure = telling family, neighbours or employer about the debt.
false_promise = agent promising an unrealistic waiver or guarantee.

TRANSCRIPT:
"""


def llm_analyze(segments):
    text = "\n".join(f"[{i}] {s['text']}" for i, s in enumerate(segments))
    try:
        resp = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": PROMPT + text}],
            format="json",
            options={"temperature": 0},
        )
        return json.loads(resp["message"]["content"])
    except Exception as e:
        print("LLM failed:", e)
        return {
            "violations": [],
            "promises": [],
            "sentiment": "neutral",
            "summary": f"LLM unavailable: {str(e)[:100]}",
        }


def analyze_call(name, segments):
    n = len(segments)
    llm = llm_analyze(segments)
    merged = {}

    for v in scan_segments(segments):
        merged[(v["type"], v["seg"])] = {**v, "source": "rule"}

    for v in llm.get("violations", []):
        t, s = v.get("type"), v.get("seg")
        if t not in WEIGHTS or not isinstance(s, int) or not 0 <= s < n:
            continue
        key = (t, s)
        if key in merged:
            merged[key]["source"] = "rule+llm"
        else:
            merged[key] = {"type": t, "seg": s,
                           "quote": v.get("quote", segments[s]["text"]),
                           "reason": v.get("reason", ""), "source": "llm"}

    violations = []
    for v in merged.values():
        seg = segments[v["seg"]]
        violations.append({**v, "start_s": seg["start_s"], "audio": seg["audio"]})
    violations.sort(key=lambda x: x["start_s"])

    score = 0.0
    for t, w in WEIGHTS.items():
        c = sum(1 for v in violations if v["type"] == t)
        if c:
            score += w * min(1.5, 1 + 0.25 * (c - 1))
    if llm.get("sentiment") == "negative":
        score += 10

    return {
        "call": name,
        "risk_score": int(min(100, round(score))),
        "sentiment": llm.get("sentiment", "neutral"),
        "summary": llm.get("summary", ""),
        "promises": [p for p in llm.get("promises", [])
                     if isinstance(p.get("seg"), int) and 0 <= p["seg"] < n],
        "violations": violations,
        "segments": segments,
    }
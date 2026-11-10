import glob, json, os
import jiwer
import pandas as pd
from src.transcribe import transcribe_call
from src.analyze import analyze_call

os.makedirs("data/transcripts_noisy", exist_ok=True)


def join(segs):
    return " ".join(s["text"] for s in segs)


def types(res):
    return {v["type"] for v in res["violations"]}


rows = []
for clean_path in sorted(glob.glob("data/results/*.json")):
    clean = json.load(open(clean_path, encoding="utf-8"))
    name = clean["call"]
    ref_text, ref_types = join(clean["segments"]), types(clean)
    rows.append({"call": name, "condition": "clean", "WER_vs_clean": 0.0,
                 "flags_found": ", ".join(sorted(ref_types)) or "-",
                 "flag_recall": 1.0, "risk": clean["risk_score"]})

    for noisy in sorted(glob.glob(f"data/noisy/{name}__snr*.wav")):
        tag = os.path.splitext(os.path.basename(noisy))[0].split("__")[1]
        tpath = f"data/transcripts_noisy/{name}__{tag}.json"
        if os.path.exists(tpath):
            segs = json.load(open(tpath, encoding="utf-8"))
        else:
            segs = transcribe_call(noisy, language_code="hi-IN")
            json.dump(segs, open(tpath, "w", encoding="utf-8"), ensure_ascii=False)
        if segs:
            res = analyze_call(name, segs)
            wer = round(min(1.0, jiwer.wer(ref_text, join(segs))), 2)
            found, risk = types(res), res["risk_score"]
        else:
            wer, found, risk = 1.0, set(), 0
        recall = round(len(found & ref_types) / len(ref_types), 2) if ref_types else 1.0
        rows.append({"call": name, "condition": tag, "WER_vs_clean": wer,
                     "flags_found": ", ".join(sorted(found)) or "-",
                     "flag_recall": recall, "risk": risk})

df = pd.DataFrame(rows)
df.to_csv("data/benchmark.csv", index=False)
print(df.to_string(index=False))
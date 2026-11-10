import os, glob, json
from src.transcribe import transcribe_call
from src.analyze import analyze_call

os.makedirs("data/results", exist_ok=True)
os.makedirs("data/transcripts", exist_ok=True)

for f in sorted(glob.glob("data/raw/*.*")):
    name = os.path.splitext(os.path.basename(f))[0]
    tpath = f"data/transcripts/{name}.json"
    if os.path.exists(tpath):
        segments = json.load(open(tpath, encoding="utf-8"))
    else:
        segments = transcribe_call(f, language_code="hi-IN")
        json.dump(segments, open(tpath, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    if not segments:
        print("No speech found in", name)
        continue
    result = analyze_call(name, segments)
    json.dump(result, open(f"data/results/{name}.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"{name}: risk={result['risk_score']} violations={len(result['violations'])}")
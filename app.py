import glob, json
import pandas as pd
import streamlit as st

st.set_page_config(page_title="CallTriage", layout="wide")
st.title("CallTriage: Risk-Ranked Call Audit")
st.caption("Synthetic calls only. Speakers inferred by AI. Human review required for every flag.")

import os
from src.transcribe import transcribe_call
from src.analyze import analyze_call

with st.sidebar:
    st.header("Audit a new call")
    up = st.file_uploader("Upload a recording", type=["wav", "mp3", "mp4", "m4a"])
    lang = st.selectbox("Language", ["indic-auto", "hi-IN", "kn-IN", "ta-IN", "te-IN",
                                 "ml-IN", "en-IN", "bn-IN", "mr-IN", "gu-IN", "pa-IN"])
    if up and st.button("Run audit"):
        safe = up.name.replace(" ", "_")
        name = os.path.splitext(safe)[0]
        os.makedirs("data/uploads", exist_ok=True)
        path = os.path.join("data/uploads", safe)
        with open(path, "wb") as f:
            f.write(up.getbuffer())
        try:
            with st.spinner("Transcribing and analyzing (about 1 minute)..."):
                segs = transcribe_call(path, language_code=lang)
                if not segs:
                    st.error("No speech found, or the API failed. Try again.")
                else:
                    res = analyze_call(name, segs)
                    os.makedirs("data/results", exist_ok=True)
                    with open(f"data/results/{name}.json", "w", encoding="utf-8") as f:
                        json.dump(res, f, ensure_ascii=False, indent=2)
                    st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

results = [json.load(open(p, encoding="utf-8")) for p in glob.glob("data/results/*.json")]
if not results:
    st.warning("No results yet. Run: python process_all.py")
    st.stop()
results.sort(key=lambda r: r["risk_score"], reverse=True)

st.subheader("Review queue (highest risk first)")
st.dataframe(pd.DataFrame([{
    "Call": r["call"], "Risk": r["risk_score"], "Flags": len(r["violations"]),
    "Promises": len(r["promises"]), "Sentiment": r["sentiment"], "Summary": r["summary"],
} for r in results]), use_container_width=True, hide_index=True)

pick = st.selectbox("Open a call", [r["call"] for r in results])
r = next(x for x in results if x["call"] == pick)

if r["summary"].startswith("LLM unavailable"):
    st.warning("The LLM did not run for this call, so only keyword rules were applied. A risk of 0 does not mean the call is safe.")

c1, c2, c3 = st.columns(3)
c1.metric("Risk score", r["risk_score"])
c2.metric("Flags", len(r["violations"]))
c3.metric("Sentiment", r["sentiment"])

st.subheader("Evidence")
if not r["violations"]:
    st.success("No violations flagged.")
for v in r["violations"]:
    m, s = divmod(int(v["start_s"]), 60)
    st.error(f"**{v['type'].upper()}** at {m:02d}:{s:02d} [{v['source']}]  \n> {v['quote']}  \n{v['reason']}")
    st.audio(v["audio"])

st.subheader("Promises")
for p in r["promises"]:
    st.info(f"**{p['speaker']}**: {p['commitment']} (segment {p['seg']})")

st.subheader("Full transcript")
flagged = {v["seg"] for v in r["violations"]}
for i, s in enumerate(r["segments"]):
    m, sec = divmod(int(s["start_s"]), 60)
    line = f"`{m:02d}:{sec:02d}` {s['text']}"
    st.markdown(f":red[{line}]" if i in flagged else line)

try:
    bench = pd.read_csv("data/benchmark.csv")
    st.subheader("Noise robustness benchmark (8kHz + traffic noise)")
    st.dataframe(bench, use_container_width=True, hide_index=True)
except FileNotFoundError:
    pass
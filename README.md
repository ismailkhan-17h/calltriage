# CallTriage

**Evidence-linked risk ranking for noisy, code-mixed Indian collection calls.**

CallTriage ingests phone-call recordings, transcribes them with Gnani.ai Prisma, and combines a rule-based lexicon with a local LLM to produce a 0-100 risk score with timestamped, quote-linked evidence. A QA manager reviews the few calls that matter first instead of sampling at random.

> **Data notice:** All calls used in this project are synthetic, scripted and recorded by the author. No real borrower data is used.

---

## Problem

Micro-credit, banking and collections teams in India handle thousands of calls a day over 8 kHz cellular lines with background noise and Hindi/Tamil/Kannada-English code-switching. Human QA teams can review only a small fraction of them, so threats, false promises and disclosure of debt to third parties are usually discovered only after a borrower complains.

The real bottleneck is not transcription. It is **deciding which calls a human must listen to**. Transcription is only an input to that decision.

## Solution

CallTriage turns every call into a ranked, auditable record.

1. **Segment** the audio into short speech segments (≤10 s) using silence detection. Each segment's start time becomes the evidence timestamp, because the transcription API returns a flat string without timestamps.
2. **Transcribe** each segment with Gnani.ai Prisma (`/stt/v3`), with retry and backoff on gateway errors.
3. **Detect (hybrid):**
   - *Rules layer:* a curated lexicon of threat, abuse, family-disclosure and false-promise phrases in Roman and native scripts, with fuzzy matching for spelling variants.
   - *LLM layer:* a local model (Qwen2.5 via Ollama) returns structured JSON with violations, promises, sentiment and a one-line summary.
4. **Score** each call with weighted violation types, repeat-offence escalation and a sentiment adjustment.
5. **Review** in a Streamlit dashboard: ranked queue, per-call evidence with click-to-play audio, promise log, and full transcript with flagged segments highlighted.

```
Audio (.wav/.mp3/.mp4/.m4a)
        │
        ▼
  Silence-based segmentation (pydub)          → start/end timestamps per segment
        │
        ▼
  Gnani.ai Prisma STT (per segment, w/ retry) → transcript text
        │
        ├──► Lexicon rules (rapidfuzz, nukta-normalised) ─┐
        │                                                 ├─► Merge → Risk score
        └──► Local LLM (Ollama, JSON-constrained) ────────┘
                                                          │
                                                          ▼
                                       Streamlit dashboard (ranked queue + evidence)
```

## Why hybrid detection

| Layer | Strength | Weakness |
|---|---|---|
| Lexicon rules | Precise, deterministic, explainable to a compliance officer | Misses paraphrase and unseen vocabulary |
| LLM | Catches context-dependent intimidation, promises and sentiment | Can hallucinate; weaker on low-resource languages |

Each covers the other's failure mode. Every flag is tagged with its source (`rule`, `llm` or `rule+llm`) so reviewers can see why it was raised.

## Features

- Risk-ranked review queue (highest risk first)
- Timestamped evidence with the exact quote and playable audio for each flag
- Promise extraction with inferred speaker (agent or borrower)
- Live upload of a new recording from the sidebar, with language selection
- Visible warning when the LLM did not run, so a risk of 0 is never mistaken for "safe"
- Noise-robustness benchmark (8 kHz downsampling plus traffic noise at several SNRs)
- Transcript caching to avoid repeated API calls

## Noise robustness benchmark

To test how the pipeline degrades on telephony-quality audio, each clean recording is downsampled to 8 kHz and mixed with traffic noise at 20 dB, 10 dB and 5 dB SNR. The clean-audio transcript and flags are used as the reference.

| Call | Condition | WER vs. clean | Flags found | Flag recall | Risk |
|---|---|---|---|---|---|
| _fill from `data/benchmark.csv`_ | | | | | |

**Observation:** key compliance phrases (for example the Hindi phrases for "interest waived" and "guarantee") were still transcribed correctly at 5 dB SNR in the false-promise call.

> **Methodology caveat:** there are no human-labelled transcripts, so WER is measured against the clean-audio ASR output, not a ground-truth transcript. It measures *degradation*, not absolute accuracy. The sample is small (3 calls × 3 noise levels) and should be read as a feasibility signal, not a statistically robust result.

## Getting started

### Prerequisites

- Python 3.10 or 3.11
- [ffmpeg](https://ffmpeg.org/) on your PATH
- [Ollama](https://ollama.com/) with a pulled model
- A Gnani.ai Prisma API key

### Installation

```bash
git clone https://github.com/<your-username>/calltriage.git
cd calltriage
python -m venv venv
# Windows: venv\Scripts\activate    |    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:3b
```

### Configuration

Create a `.env` file in the project root (never commit it):

```
PRISMA_API_URL=https://api.vachana.ai/stt/v3
PRISMA_API_KEY=<your key>
PRISMA_KEY_HEADER=X-API-Key
```

Confirm the endpoint and header name against your Prisma documentation.

### Run

```bash
# 1. Put recordings in data/raw/ and noise clips in data/noise/
python process_all.py          # transcribe + analyse all calls
streamlit run app.py           # open the dashboard

# 2. Optional: robustness benchmark
python -m src.degrade          # create 8 kHz noisy copies
python -m src.benchmark        # writes data/benchmark.csv
```

Run the `src.*` modules with `python -m` from the project root.

## Project structure

```
calltriage/
├── app.py              # Streamlit dashboard + upload
├── process_all.py      # batch pipeline with transcript caching
├── src/
│   ├── transcribe.py   # segmentation + Prisma API client (retry/backoff)
│   ├── lexicon.py      # rule layer (multi-script, fuzzy match)
│   ├── analyze.py      # LLM analysis, merging, risk scoring
│   ├── degrade.py      # 8 kHz + noise augmentation
│   └── benchmark.py    # clean vs. noisy comparison
└── data/               # raw, noise, noisy, transcripts, results (git-ignored)
```

## Risk scoring

| Violation type | Weight |
|---|---|
| Threat | 35 |
| Family / third-party disclosure | 25 |
| Abuse | 25 |
| False promise | 20 |
| Pressure | 10 |

Repeated violations of the same type add 25% each (capped at 1.5×). Negative overall sentiment adds 10 points. The score is capped at 100. The weights are heuristic and intended to be tuned with a compliance team.

## Known limitations

Stating these plainly matters more than hiding them.

- **No speaker diarization.** The API returns a flat transcript, so one segment can contain both speakers. Agent and borrower roles are inferred by the LLM and labelled as inferred.
- **Timestamps are segment-level**, not word-level, because they derive from silence-based segmentation.
- **ASR hallucination on non-speech audio.** Pure traffic noise produced short spurious transcripts ("hello", "baat mein"). A voice-activity or confidence filter is needed in production.
- **Language coverage is uneven.** The lexicon is strongest for Hindi/Hinglish. Tamil and Kannada terms are starter lists and have not been validated against real transcripts.
- **A 3B-parameter local LLM is limited** in nuance and reliability on code-mixed text. It was chosen for 8 GB RAM and offline operation.
- **Small, synthetic evaluation set.** Results demonstrate feasibility, not production accuracy.
- **Third-party API dependency.** The Prisma gateway returned intermittent 504 errors during testing; retry with backoff mitigates this but does not eliminate it.
- **False positives are expected.** A flag is a prompt for human review, not a finding of misconduct.

## Responsible use

- CallTriage is a **triage aid**, not an automated disciplinary system. A human reviews every flag before any action.
- Production use requires lawful call recording, consent and notice, and compliance with applicable Indian data-protection and Reserve Bank of India recovery-agent rules. This repository does not provide legal advice.
- Do not commit real call recordings or API keys. `data/` and `.env` are git-ignored.

## Roadmap

- Speaker diarization and per-speaker risk attribution
- Confidence- and VAD-based filtering of non-speech segments
- Labelled evaluation set with precision/recall per violation type
- Agent-level scorecards and trend reporting
- Mandatory-disclosure and calling-hours compliance checks
- Larger LLM or fine-tuned classifier for code-mixed intent

## Tech stack

Python · Streamlit · Gnani.ai Prisma · Ollama (Qwen2.5) · pydub / ffmpeg · rapidfuzz · jiwer · pandas

## Acknowledgements

- Speech-to-text by [Gnani.ai](https://www.gnani.ai/) Prisma
- Traffic-noise audio from Freesound 

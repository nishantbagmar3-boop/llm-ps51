# Medical Report Explainer

**AI-powered blood test report analysis — GenAI (LLM) Mini Project, Problem Statement 51**

Upload a blood test report (PDF or TXT) or paste its text. The application:

1. Extracts the report text locally (PyMuPDF for PDFs).
2. Uses **Google Gemini 2.5 Flash** to copy every test name, measured value, unit
   and reference range into **structured JSON** (validated with **Pydantic**).
3. Classifies every value as **LOW / NORMAL / HIGH** with **deterministic Python
   code** — the LLM never decides the status.
4. Uses Gemini again to explain each result in **simple, patient-friendly English**
   (no diagnoses, no treatment advice — the Python-calculated status is final).
5. Shows a colour-coded results table, summary charts, explanation cards, and
   offers **PDF / JSON / CSV downloads**.

> **DISCLAIMER:** This application is designed for educational and informational
> purposes only. It does not provide medical diagnoses, treatment
> recommendations, or professional medical advice. Blood test results must be
> interpreted by a qualified healthcare professional considering your medical
> history, symptoms, age, and other relevant factors. Please consult your doctor
> for proper interpretation of your results.

---

## Features

- **PDF, TXT and pasted-text input** with file-type and size validation (10 MB limit).
- **Page-aware PDF extraction**; scanned/image-only PDFs are detected and a clear
  "OCR required" message is shown instead of wrong output.
- **Strict extraction rules** — the LLM copies only what is printed: no invented
  values, no invented reference ranges, `null` for missing data, original text preserved.
- **Pydantic validation** of the LLM JSON, with one limited LLM "repair" attempt
  for malformed output, then a clear error.
- **Deterministic range checking** in `analysis/range_checker.py`:
  - `value < minimum → LOW`, `value > maximum → HIGH`, otherwise `NORMAL`
    (boundary values count as NORMAL);
  - open-ended ranges (`< 200`, `> 60`) supported;
  - qualitative results (e.g. *Negative*) and missing ranges → **NOT EVALUATED**;
  - multiple age/sex-specific intervals or unit mismatches →
    **REFERENCE RANGE NEEDS REVIEW** (the app never infers patient demographics
    and never substitutes internet reference ranges).
- **Status colours:** HIGH red · LOW orange · NORMAL green · NOT EVALUATED grey ·
  NEEDS REVIEW yellow.
- **Medical disclaimer** on the home page, below the results and inside every download.
- Reports are processed **in memory only** — nothing is stored on disk.

## Technology stack

| Purpose | Tool |
|---|---|
| Language | Python 3.11 |
| UI | Streamlit |
| LLM | Google Gemini 2.5 Flash (google-genai SDK) |
| PDF extraction | PyMuPDF |
| JSON validation | Pydantic |
| Data handling | Pandas |
| Charts | Plotly |
| Config | python-dotenv |
| PDF export | ReportLab |
| Tests | pytest |

## Project structure

```
medical-report-explainer/
├── app.py                  # Streamlit UI
├── pipeline.py             # end-to-end pipeline (shared by app and tests)
├── config.py               # settings, limits, disclaimer, .env loading
├── requirements.txt
├── .env.example            # template for your own .env
├── extraction/
│   ├── pdf_extractor.py    # PyMuPDF page-by-page extraction + scanned detection
│   ├── text_extractor.py   # TXT decoding and text cleanup
│   ├── models.py           # Pydantic schema for the LLM JSON
│   └── json_parser.py      # parse + validate + one repair attempt
├── ai/
│   ├── gemini_client.py    # google-genai wrapper (temperature 0, JSON mode)
│   ├── extraction_prompt.py
│   └── explanation_prompt.py
├── analysis/
│   ├── range_checker.py    # deterministic LOW/NORMAL/HIGH logic (no LLM)
│   └── report_analyzer.py  # dataframes, summaries, export payloads
├── reporting/
│   ├── pdf_report.py       # downloadable PDF summary (ReportLab)
│   └── export_results.py   # JSON / CSV exports
├── utils/
│   ├── validators.py       # upload and text validation
│   └── helpers.py          # status colours, badges, formatting
├── sample_reports/         # synthetic sample inputs (NOT real patients)
├── scripts/
│   ├── make_sample_pdfs.py # builds sample_report.pdf + scanned_report.pdf
│   └── run_samples.py      # live end-to-end runs of the 5 required samples
├── tests/                  # pytest unit tests (no network needed)
├── docs/TEST_RESULTS.md    # genuine output of scripts/run_samples.py
└── screenshots/            # screenshots of the running application
```

## Setup

Requires Python 3.11+ and a (free) Gemini API key.

```bash
# 1. Clone and enter the project
git clone https://github.com/USERNAME/REPOSITORY.git
cd medical-report-explainer

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
copy .env.example .env         # Windows (cp on macOS/Linux)
# then edit .env and set:
#   GEMINI_API_KEY=your_real_key   (from https://aistudio.google.com/apikey)
#   GEMINI_MODEL=gemini-2.5-flash
```

**Never commit the `.env` file** — it is already listed in `.gitignore`.
If the key is missing, the app shows a step-by-step setup message instead of failing.

## Run the application

```bash
streamlit run app.py
```

Open http://localhost:8501, go to **Analyze Report**, upload a file from
`sample_reports/` (or paste text), and press **Analyze Report**.

## Testing

```bash
# Unit tests (no network, no API key needed)
python -m pytest tests -v

# Generate the sample PDFs (text-based + simulated scanned PDF)
python scripts/make_sample_pdfs.py

# Live end-to-end runs of the five required sample inputs (needs API key);
# writes genuine results to docs/TEST_RESULTS.md
python scripts/run_samples.py
```

The five required sample inputs (all synthetic — no real patient data):

| File | Scenario | Expected status |
|---|---|---|
| `test1_hemoglobin_low.txt` | Hemoglobin below its range | LOW |
| `test2_glucose_normal.txt` | Glucose inside its range | NORMAL |
| `test3_wbc_high.txt` | WBC above its range | HIGH |
| `test4_mixed_results.txt` | Multiple tests, mixed results | LOW/HIGH/NORMAL mix |
| `test5_missing_range.txt` | Vitamin D with no printed range | NOT EVALUATED |

Error paths covered: invalid PDF upload, empty text input, malformed LLM JSON,
missing API key, scanned PDF without extractable text.

## GitHub submission

Repository naming convention: `llm-ps51-<YOUR_ROLL_NUMBER>`

```bash
git init
git add .
git commit -m "Medical Report Explainer PS51"
git branch -M main
git remote add origin https://github.com/USERNAME/REPOSITORY.git
git push -u origin main
```

Never upload the `.env` file or API credentials.

## Safety rules implemented

- The LLM **extracts** and **explains**; it never classifies. LOW/NORMAL/HIGH is
  decided only by `analysis/range_checker.py`, and the explanation prompt forbids
  contradicting it.
- No diagnoses, no medication or treatment advice, no fear-inducing language
  (enforced by the explanation prompt rules).
- Only the reference ranges **printed on the uploaded report** are used — generic
  internet ranges are never substituted.
- The medical disclaimer is shown on the home page, under the analysis and in all
  downloads.

## Limitations

- Scanned/image PDFs are detected but not OCR-processed.
- Unit conversion is not attempted; mismatched units are flagged for review.
- When several age/sex-specific intervals are printed, the result is flagged
  **REFERENCE RANGE NEEDS REVIEW** rather than guessed.
- LLM extraction quality depends on how cleanly the PDF's text layer is laid out.

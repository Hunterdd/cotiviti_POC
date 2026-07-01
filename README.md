# Cotiviti Intern Submission — Policy Audit Assistant

**Topic:** Content Management in Health Care
**Candidate:** Dhruv
**Submission Type:** Cotiviti Intern Technical Screening

> A 3-agent AI pipeline for CMS Remote Patient Monitoring (RPM) policy ingestion, version diffing, and claim auditing — built as a Proof of Concept for the Cotiviti Intern screening.

---

## 📦 Deliverables

| Deliverable | File | Description |
|---|---|---|
| 📄 Written Report | [Report.pdf](./Report.pdf) | Two-page Word report on Content Management in Health Care with bibliography |
| 📊 Slide Presentation | [Cotiviti-POC..pptx](./Cotiviti-POC..pptx) | PowerPoint overview of the report and POC demo |
| 🎥 Video Recording | [video1382756422.mp4](./video1382756422.mp4) | Recorded walkthrough of the presentation and live POC screenshare |
| 💻 POC Demo Code | This repository | Streamlit app + 3-agent pipeline (see setup below) |

---

## 🧠 Topic: Content Management in Health Care

This POC addresses **Topic 3: Content Management in Health Care**, focusing on:

- **Billing and Coding Policies** — ingesting CMS Remote Patient Monitoring PDFs
- **Summarization of Content** — extracting structured rules from policy documents via LLM
- **Comparison of Content Changes** — diffing policy versions to surface tightened, loosened, added, or removed rules
- **Conversion of Written Policy into Rules** — translating natural-language policy text into machine-auditable JSON rule sets used to evaluate real claims

---

## 🏗️ POC Architecture: 3-Agent Pipeline

```
PDF Policy (CMS RPM)
       │
       ▼
[Agent 1 — Extractor]  →  Structured rules JSON
       │
       ▼
[Agent 2 — Differ]     →  Version diff report (added / removed / tightened / loosened)
       │
       ▼
[Agent 3 — Auditor]    →  Claim decision (approved / denied + citations + rationale)
```
---

## 🛠️ Stack

| Layer | Tool | Why |
|---|---|---|
| PDF parsing | `pdfplumber` | Free, zero API, sufficient for clean CMS PDFs |
| LLM | OpenRouter → DeepSeek | Flexible model routing, cost-efficient |
| Storage | JSON files | Versioned, auditable, human-readable |
| UI | Streamlit | Python-native, fast to demo |
| AI Coding Assistant | Claude Code (Anthropic) | Used to scaffold, iterate, and debug the POC codebase |

---

## ⚙️ Setup

```bash
# 1. Clone / open the project
cd project_folder

# 2. Create venv and install dependencies
bash setup.sh

# 3. Add your API key
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY

# 4. Activate venv (if not already active)
source .venv/bin/activate

# 5. Run the app
streamlit run app.py
```

---

## 🔑 Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Your OpenRouter API key |
| `MODEL` | `deepseek/deepseek-chat` | Any model on OpenRouter — swap freely |

To switch to DeepSeek R1 (reasoning model):
```
MODEL=deepseek/deepseek-r1
```

---

## 📁 Project Structure

```
cotiviti/
├── Report.docx                 ← Written report (deliverable)
├── Cotiviti-POC..pptx          ← Slide presentation (deliverable)
├── video1382756422.mp4         ← Video recording (deliverable)
│
├── .env.example                ← copy to .env
├── requirements.txt            ← 4 dependencies
├── setup.sh                    ← one-command venv setup
│
├── src/
│   ├── extractor.py            ← Agent 1: PDF → rules JSON
│   ├── differ.py               ← Agent 2: rules v1 + v2 → diff report
│   └── auditor.py              ← Agent 3: claim + rules → decision
│
├── data/
│   ├── policies/               ← PDF inputs
│   ├── rules/                  ← extracted rules (auto-created)
│   ├── diffs/                  ← diff reports (auto-created)
│   └── claims/
│       └── test_claims.json
│
└── app.py                      ← Streamlit UI
```

---

## 🤖 Agents

### `extractor.py`
- **Input:** PDF file path
- **Output:** `data/rules/rules_YYYY.json`
- **Fields:** `rule_id`, `description`, `applicable_codes`, `conditions`, `source_citation`

```bash
python src/extractor.py data/policies/rpm_policy_2025.pdf
```

### `differ.py`
- **Input:** two rules JSON files
- **Output:** `data/diffs/diff_YYYY_vs_YYYY.json`
- **Fields:** `added`, `removed`, `tightened`, `loosened`, `unchanged`, `summary`

```bash
python src/differ.py data/rules/rules_2023.json data/rules/rules_2025.json
```

### `auditor.py`
- **Input:** claim JSON + rules JSON
- **Output:** `decision`, `violations`, `met_rules`, `citations`, `rationale`

```bash
python src/auditor.py data/claims/test_claims.json data/rules/rules_2025.json
```

---

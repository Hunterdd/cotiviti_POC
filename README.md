# Policy Audit Assistant

A 3-agent AI pipeline for CMS Remote Patient Monitoring policy ingestion, version diffing, and claim auditing.

## Stack

| Layer | Tool | Why |
|---|---|---|
| PDF parsing | `pdfplumber` | Free, zero API, sufficient for clean CMS PDFs |
| LLM | OpenRouter → DeepSeek | Flexible model routing, cost-efficient |
| Storage | JSON files | Versioned, auditable, human-readable |
| UI | Streamlit | Python-native, fast to demo |

> **On LangChain / vector DBs**: Deliberately excluded. Every step is transparent and readable in under 10 minutes — which matters in a regulated healthcare context where auditability is non-negotiable.

---

## Setup

```bash
# 1. Clone / open the project
cd cotiviti

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

## Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Your OpenRouter API key |
| `MODEL` | `deepseek/deepseek-chat` | Any model on OpenRouter — swap freely |

To switch to DeepSeek R1 (reasoning model):
```
MODEL=deepseek/deepseek-r1
```

---

## Project Structure

```
cotiviti/
├── .env.example            ← copy to .env
├── requirements.txt        ← 4 dependencies
├── setup.sh                ← one-command venv setup
│
├── src/
│   ├── extractor.py        ← Agent 1: PDF → rules JSON
│   ├── differ.py           ← Agent 2: rules v1 + v2 → diff report
│   └── auditor.py          ← Agent 3: claim + rules → decision
│
├── data/
│   ├── policies/           ← PDF inputs
│   ├── rules/              ← extracted rules (auto-created)
│   ├── diffs/              ← diff reports (auto-created)
│   └── claims/
│       └── test_claims.json
│
└── app.py                  ← Streamlit UI
```

---

## Agents

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

## Test Claims

`data/claims/test_claims.json` contains 5 synthetic RPM claims:

| Claim | Scenario |
|---|---|
| CLM-001 | Clean approval — all conditions met |
| CLM-002 | Missing physician order, insufficient monitoring days |
| CLM-003 | Missing care plan documentation |
| CLM-004 | Dual additional billing sessions |
| CLM-005 | Non-FDA-cleared consumer device |

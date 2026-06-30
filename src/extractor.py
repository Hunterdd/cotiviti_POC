"""
Agent 1 — Extractor
Input:  path to a CMS policy PDF
Output: data/rules/rules_YYYY.json
"""

import json
import re
import sys
import hashlib
from pathlib import Path

import pdfplumber

from src.llm import MODEL, call_llm, parse_json

RULES_DIR = Path(__file__).parent.parent / "data" / "rules"
CACHE_DIR = Path("data/cache")


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Pull all text from every page using pdfplumber."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    return "\n\n".join(pages)


def build_extraction_prompt(policy_text: str) -> str:
    return f"""You are a healthcare policy analyst. Read the CMS policy document below and extract every distinct coverage rule.

Return a JSON array. Each element must have exactly these fields:
- "rule_id": sequential string like "R001", "R002" …
- "description": plain-English summary of the rule (1–3 sentences)
- "applicable_codes": list of CPT/HCPCS codes this rule applies to (empty list if not specified)
- "conditions": list of clinical or administrative conditions that must be met
- "source_citation": the section heading or line reference where this rule appears in the document

Return ONLY valid JSON — no markdown fences, no explanation text.

--- POLICY DOCUMENT ---
{policy_text}
--- END ---
"""


def extract_rules(pdf_path: str | Path, year: str | None = None, use_cache: bool = True) -> Path:
    """Extract rules from a PDF and write rules_YYYY.json to data/rules/, optionally using cache."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if year is None:
        match = re.search(r"(\d{4})", pdf_path.stem)
        year = match.group(1) if match else "unknown"

    RULES_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RULES_DIR / f"rules_{year}.json"

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            pdf_bytes = pdf_path.read_bytes()
            pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
            combined = f"{pdf_hash}||{MODEL}"
            cache_key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            cache_file = CACHE_DIR / f"extractor_{cache_key}.json"
            
            if cache_file.exists():
                rules = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(rules, list):
                    print(f"[extractor] [CACHE HIT] Loading extracted rules from cache for {pdf_path.name}")
                    out_path.write_text(json.dumps(rules, indent=2))
                    return out_path
        except Exception as e:
            print(f"[extractor] Cache read error: {e}")

    print(f"[extractor] Reading PDF: {pdf_path.name}")
    policy_text = extract_text_from_pdf(pdf_path)

    print(f"[extractor] Extracted {len(policy_text)} chars — calling {MODEL}")
    rules = parse_json(call_llm(build_extraction_prompt(policy_text)), kind="array")
    print(f"[extractor] Parsed {len(rules)} rules")

    out_path.write_text(json.dumps(rules, indent=2))
    print(f"[extractor] Saved → {out_path}")
    
    if use_cache:
        try:
            cache_file.write_text(json.dumps(rules, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[extractor] Cache write error: {e}")
            
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python src/extractor.py <path_to_pdf> [year]")
        sys.exit(1)
    extract_rules(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)

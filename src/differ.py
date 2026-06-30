"""
Agent 2 — Differ
Input:  two rules JSON files (e.g. rules_2023.json, rules_2025.json)
Output: data/diffs/diff_2023_vs_2025.json
"""

import json
import re
import sys
import hashlib
from pathlib import Path

from src.llm import MODEL, call_llm, load_json, parse_json

DIFFS_DIR = Path(__file__).parent.parent / "data" / "diffs"
CACHE_DIR = Path("data/cache")


def build_diff_prompt(rules_old: list, rules_new: list, year_old: str, year_new: str) -> str:
    return f"""You are a healthcare compliance analyst comparing two versions of a CMS coverage policy.

VERSION {year_old} RULES:
{json.dumps(rules_old, indent=2)}

VERSION {year_new} RULES:
{json.dumps(rules_new, indent=2)}

Compare the two versions and return a JSON object with exactly these keys:
- "added":     list of rules in {year_new} that did not exist in {year_old}
                Each item: {{"rule_id": "...", "description": "...", "impact": "plain English impact on claims"}}
- "removed":   list of rules in {year_old} that no longer appear in {year_new}
                Same shape as added.
- "tightened": list of rules that became MORE restrictive (fewer approvals expected)
                Each item: {{"rule_id_old": "...", "rule_id_new": "...", "what_changed": "...", "impact": "..."}}
- "loosened":  list of rules that became LESS restrictive (more approvals expected)
                Same shape as tightened.
- "unchanged": list of rule_ids that are substantively the same in both versions
- "summary":   2–4 sentence plain-English executive summary of the overall policy shift

CRITICAL GUIDELINES FOR MATCHING RULES:
1. Match rules by their semantic meaning and clinical intent, NOT just their rule ID (since IDs can shift if rules are inserted or re-ordered).
2. If a rule exists in both versions but has minor cosmetic wording, punctuation, or formatting changes, classify it as "unchanged" (or "tightened"/"loosened" if clinical intent changed).
3. Do NOT list a rule as "removed" in {year_old} and "added" in {year_new} if it represents the same underlying rule with minor phrasing tweaks. Group them together as "unchanged", "tightened", or "loosened" to prevent false changes.

Return ONLY valid JSON — no markdown fences, no explanation.
"""


def diff_rules(path_old: str | Path, path_new: str | Path, use_cache: bool = True) -> Path:
    """Compare two rule JSON files and write a diff report, optionally using cache."""
    path_old, path_new = Path(path_old), Path(path_new)

    def _year(p: Path) -> str:
        m = re.search(r"(\d{4})", p.stem)
        return m.group(1) if m else p.stem

    year_old, year_new = _year(path_old), _year(path_new)

    DIFFS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DIFFS_DIR / f"diff_{year_old}_vs_{year_new}.json"

    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            old_str = path_old.read_text(encoding="utf-8") if path_old.exists() else ""
            new_str = path_new.read_text(encoding="utf-8") if path_new.exists() else ""
            combined = f"{old_str}||{new_str}||{MODEL}"
            cache_key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            cache_file = CACHE_DIR / f"diff_{cache_key}.json"
            
            if cache_file.exists():
                diff = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(diff, dict):
                    print(f"[differ] [CACHE HIT] Loading rule diff from cache for diff_{year_old}_vs_{year_new}.json")
                    out_path.write_text(json.dumps(diff, indent=2))
                    return out_path
        except Exception as e:
            print(f"[differ] Cache read error: {e}")

    print(f"[differ] Loading rules: {path_old.name} vs {path_new.name}")
    prompt = build_diff_prompt(load_json(path_old), load_json(path_new), year_old, year_new)

    print(f"[differ] Calling {MODEL} for diff analysis")
    diff = parse_json(call_llm(prompt))

    out_path.write_text(json.dumps(diff, indent=2))
    print(f"[differ] Saved → {out_path}")
    
    if use_cache:
        try:
            cache_file.write_text(json.dumps(diff, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[differ] Cache write error: {e}")
            
    return out_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/differ.py <rules_old.json> <rules_new.json>")
        sys.exit(1)
    diff_rules(sys.argv[1], sys.argv[2])

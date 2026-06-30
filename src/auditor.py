"""
Agent 3 — Auditor
Input:  a claim dict + path to a rules JSON file
Output: structured audit decision (approve / deny / needs_review)
"""

import json
import sys
import hashlib
from pathlib import Path

from src.llm import call_llm, load_json, parse_json

CACHE_DIR = Path("data/cache")


def build_audit_prompt(claim: dict, rules: list) -> str:
    return f"""You are a senior healthcare claims auditor. Your job is to evaluate whether a submitted claim
complies with the CMS coverage policy rules provided below.

CLAIM:
{json.dumps(claim, indent=2)}

POLICY RULES:
{json.dumps(rules, indent=2)}

Evaluate the claim against every applicable rule and return a JSON object with exactly these keys:

- "decision": one of "approve", "deny", or "needs_review"
  - "approve"      → claim meets all applicable rules
  - "deny"         → claim clearly violates one or more rules
  - "needs_review" → insufficient information or ambiguous compliance

- "violations": list of objects for each rule the claim fails
  Each: {{"rule_id": "...", "rule_description": "...", "reason": "why this claim fails this rule"}}

- "met_rules": list of rule_ids the claim satisfies

- "citations": list of source_citation strings from the rules that were evaluated

- "rationale": 2–4 sentence plain-English explanation of the overall decision, suitable
  for a clinician or billing staff member to read

Return ONLY valid JSON — no markdown fences, no explanation text.
"""


def build_audit_batch_prompt(claims: list, rules: list) -> str:
    return f"""You are a senior healthcare claims auditor. Your job is to evaluate a batch of submitted claims
against the CMS coverage policy rules provided below.

POLICY RULES:
{json.dumps(rules, indent=2)}

CLAIMS TO AUDIT (BATCH OF {len(claims)}):
{json.dumps(claims, indent=2)}

Evaluate each claim against every applicable rule and return a JSON array containing exactly one object for each claim in the input batch, in the exact same order.
Each object in the array must correspond to one input claim and have exactly these keys:
- "claim_id": the claim_id from the input claim object
- "decision": one of "approve", "deny", or "needs_review"
  - "approve"      → claim meets all applicable rules
  - "deny"         → claim clearly violates one or more rules
  - "needs_review" → insufficient information or ambiguous compliance
- "violations": list of objects for each rule the claim fails
  Each: {{"rule_id": "...", "rule_description": "...", "reason": "why this claim fails this rule"}}
- "met_rules": list of rule_ids the claim satisfies
- "citations": list of source_citation strings from the rules that were evaluated
- "rationale": 2–4 sentence plain-English explanation of the overall decision, suitable for a clinician or billing staff member to read

Return ONLY a valid JSON array of objects — no markdown fences, no explanation text.
"""



def audit_claim(claim: dict, rules_path: str | Path, use_cache: bool = True) -> dict:
    """Audit a claim against a specific rules version, optionally using persistent cache."""
    rules_path = Path(rules_path)
    
    if use_cache:
        from src.llm import MODEL
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # Serialize claim and rules stably
        claim_str = json.dumps(claim, sort_keys=True)
        try:
            rules_str = rules_path.read_text(encoding="utf-8")
        except Exception:
            rules_str = ""
            
        combined = f"{claim_str}||{rules_str}||{MODEL}"
        cache_key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        cache_file = CACHE_DIR / f"{cache_key}.json"
        
        if cache_file.exists():
            try:
                result = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(result, dict) and "decision" in result:
                    print(f"[auditor] [CACHE HIT] Claim {claim.get('claim_id', '?')} against {rules_path.name}")
                    return result
            except Exception:
                pass

    print(f"[auditor] Auditing claim {claim.get('claim_id', '?')} against {rules_path.name}")

    result = parse_json(call_llm(build_audit_prompt(claim, load_json(rules_path))))
    result["claim_id"]      = claim.get("claim_id")
    result["rules_version"] = rules_path.stem
    print(f"[auditor] Decision: {result.get('decision', 'unknown')}")
    
    if use_cache:
        try:
            cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[auditor] Failed to write cache: {e}")
            
    return result


def audit_claims_batch(claims: list, rules_path: str | Path, use_cache: bool = True) -> list:
    """Audit a list of claims against a specific rules version in batches of 4, using cache where available."""
    rules_path = Path(rules_path)
    from src.llm import MODEL, call_llm, parse_json
    import hashlib
    
    rules = load_json(rules_path)
    
    results = {}
    claims_to_query = []
    claims_cache_info = {}  # claim_id -> (cache_file, cache_key)
    
    # 1. Check cache for each claim individually (to load instantly if hit)
    if use_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        for claim in claims:
            cid = claim.get("claim_id")
            claim_str = json.dumps(claim, sort_keys=True)
            try:
                rules_str = rules_path.read_text(encoding="utf-8")
            except Exception:
                rules_str = ""
            
            combined = f"{claim_str}||{rules_str}||{MODEL}"
            cache_key = hashlib.sha256(combined.encode("utf-8")).hexdigest()
            cache_file = CACHE_DIR / f"{cache_key}.json"
            
            claims_cache_info[cid] = (cache_file, cache_key)
            
            if cache_file.exists():
                try:
                    res = json.loads(cache_file.read_text(encoding="utf-8"))
                    if isinstance(res, dict) and "decision" in res:
                        print(f"[auditor] [CACHE HIT] Claim {cid} against {rules_path.name}")
                        results[cid] = res
                        continue
                except Exception:
                    pass
            claims_to_query.append(claim)
    else:
        claims_to_query = list(claims)
        
    # If all claims hit cache, we are done!
    if not claims_to_query:
        return [results[c.get("claim_id")] for c in claims]
        
    # 2. Process claims_to_query in batches of 4
    batch_size = 4
    for idx in range(0, len(claims_to_query), batch_size):
        batch = claims_to_query[idx : idx + batch_size]
        print(f"[auditor] Batch query: auditing {len(batch)} claims against {rules_path.name}...")
        
        try:
            prompt = build_audit_batch_prompt(batch, rules)
            raw_response = call_llm(prompt)
            batch_results = parse_json(raw_response, kind="array")
            
            if not isinstance(batch_results, list) or len(batch_results) != len(batch):
                raise ValueError(
                    f"Batch response length mismatch: expected {len(batch)}, "
                    f"got {len(batch_results) if isinstance(batch_results, list) else 'not a list'}"
                )
                
            for claim, res in zip(batch, batch_results):
                cid = claim.get("claim_id")
                res["claim_id"] = cid
                res["rules_version"] = rules_path.stem
                results[cid] = res
                
                # Write to cache individually
                if use_cache and cid in claims_cache_info:
                    c_file, _ = claims_cache_info[cid]
                    try:
                        c_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[auditor] Batch failed with error: {e}. Falling back to individual audits for this batch...")
            # Fallback: run each claim in the batch individually
            for claim in batch:
                cid = claim.get("claim_id")
                try:
                    res = audit_claim(claim, rules_path, use_cache=use_cache)
                    results[cid] = res
                except Exception as inner_e:
                    res = {
                        "decision": "error",
                        "violations": [],
                        "met_rules": [],
                        "citations": [],
                        "rationale": str(inner_e),
                        "claim_id": cid,
                        "rules_version": rules_path.stem
                    }
                    results[cid] = res
                    
    return [results[c.get("claim_id")] for c in claims]



# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python src/auditor.py <claim_json_file> <rules_json_file>")
        sys.exit(1)

    claim_data = json.loads(Path(sys.argv[1]).read_text())
    if isinstance(claim_data, list):
        claim_data = claim_data[0]

    print(json.dumps(audit_claim(claim_data, sys.argv[2]), indent=2))

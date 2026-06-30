"""
app.py — Streamlit UI for the Policy Audit Assistant
Three tabs:
  1. Extract Rules    — upload a PDF, run extractor, view & delete rules files
  2. Compare Policies — pick two rule sets, run differ, view & delete diff files
  3. Regression Audit — run ALL test claims against two versions (PRIMARY)
                        + manual single-claim audit (secondary, collapsed)
"""

import json
from pathlib import Path

import streamlit as st

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Policy Audit Assistant",
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── constants ─────────────────────────────────────────────────────────────────

POLICIES_DIR = Path("data/policies")
RULES_DIR    = Path("data/rules")
DIFFS_DIR    = Path("data/diffs")
CLAIMS_FILE  = Path("data/claims/test_claims.json")

# ── CSS ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    color: #e6edf3;
}

.hero {
    background: linear-gradient(90deg, #1f6feb22 0%, #388bfd22 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 24px 32px;
    margin-bottom: 28px;
}
.hero h1 { margin: 0; font-size: 2rem; font-weight: 700; color: #e6edf3; }
.hero p  { margin: 6px 0 0; color: #8b949e; font-size: 0.95rem; }

/* Decision badges */
.badge-approve { background:#1a7f37; color:#fff; padding:3px 10px; border-radius:20px; font-weight:600; font-size:0.82rem; }
.badge-deny    { background:#b62324; color:#fff; padding:3px 10px; border-radius:20px; font-weight:600; font-size:0.82rem; }
.badge-review  { background:#9e6a03; color:#fff; padding:3px 10px; border-radius:20px; font-weight:600; font-size:0.82rem; }

/* Regression result rows */
.reg-row {
    display: flex;
    align-items: center;
    padding: 10px 16px;
    border-radius: 8px;
    margin-bottom: 6px;
    border: 1px solid #30363d;
    gap: 12px;
}
.reg-stable  { border-left: 4px solid #3fb950; background: #0d1f0f; }
.reg-changed { border-left: 4px solid #d29922; background: #1f1700; }

/* Diff section headers */
.diff-added    { color: #3fb950; font-weight: 600; }
.diff-removed  { color: #f85149; font-weight: 600; }
.diff-tightened{ color: #d29922; font-weight: 600; }
.diff-loosened { color: #58a6ff; font-weight: 600; }

/* Streamlit overrides */
div[data-testid="stTabs"] button { font-family: 'Inter', sans-serif !important; font-weight: 500; }
div.stButton > button {
    background: linear-gradient(90deg,#1f6feb,#388bfd);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; padding: 10px 24px; transition: opacity 0.2s;
}
div.stButton > button:hover { opacity: 0.85; }
</style>
""", unsafe_allow_html=True)

# ── hero ──────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="hero">
  <h1>⚕️ Policy Audit Assistant</h1>
  <p>CMS Remote Patient Monitoring — rule extraction · policy diff · regression audit</p>
</div>
""", unsafe_allow_html=True)

# ── tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["📄 Extract Rules", "🔀 Compare Policies", "🔍 Regression Audit"])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — EXTRACT RULES
# ─────────────────────────────────────────────────────────────────────────────

with tab1:
    st.subheader("Extract Coverage Rules from a PDF")
    st.caption("Reads a PDF with pdfplumber → sends to DeepSeek → writes structured rules JSON.")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("**Option A — Existing PDF in `data/policies/`**")
        existing_pdfs = sorted(POLICIES_DIR.glob("*.pdf")) if POLICIES_DIR.exists() else []
        if existing_pdfs:
            selected_pdf = st.selectbox(
                "Select policy PDF",
                options=existing_pdfs,
                format_func=lambda p: p.name,
                key="extract_existing_pdf",
            )
        else:
            st.info("No PDFs found in `data/policies/`. Upload one below.")
            selected_pdf = None

        st.markdown("**Option B — Upload a PDF**")
        uploaded = st.file_uploader("Upload PDF", type="pdf", key="extract_upload")
        if uploaded:
            POLICIES_DIR.mkdir(parents=True, exist_ok=True)
            save_path = POLICIES_DIR / uploaded.name
            save_path.write_bytes(uploaded.read())
            selected_pdf = save_path
            st.success(f"Saved → {save_path}")

        year_override = st.text_input("Year (inferred from filename if blank)", key="year_override")

        if st.button("⚡ Extract Rules", key="btn_extract"):
            if not selected_pdf:
                st.error("Select or upload a PDF first.")
            else:
                with st.spinner(f"Extracting rules from {selected_pdf.name}…"):
                    try:
                        from src.extractor import extract_rules
                        out_path = extract_rules(selected_pdf, year_override.strip() or None)
                        st.session_state["last_extracted"] = str(out_path)
                        st.success(f"Done → `{out_path}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")

    with col_right:
        rules_files = sorted(RULES_DIR.glob("rules_*.json")) if RULES_DIR.exists() else []
        if rules_files:
            r_col1, r_col2 = st.columns([4, 1])
            with r_col1:
                view_rules = st.selectbox(
                    "View / delete rules file",
                    options=rules_files,
                    format_func=lambda p: p.name,
                    key="view_rules_file",
                )
            with r_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🗑️", key="del_rules", help=f"Delete {view_rules.name}"):
                    view_rules.unlink()
                    st.toast(f"Deleted {view_rules.name}")
                    st.rerun()

            rules_data = json.loads(view_rules.read_text())
            st.markdown(f"**{len(rules_data)} rules extracted**")
            for rule in rules_data:
                with st.expander(f"🔹 {rule.get('rule_id','?')} — {rule.get('description','')[:75]}…"):
                    st.markdown(f"**Description:** {rule.get('description','')}")
                    codes = rule.get("applicable_codes", [])
                    if codes:
                        st.markdown(f"**Codes:** `{'`, `'.join(codes)}`")
                    for c in rule.get("conditions", []):
                        st.markdown(f"- {c}")
                    st.caption(f"Source: {rule.get('source_citation','N/A')}")
        else:
            st.info("Run extraction to see rules here.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — COMPARE POLICIES
# ─────────────────────────────────────────────────────────────────────────────

with tab2:
    st.subheader("Compare Two Policy Versions")
    st.caption("Categorises every rule change as added, removed, tightened, or loosened.")

    rules_files = sorted(RULES_DIR.glob("rules_*.json")) if RULES_DIR.exists() else []

    if len(rules_files) < 2:
        st.warning("You need at least two extracted rules files. Run **Extract Rules** first.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            old_file = st.selectbox("Older policy", rules_files, format_func=lambda p: p.name, key="diff_old")
        with col_b:
            new_file = st.selectbox("Newer policy", rules_files, format_func=lambda p: p.name, key="diff_new")

        if st.button("🔀 Run Diff", key="btn_diff"):
            if old_file == new_file:
                st.error("Select two different files.")
            else:
                with st.spinner("Comparing policies…"):
                    try:
                        from src.differ import diff_rules
                        out_path = diff_rules(old_file, new_file)
                        st.session_state["last_diff"] = str(out_path)
                        st.success(f"Diff saved → `{out_path}`")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Diff failed: {e}")

    diff_files = sorted(DIFFS_DIR.glob("diff_*.json")) if DIFFS_DIR.exists() else []
    if diff_files:
        d_col1, d_col2 = st.columns([4, 1])
        with d_col1:
            view_diff = st.selectbox(
                "View / delete diff file",
                diff_files,
                format_func=lambda p: p.name,
                key="view_diff",
            )
        with d_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️", key="del_diff", help=f"Delete {view_diff.name}"):
                view_diff.unlink()
                st.toast(f"Deleted {view_diff.name}")
                st.rerun()

        diff_data = json.loads(view_diff.read_text())

        summary = diff_data.get("summary", "")
        if summary:
            st.info(f"📋 **Executive Summary:** {summary}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("➕ Added",     len(diff_data.get("added", [])))
        m2.metric("➖ Removed",   len(diff_data.get("removed", [])))
        m3.metric("🔒 Tightened", len(diff_data.get("tightened", [])))
        m4.metric("🔓 Loosened",  len(diff_data.get("loosened", [])))

        for section, label, css in [
            ("added",     "➕ Added Rules",     "diff-added"),
            ("removed",   "➖ Removed Rules",   "diff-removed"),
            ("tightened", "🔒 Tightened Rules", "diff-tightened"),
            ("loosened",  "🔓 Loosened Rules",  "diff-loosened"),
        ]:
            items = diff_data.get(section, [])
            if items:
                st.markdown(f'<p class="{css}">{label}</p>', unsafe_allow_html=True)
                for item in items:
                    rid = item.get("rule_id") or f"{item.get('rule_id_old','?')} → {item.get('rule_id_new','?')}"
                    desc = item.get("description", item.get("what_changed", ""))[:80]
                    with st.expander(f"{rid} — {desc}"):
                        if item.get("what_changed"):
                            st.markdown(f"**What changed:** {item['what_changed']}")
                        st.markdown(f"**Impact:** {item.get('impact','')}")

        unchanged = diff_data.get("unchanged", [])
        if unchanged:
            st.caption(f"Unchanged rules: {', '.join(str(x) for x in unchanged)}")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — REGRESSION AUDIT  (primary)  +  manual claim  (secondary)
# ─────────────────────────────────────────────────────────────────────────────

with tab3:
    st.subheader("Regression Audit")
    st.caption(
        "Run all test claims against **two policy versions** — see which decisions changed "
        "and which stayed stable. Stable = rule didn't affect this claim. Changed = needs human review."
    )

    rules_files = sorted(RULES_DIR.glob("rules_*.json")) if RULES_DIR.exists() else []

    if not rules_files:
        st.warning("No rule files found. Extract rules in **Tab 1** first.")
        st.stop()

    # ── version selectors ─────────────────────────────────────────────────────
    v_col1, v_col2, v_col3 = st.columns([2, 2, 1], gap="small")
    with v_col1:
        baseline_file = st.selectbox(
            "🔵 Baseline version (older)",
            rules_files,
            format_func=lambda p: p.name,
            key="reg_baseline",
        )
    with v_col2:
        new_version_file = st.selectbox(
            "🟢 New version",
            rules_files,
            format_func=lambda p: p.name,
            index=min(1, len(rules_files) - 1),
            key="reg_new",
        )
    with v_col3:
        st.markdown("<br>", unsafe_allow_html=True)
        run_regression = st.button("▶ Run Regression", key="btn_regression", use_container_width=True)

    # ── link to diff if it exists ─────────────────────────────────────────────
    def _year(p: Path) -> str:
        import re as _re
        m = _re.search(r"(\d{4})", p.stem)
        return m.group(1) if m else p.stem

    baseline_year = _year(baseline_file)
    new_year      = _year(new_version_file)
    diff_path     = DIFFS_DIR / f"diff_{baseline_year}_vs_{new_year}.json"
    if diff_path.exists():
        st.caption(f"📂 Diff available: `{diff_path.name}` — view in **Compare Policies** tab")

    st.markdown("---")

    # ── run regression ────────────────────────────────────────────────────────
    if run_regression:
        if baseline_file == new_version_file:
            st.error("Select two different rule versions.")
            st.stop()
        # Compute policy diff on the fly if it doesn't exist
        if not diff_path.exists():
            from src.differ import diff_rules
            try:
                diff_rules(baseline_file, new_version_file)
            except Exception as e:
                st.error(f"Failed to generate policy diff: {e}")
                st.stop()

        test_claims = json.loads(CLAIMS_FILE.read_text())
        from src.auditor import audit_claims_batch
        import concurrent.futures

        results = []
        progress_bar = st.progress(0, text="Running batch audits...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            # Run baseline and new audits in parallel (strictly isolating policy versions)
            f_base = executor.submit(audit_claims_batch, test_claims, baseline_file)
            f_new  = executor.submit(audit_claims_batch, test_claims, new_version_file)

            # Wait for both to complete
            baseline_results = f_base.result()
            new_results      = f_new.result()

        for claim, b_res, n_res in zip(test_claims, baseline_results, new_results):
            cid = claim.get("claim_id", "CLM-?")
            baseline_dec = b_res.get("decision", "error").lower()
            new_dec      = n_res.get("decision", "error").lower()
            changed      = baseline_dec != new_dec

            results.append({
                "claim_id":        cid,
                "scenario":        claim.get("notes", "")[:60] or ", ".join(claim.get("diagnosis_codes", [])),
                "baseline_dec":    baseline_dec,
                "new_dec":         new_dec,
                "changed":         changed,
                "baseline_result": b_res,
                "new_result":      n_res,
                "claim":           claim,
            })

        progress_bar.progress(1.0, text="Done ✅")
        st.session_state["regression_results"] = results
        st.session_state["regression_label"]   = f"{baseline_file.name}  vs  {new_version_file.name}"
        st.rerun()

    # ── display regression results ────────────────────────────────────────────
    results = st.session_state.get("regression_results")
    if results:
        label = st.session_state.get("regression_label", "")
        st.caption(f"Results for: **{label}**")

        baseline_file = st.session_state.get("reg_baseline")
        new_version_file = st.session_state.get("reg_new")
        
        baseline_year = _year(baseline_file) if baseline_file else "old"
        new_year      = _year(new_version_file) if new_version_file else "new"
        
        diff_data = {}
        if baseline_file and new_version_file:
            diff_path = DIFFS_DIR / f"diff_{baseline_year}_vs_{new_year}.json"
            if diff_path.exists():
                try:
                    diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
                except Exception:
                    pass

        # Collect changed rule IDs
        changed_rule_ids = set()
        if diff_data:
            for rule in diff_data.get("added", []):
                if isinstance(rule, dict) and "rule_id" in rule:
                    changed_rule_ids.add(rule["rule_id"])
            for rule in diff_data.get("removed", []):
                if isinstance(rule, dict) and "rule_id" in rule:
                    changed_rule_ids.add(rule["rule_id"])
            for rule in diff_data.get("tightened", []):
                if isinstance(rule, dict):
                    if "rule_id_old" in rule: changed_rule_ids.add(rule["rule_id_old"])
                    if "rule_id_new" in rule: changed_rule_ids.add(rule["rule_id_new"])
            for rule in diff_data.get("loosened", []):
                if isinstance(rule, dict):
                    if "rule_id_old" in rule: changed_rule_ids.add(rule["rule_id_old"])
                    if "rule_id_new" in rule: changed_rule_ids.add(rule["rule_id_new"])

        def get_touched_rules(audit_res):
            touched = set()
            if not audit_res or not isinstance(audit_res, dict):
                return touched
            for v in audit_res.get("violations", []):
                if isinstance(v, dict) and "rule_id" in v:
                    touched.add(v["rule_id"])
                elif isinstance(v, str):
                    touched.add(v)
            for m in audit_res.get("met_rules", []):
                if isinstance(m, dict) and "rule_id" in m:
                    touched.add(m["rule_id"])
                elif isinstance(m, str):
                    touched.add(m)
            return touched

        enriched_results = []
        for r in results:
            b_res = r.get("baseline_result", {})
            n_res = r.get("new_result", {})
            
            touched_rules = get_touched_rules(b_res) | get_touched_rules(n_res)
            touched_changed = touched_rules & changed_rule_ids
            affected_by_change = bool(touched_changed)
            decision_changed = r.get("changed", False)
            
            if not affected_by_change and not decision_changed:
                category = "Expected Stable"
                badge = "🟢 Expected Stable"
                explanation = "No modified policy rules apply to this claim, and the audit decision remained identical."
            elif affected_by_change and decision_changed:
                category = "Expected Change"
                badge = "🔵 Expected Change"
                explanation = f"Claim touched updated rules ({', '.join(sorted(touched_changed))}), and the audit decision changed as expected."
            elif not affected_by_change and decision_changed:
                category = "Anomaly"
                badge = "❌ Anomaly (Needs Review)"
                explanation = "Decision changed, but no underlying policy rules were modified. Possible LLM variance."
            else: # affected_by_change and not decision_changed
                category = "Unchanged / Check"
                badge = "⚠️ Unchanged despite Policy Update"
                explanation = f"Claim touched updated rules ({', '.join(sorted(touched_changed))}), but the overall decision remained the same. Confirm if correct."

            enriched_results.append({
                **r,
                "category": category,
                "badge": badge,
                "explanation": explanation,
                "touched_rules": sorted(list(touched_rules)),
                "touched_changed_rules": sorted(list(touched_changed))
            })

        # Calculate counts
        stable_expected_count = sum(1 for r in enriched_results if r["category"] == "Expected Stable")
        changed_expected_count = sum(1 for r in enriched_results if r["category"] == "Expected Change")
        anomaly_count = sum(1 for r in enriched_results if r["category"] == "Anomaly")
        unchanged_check_count = sum(1 for r in enriched_results if r["category"] == "Unchanged / Check")

        # 1. Summary Dashboard Metrics
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("🟢 Expected Stable", stable_expected_count)
        s2.metric("🔵 Expected Change", changed_expected_count)
        s3.metric("❌ Anomalies", anomaly_count)
        s4.metric("⚠️ Unchanged / Check", unchanged_check_count)

        # 2. Recommendations Banners
        if anomaly_count > 0:
            st.error(
                f"🚨 **System Anomaly Detected**: {anomaly_count} claim decision(s) changed without any underlying policy rule modifications. "
                "This could indicate LLM inconsistency or model variance. Review these cases first."
            )
        elif unchanged_check_count > 0:
            st.warning(
                f"🔍 **Review Recommended**: {unchanged_check_count} claim(s) touched modified rules but did not change their final decision. "
                "Verify if the rule modifications should have triggered a decision change."
            )
        else:
            st.success("✅ **Policy Migration Successful**: All claims behaved exactly as expected (either stable with no rule changes, or changed in line with policy modifications)!")

        st.markdown("---")

        # 3. Filter Claims
        st.markdown("### 🔍 Filter and Search Claims")
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            status_filter = st.multiselect(
                "Filter by Audit Status Class",
                options=["🟢 Expected Stable", "🔵 Expected Change", "❌ Anomaly (Needs Review)", "⚠️ Unchanged despite Policy Update"],
                default=["🟢 Expected Stable", "🔵 Expected Change", "❌ Anomaly (Needs Review)", "⚠️ Unchanged despite Policy Update"]
            )
        with f_col2:
            search_query = st.text_input("Search Claim ID or Scenario Notes", "").strip().lower()

        # Apply Filters
        filtered_results = []
        for r in enriched_results:
            if r["badge"] not in status_filter:
                continue
            if search_query:
                notes = r["claim"].get("notes", "").lower()
                cid = r["claim_id"].lower()
                scenario = r["scenario"].lower()
                if search_query not in cid and search_query not in notes and search_query not in scenario:
                    continue
            filtered_results.append(r)

        if not filtered_results:
            st.info("No claims match the active filter or search query.")
        else:
            def _badge(decision: str) -> str:
                icons = {"approve": "✅ approve", "deny": "❌ deny", "needs_review": "⚠️ needs review", "error": "🔴 error"}
                return icons.get(decision, decision)

            # Header row
            h1, h2, h3, h4, h5 = st.columns([1.0, 2.5, 1.2, 1.2, 2.1])
            h1.markdown("**Claim**")
            h2.markdown("**Scenario**")
            h3.markdown(f"**Baseline**")
            h4.markdown(f"**New**")
            h5.markdown("**Status Class**")
            st.markdown("<hr style='margin:4px 0 8px;border-color:#30363d'>", unsafe_allow_html=True)

            for r in filtered_results:
                c1, c2, c3, c4, c5 = st.columns([1.0, 2.5, 1.2, 1.2, 2.1])
                c1.markdown(f"`{r['claim_id']}`")
                c2.markdown(r["scenario"][:60])
                c3.markdown(_badge(r["baseline_dec"]))
                c4.markdown(_badge(r["new_dec"]))
                c5.markdown(r["badge"])

                with st.expander(f"🔍 Review {r['claim_id']} — What & Why"):
                    st.info(f"**Status Analysis**: {r['explanation']}")
                    
                    if r["touched_rules"]:
                        st.markdown(f"**Touched Rules**: {', '.join(f'`{rid}`' for rid in r['touched_rules'])}")
                    if r["touched_changed_rules"]:
                        st.markdown(f"**Modified Policy Rules Touched**: {', '.join(f'`{rid}`' for rid in r['touched_changed_rules'])}")
                    
                    st.markdown("---")
                    d1, d2 = st.columns(2)
                    with d1:
                        st.markdown(f"**Baseline ({baseline_year})**")
                        st.markdown(f"Decision: {_badge(r['baseline_dec'])}")
                        rat = r["baseline_result"].get("rationale", "")
                        if rat:
                            st.markdown(f"*{rat}*")
                        viols = r["baseline_result"].get("violations", [])
                        if viols:
                            for v in viols:
                                st.error(f"**{v.get('rule_id','?')}** — {v.get('reason','')}")
                        met = r["baseline_result"].get("met_rules", [])
                        if met:
                            st.success(f"Met: {', '.join(str(m) for m in met)}")
                    with d2:
                        st.markdown(f"**New version ({new_year})**")
                        st.markdown(f"Decision: {_badge(r['new_dec'])}")
                        rat = r["new_result"].get("rationale", "")
                        if rat:
                            st.markdown(f"*{rat}*")
                        viols = r["new_result"].get("violations", [])
                        if viols:
                            for v in viols:
                                st.error(f"**{v.get('rule_id','?')}** — {v.get('reason','')}")
                        met = r["new_result"].get("met_rules", [])
                        if met:
                            st.success(f"Met: {', '.join(str(m) for m in met)}")

                    with st.expander("Raw JSON Details"):
                        rj1, rj2 = st.columns(2)
                        rj1.json(r["baseline_result"])
                        rj2.json(r["new_result"])

    else:
        st.info("Select two policy versions and click **▶ Run Regression** to compare all test claims.")

    # ── secondary: manual single-claim audit ─────────────────────────────────
    st.markdown("---")
    with st.expander("➕ Audit a custom claim manually"):
        st.caption("Side feature — audit a single claim against one version.")

        test_claims_manual = json.loads(CLAIMS_FILE.read_text()) if CLAIMS_FILE.exists() else []

        prefill_option = st.selectbox(
            "Pre-fill from test claims (optional)",
            options=["— blank —"] + [f"{c['claim_id']} — {', '.join(c.get('diagnosis_codes', []))}" for c in test_claims_manual],
            key="prefill_manual",
        )
        prefill_idx = None
        if prefill_option != "— blank —":
            prefill_idx = next(
                (i for i, c in enumerate(test_claims_manual)
                 if f"{c['claim_id']} — {', '.join(c.get('diagnosis_codes', []))}" == prefill_option),
                None,
            )

        def pf(key, default=""):
            if prefill_idx is not None:
                val = test_claims_manual[prefill_idx].get(key, default)
                return str(val) if not isinstance(val, list) else ", ".join(str(v) for v in val)
            return str(default)

        m1, m2 = st.columns(2)
        with m1:
            claim_id   = st.text_input("Claim ID",              value=pf("claim_id", "CLM-NEW"), key="m_id")
            patient_id = st.text_input("Patient ID",            value=pf("patient_id"),           key="m_pat")
            dos        = st.text_input("Date of Service",       value=pf("date_of_service"),      key="m_dos")
            dx_codes   = st.text_input("Diagnosis Codes (CSV)", value=pf("diagnosis_codes"),      key="m_dx")
            proc_codes = st.text_input("Procedure Codes (CSV)", value=pf("procedure_codes"),      key="m_proc")
            device     = st.text_input("Device Description",    value=pf("device"),               key="m_dev")
        with m2:
            mon_days   = st.number_input("Monitoring Days",     value=int(pf("monitoring_duration_days", 30)), min_value=0, key="m_days")
            phys_order = st.checkbox("Physician Order on File", value=pf("physician_order") == "True", key="m_order")
            care_plan  = st.checkbox("Care Plan Documented",   value=pf("care_plan_documented") == "True", key="m_care")
            comm_mins  = st.number_input("Interactive Communication (mins)", value=int(pf("interactive_communication_minutes", 0)), min_value=0, key="m_mins")
            notes      = st.text_area("Notes", value=pf("notes"), key="m_notes", height=80)

        rules_version_manual = st.selectbox(
            "Policy version to audit against",
            rules_files,
            format_func=lambda p: p.name,
            key="manual_rules_ver",
        )

        if st.button("🔍 Audit Claim", key="btn_manual_audit"):
            claim = {
                "claim_id": claim_id, "patient_id": patient_id, "date_of_service": dos,
                "diagnosis_codes":  [c.strip() for c in dx_codes.split(",") if c.strip()],
                "procedure_codes":  [c.strip() for c in proc_codes.split(",") if c.strip()],
                "device": device, "monitoring_duration_days": mon_days,
                "physician_order": phys_order, "care_plan_documented": care_plan,
                "interactive_communication_minutes": comm_mins, "notes": notes,
            }
            with st.spinner("Auditing…"):
                try:
                    from src.auditor import audit_claim
                    result = audit_claim(claim, rules_version_manual)
                    st.session_state["manual_audit_result"] = result
                except Exception as e:
                    st.error(f"Audit failed: {e}")

        manual_result = st.session_state.get("manual_audit_result")
        if manual_result:
            decision = manual_result.get("decision", "unknown").lower()
            badge_class = {"approve": "badge-approve", "deny": "badge-deny"}.get(decision, "badge-review")
            st.markdown(f'<span class="{badge_class}">{decision.upper()}</span>', unsafe_allow_html=True)
            st.markdown("")
            rationale = manual_result.get("rationale", "")
            if rationale:
                st.markdown(f"**Rationale:** {rationale}")
            violations = manual_result.get("violations", [])
            if violations:
                st.markdown(f"**❌ Violations ({len(violations)})**")
                for v in violations:
                    st.error(f"**{v.get('rule_id','?')}** — {v.get('reason','')}")
            met = manual_result.get("met_rules", [])
            if met:
                st.success(f"✅ Rules met: {', '.join(str(r) for r in met)}")
            with st.expander("Raw JSON"):
                st.json(manual_result)

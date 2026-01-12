# ===============================================
# Streamlit Safeguarding Proof-of-Concept App
# ===============================================

import streamlit as st
import pandas as pd
import os
from graphviz import Digraph
import io

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(layout="wide", page_title="Safeguarding Form")

st.title("Safeguarding Referral Proof of Concept – Demo")
st.caption("Rules-driven prototype generated from specification spreadsheet")
st.divider()

# -----------------------------
# Load Excel (cached)
# -----------------------------
EXCEL_FILE = "/home/king/projects/Safeguarding_POC/Data/Safeguarding specification v0.1 2025_12_19_PK.xlsx"

if not os.path.exists(EXCEL_FILE):
    st.error(f"File not found: {EXCEL_FILE}")
    st.stop()

@st.cache_data
def load_excel(path):
    df_q = pd.read_excel(path, sheet_name="Safeguarding_Q")
    df_a = pd.read_excel(path, sheet_name="Safeguarding_A")

    df_q["domain"] = df_q["domain"].str.lower().str.strip()
    df_a["domain"] = df_a["domain"].str.lower().str.strip()

    # Ensure consistent types to avoid PyArrow errors
    df_a["answer_value"] = df_a["answer_value"].astype(str)
    df_a["next_field_ref"] = df_a["next_field_ref"].astype(str, errors="ignore")
    df_q["field_ref"] = df_q["field_ref"].astype(str)

    return df_q, df_a

df_q, df_a = load_excel(EXCEL_FILE)

# -----------------------------
# Precompute rule structures
# -----------------------------
domains = df_q["domain"].unique()

child_map = {}
parent_map = {}
options_map = {}

for domain in domains:
    child_map[domain] = {}
    parent_map[domain] = {}

    domain_q = df_q[df_q["domain"] == domain]
    domain_a = df_a[df_a["domain"] == domain]

    options_map[domain] = {
        q["field_ref"]: [
            o.strip()
            for o in str(q.get("answer_options", "")).split(";")
            if o.strip()
        ]
        for _, q in domain_q.iterrows()
    }

    for _, r in domain_a.iterrows():
        child_map[domain].setdefault(r["field_ref"], []).append(
            (str(r["answer_value"]), r["next_field_ref"])
        )

    for _, r in domain_a.iterrows():
        if pd.notna(r["next_field_ref"]):
            parent_map[domain].setdefault(r["next_field_ref"], []).append(
                (r["field_ref"], str(r["answer_value"]))
            )

# -----------------------------
# Session state init
# -----------------------------
for domain in domains:
    for _, q in df_q[df_q["domain"] == domain].iterrows():
        key = f"{domain}__{q['field_ref']}"
        st.session_state.setdefault(key, None)
        st.session_state.setdefault(f"{key}_prev", None)

# -----------------------------
# Reset
# -----------------------------
if st.button("Reset All"):
    for domain in domains:
        for _, q in df_q[df_q["domain"] == domain].iterrows():
            key = f"{domain}__{q['field_ref']}"
            st.session_state[key] = None
            st.session_state[f"{key}_prev"] = None
    st.rerun()

# -----------------------------
# Rule helpers
# -----------------------------
def get_next_fields(domain, field_ref, value):
    return [
        nxt for ans, nxt in child_map.get(domain, {}).get(field_ref, [])
        if str(value) == ans
    ]

def clear_children(domain, field_ref):
    for child in get_next_fields(domain, field_ref, st.session_state.get(f"{domain}__{field_ref}")):
        child_key = f"{domain}__{child}"
        if child_key in st.session_state:
            st.session_state[child_key] = None
        clear_children(domain, child)

def display_question(domain, q, indent=0):
    field_ref = q["field_ref"]
    widget_key = f"{domain}__{field_ref}"

    # Parent gating
    parents = parent_map.get(domain, {}).get(field_ref, [])
    if parents:
        if not any(
            st.session_state.get(f"{domain}__{parent}") == expected
            for parent, expected in parents
        ):
            return

    options = options_map.get(domain, {}).get(field_ref, [])
    label = f"{field_ref} – {q['questions_text']}"

    with st.expander(label, expanded=True):
        if q["answer_type"] == "radio":
            st.radio("Answer:", options, key=widget_key, label_visibility="collapsed")
        elif q["answer_type"] == "select":
            st.selectbox("Answer:", options, key=widget_key, label_visibility="collapsed")
        elif q["answer_type"] == "free_text":
            st.text_input("Answer:", key=widget_key, label_visibility="collapsed")
        elif q["answer_type"] == "numeric":
            st.number_input("Answer:", key=widget_key, label_visibility="collapsed")
        elif q["answer_type"] == "date":
            st.date_input("Answer:", key=widget_key, label_visibility="collapsed")

    prev_key = f"{widget_key}_prev"
    current_val = st.session_state.get(widget_key)

    # Clear children if value changed
    if st.session_state[prev_key] != current_val:
        clear_children(domain, field_ref)
        st.session_state[prev_key] = current_val

    # Display child questions automatically
    for child in get_next_fields(domain, field_ref, current_val):
        child_rows = df_q[
            (df_q["domain"] == domain) &
            (df_q["field_ref"] == child)
        ]
        if child_rows.empty:
            st.warning(f"Rule points to missing question: {child} (domain: {domain})")
            continue
        display_question(domain, child_rows.iloc[0], indent + 1)

# -----------------------------
# Rule tree (SVG/PNG export only)
# -----------------------------
def build_rule_tree_svg(domain):
    dot = Digraph(format="svg")
    dot.attr(rankdir="TB", dpi="150")  # Left-to-right layout
    dot.node_attr.update(
        shape="box",
        style="rounded,filled",
        fillcolor="lightyellow",
        width="2",
        height="0.7",
        fontsize="10",
        margin="0.1"
    )

    def wrap_text(text, width=25):
        import textwrap
        return "\n".join(textwrap.wrap(str(text), width))

    dq = df_q[df_q["domain"] == domain]
    da = df_a[df_a["domain"] == domain]

    for _, q in dq.iterrows():
        dot.node(q["field_ref"], f"{q['field_ref']}\n{wrap_text(q['questions_text'], 25)}")

    for _, r in da.iterrows():
        if pd.notna(r["next_field_ref"]):
            dot.edge(r["field_ref"], r["next_field_ref"], label=str(r["answer_value"]))

    return dot

# -----------------------------
# Audit helpers
# -----------------------------
def find_top_level(domain):
    q = set(df_q[df_q["domain"] == domain]["field_ref"])
    children = set(df_a[df_a["domain"] == domain]["next_field_ref"].dropna())
    return sorted(q - children)

def find_missing_targets(domain):
    q = set(df_q[df_q["domain"] == domain]["field_ref"])
    targets = set(df_a[df_a["domain"] == domain]["next_field_ref"].dropna())
    return sorted(targets - q)

def find_ambiguous_rules(domain):
    issues = []
    da = df_a[df_a["domain"] == domain]
    grouped = da.groupby(["field_ref", "answer_value"])
    for (field, answer), g in grouped:
        if g["next_field_ref"].nunique() > 1:
            issues.append((field, answer))
    return issues

# -----------------------------
# Tabs
# -----------------------------
DOMAIN_LABELS = {
    "safeguarding": "Safeguarding",
    "police": "Police",
    "fire": "Fire"
}

active_domains = [d for d in DOMAIN_LABELS if d in domains]

tabs = st.tabs(
    [DOMAIN_LABELS[d] for d in active_domains] + ["Rule Trees", "Rule Audit"]
)

# -----------------------------
# Question tabs
# -----------------------------
for tab, domain in zip(tabs[:len(active_domains)], active_domains):
    with tab:
        st.header(DOMAIN_LABELS[domain])
        domain_q = df_q[df_q["domain"] == domain]
        domain_a = df_a[df_a["domain"] == domain]

        # Top-level questions (not children)
        top = domain_q[~domain_q["field_ref"].isin(domain_a["next_field_ref"].dropna())]

        for _, q in top.iterrows():
            display_question(domain, q)

# -----------------------------
# Rule trees tab (export only)
# -----------------------------
with tabs[len(active_domains)]:
    st.header("Rule Trees Export")

    for domain in active_domains:
        st.subheader(DOMAIN_LABELS[domain])

        tree = build_rule_tree_svg(domain)

        # Export SVG
        svg_bytes = tree.pipe(format="svg")
        st.download_button(
            label=f"Download {DOMAIN_LABELS[domain]} tree (SVG)",
            data=svg_bytes,
            file_name=f"{domain}_rule_tree.svg",
            mime="image/svg+xml"
        )

        # Export PNG
        png_bytes = tree.pipe(format="png")
        st.download_button(
            label=f"Download {DOMAIN_LABELS[domain]} tree (PNG)",
            data=png_bytes,
            file_name=f"{domain}_rule_tree.png",
            mime="image/png"
        )

# -----------------------------
# Rule audit tab
# -----------------------------
with tabs[len(active_domains) + 1]:
    st.header("Rule Audit")

    for domain in active_domains:
        st.subheader(DOMAIN_LABELS[domain])

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Top-level questions**")
            st.write(find_top_level(domain))

        with col2:
            st.markdown("**Missing rule targets**")
            missing = find_missing_targets(domain)
            st.write(missing if missing else "None ✅")

        with col3:
            st.markdown("**Ambiguous rules**")
            amb = find_ambiguous_rules(domain)
            st.write(amb if amb else "None ✅")

        with st.expander("Raw rules (questions)"):
            st.dataframe(df_q[df_q["domain"] == domain])

        with st.expander("Raw rules (answers)"):
            st.dataframe(df_a[df_a["domain"] == domain])

        st.divider()

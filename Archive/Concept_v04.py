# ===============================================
# Streamlit Safeguarding Proof-of-Concept App
# ===============================================

import streamlit as st
import pandas as pd
import os
import time
from graphviz import Digraph

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(layout="wide", page_title="Safeguarding Form")

st.title("Safeguarding Referral Proof of Concept – Demo")
st.caption("Rules-driven prototype generated from specification spreadsheet - v0.1")
st.divider()

# -----------------------------
# Load Excel (cached for speed)
# -----------------------------
EXCEL_FILE = "/home/king/projects/Safeguarding_POC/Data/Safeguarding specification v0.1 2025_12_19_PK.xlsx"

if not os.path.exists(EXCEL_FILE):
    st.error(f"File not found: {EXCEL_FILE}")
    st.stop()

@st.cache_data
def load_excel(file_path):
    df_q = pd.read_excel(file_path, sheet_name="Safeguarding_Q")
    df_a = pd.read_excel(file_path, sheet_name="Safeguarding_A")
    # normalize domains
    df_q["domain"] = df_q["domain"].str.lower().str.strip()
    df_a["domain"] = df_a["domain"].str.lower().str.strip()
    return df_q, df_a

df_q, df_a = load_excel(EXCEL_FILE)

# -----------------------------
# Precompute dictionaries for efficiency
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
    
    # Options for each question
    options_map[domain] = {
        q['field_ref']: [o.strip() for o in str(q.get("answer_options","")).split(";") if o.strip()]
        for _, q in domain_q.iterrows()
    }

    # Child map
    for _, row in domain_a.iterrows():
        key = row["field_ref"]
        child_map[domain].setdefault(key, []).append((str(row["answer_value"]), row["next_field_ref"]))

    # Parent map
    for _, row in domain_a.iterrows():
        child = row["next_field_ref"]
        if pd.notna(child):
            parent_map[domain].setdefault(child, []).append((row["field_ref"], str(row["answer_value"])))

# -----------------------------
# Initialize session state
# -----------------------------
for domain in domains:
    domain_q = df_q[df_q["domain"] == domain]
    for _, row in domain_q.iterrows():
        widget_key = f"{domain}__{row['field_ref']}"
        st.session_state.setdefault(widget_key, None)
        st.session_state.setdefault(f"{widget_key}_prev", None)

# -----------------------------
# Reset button
# -----------------------------
if st.button("Reset All"):
    for domain in domains:
        domain_q = df_q[df_q["domain"] == domain]
        for _, row in domain_q.iterrows():
            widget_key = f"{domain}__{row['field_ref']}"
            st.session_state[widget_key] = None
            st.session_state[f"{widget_key}_prev"] = None
    st.experimental_rerun()

# -----------------------------
# Helper functions
# -----------------------------
def get_next_fields(domain, field_ref, value):
    return [next_field for ans_val, next_field in child_map.get(domain, {}).get(field_ref, []) if str(value) == ans_val]

def clear_children(domain, field_ref):
    for child in get_next_fields(domain, field_ref, st.session_state.get(f"{domain}__{field_ref}")):
        child_key = f"{domain}__{child}"
        if child_key in st.session_state:
            st.session_state[child_key] = None
        clear_children(domain, child)

def display_question(domain, q, indent_level=0):
    field_ref = q["field_ref"]
    widget_key = f"{domain}__{field_ref}"
    
    # Check parents
    for parent_field, expected_val in parent_map.get(domain, {}).get(field_ref, []):
        parent_key = f"{domain}__{parent_field}"
        if st.session_state.get(parent_key) != expected_val:
            return

    options = options_map.get(domain, {}).get(field_ref, [])

    # Use expander for lazy rendering
    with st.expander(q['questions_text'], expanded=True):
        col_q, col_a, col_ref = st.columns([3,3,1])

        with col_q:
            st.markdown("&nbsp;" * 4 * indent_level + f"**{q['questions_text']}**", unsafe_allow_html=True)

        with col_a:
            if q["answer_type"] == "radio":
                st.radio("", options, key=widget_key)
            elif q["answer_type"] == "select":
                st.selectbox("", options, key=widget_key)
            elif q["answer_type"] == "free_text":
                st.text_input("", key=widget_key)
            elif q["answer_type"] == "numeric":
                st.number_input("", key=widget_key)
            elif q["answer_type"] == "date":
                st.date_input("", key=widget_key)

        with col_ref:
            st.caption(field_ref)

    # Clear child answers if value changed
    prev_key = f"{widget_key}_prev"
    if st.session_state[prev_key] != st.session_state.get(widget_key):
        clear_children(domain, field_ref)
        st.session_state[prev_key] = st.session_state.get(widget_key)

    # Display children
    for child_field in get_next_fields(domain, field_ref, st.session_state.get(widget_key)):
        child_q = df_q[df_q["field_ref"] == child_field].iloc[0]
        display_question(domain, child_q, indent_level + 1)

# -----------------------------
# Build rule tree for a domain
# -----------------------------
def build_rule_tree(domain):
    dot = Digraph()
    dot.attr(rankdir="TB", size="15,20", dpi="150", fontsize="10")
    dot.node_attr.update(shape="box", style="rounded,filled", fillcolor="lightyellow")

    domain_q = df_q[df_q["domain"] == domain]
    domain_a = df_a[df_a["domain"] == domain]

    for _, q in domain_q.iterrows():
        label = f"{q['field_ref']}\n{q['questions_text'][:50]}"
        dot.node(q['field_ref'], label=label)

    for _, r in domain_a.iterrows():
        if pd.notna(r["next_field_ref"]):
            dot.edge(r['field_ref'], r['next_field_ref'], label=str(r['answer_value']))

    return dot

# -----------------------------
# Tabs for domains + rule tree
# -----------------------------
DOMAIN_LABELS = { "safeguarding":"Safeguarding", "police":"Police", "fire":"Fire" }
active_domains = [d for d in DOMAIN_LABELS if d in df_q["domain"].unique()]
tabs = st.tabs([DOMAIN_LABELS[d] for d in active_domains] + ["Rule Trees"])

for tab, domain in zip(tabs[:-1], active_domains):
    with tab:
        st.header(DOMAIN_LABELS[domain])
        domain_q = df_q[df_q["domain"] == domain]
        domain_a = df_a[df_a["domain"] == domain]

        top_questions = domain_q[~domain_q["field_ref"].isin(domain_a["next_field_ref"].dropna())]

        with st.spinner(f"Updating {DOMAIN_LABELS[domain]} questions..."):
            for _, q in top_questions.iterrows():
                display_question(domain, q)

# Rule tree tab
with tabs[-1]:
    st.header("Rule Trees (Vertical)")
    rule_tabs = st.tabs([DOMAIN_LABELS[d] for d in active_domains])

    for rt_tab, domain in zip(rule_tabs, active_domains):
        with rt_tab:
            st.subheader(f"{DOMAIN_LABELS[domain]} Rule Tree")
            st.graphviz_chart(build_rule_tree(domain), use_container_width=True)

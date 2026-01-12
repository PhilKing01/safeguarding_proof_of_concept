import streamlit as st
import pandas as pd
import os
import time
from graphviz import Digraph



# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    layout="wide",
    page_title="Safeguarding Referral Proof of Concept"
)

st.title("Safeguarding Referral Proof of Concept – Demo")
st.caption("Rules-driven prototype generated from specification spreadsheet – v0.1")

st.divider()

# -----------------------------
# Load Excel
# -----------------------------
EXCEL_FILE = (
    "/home/king/projects/Safeguarding_POC/Data/"
    "Safeguarding specification v0.1 2025_12_19_PK.xlsx"
)

if not os.path.exists(EXCEL_FILE):
    st.error(f"File not found: {EXCEL_FILE}")
    st.stop()

df_q = pd.read_excel(EXCEL_FILE, sheet_name="Safeguarding_Q")
df_a = pd.read_excel(EXCEL_FILE, sheet_name="Safeguarding_A")

# Normalise domains
df_q["domain"] = df_q["domain"].str.lower().str.strip()
df_a["domain"] = df_a["domain"].str.lower().str.strip()

# -----------------------------
# Initialise session state
# -----------------------------
for _, row in df_q.iterrows():
    widget_key = f"{row['domain']}__{row['field_ref']}"
    st.session_state.setdefault(widget_key, None)
    st.session_state.setdefault(f"{widget_key}_prev", None)

# -----------------------------
# Reset button
# -----------------------------
if st.button("Reset all"):
    for _, row in df_q.iterrows():
        key = f"{row['domain']}__{row['field_ref']}"
        st.session_state[key] = None
        st.session_state[f"{key}_prev"] = None
    st.rerun()

# -----------------------------
# Helper functions
# -----------------------------
def get_next_fields(domain, field_ref, value):
    return (
        df_a[
            (df_a["domain"] == domain)
            & (df_a["field_ref"] == field_ref)
            & (df_a["answer_value"] == str(value))
        ]["next_field_ref"]
        .dropna()
        .tolist()
    )


def clear_children(domain, field_ref):
    children = df_a[
        (df_a["domain"] == domain)
        & (df_a["field_ref"] == field_ref)
    ]["next_field_ref"].dropna().tolist()

    for child in children:
        child_key = f"{domain}__{child}"
        if child_key in st.session_state:
            st.session_state[child_key] = None
        clear_children(domain, child)


def display_question(domain, q, indent=0):
    field_ref = q["field_ref"]
    widget_key = f"{domain}__{field_ref}"

    # Check parent rules
    parents = df_a[
        (df_a["domain"] == domain)
        & (df_a["next_field_ref"] == field_ref)
    ]

    for _, pr in parents.iterrows():
        parent_key = f"{domain}__{pr['field_ref']}"
        if st.session_state.get(parent_key) != pr["answer_value"]:
            return

    # Animated reveal
    with st.container():
        time.sleep(0.05)

        col_q, col_a, col_ref = st.columns([3, 3, 1])

        with col_q:
            st.markdown(
                "&nbsp;" * 4 * indent + f"**{q['questions_text']}**",
                unsafe_allow_html=True
            )

        with col_a:
            options = []
            if q["answer_type"] in ("radio", "select"):
                options = [
                    o.strip()
                    for o in str(q.get("answer_options", "")).split(";")
                    if o.strip()
                ]

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

    # Detect change → clear children
    prev_key = f"{widget_key}_prev"
    if st.session_state[prev_key] != st.session_state.get(widget_key):
        clear_children(domain, field_ref)
        st.session_state[prev_key] = st.session_state.get(widget_key)

    # Recurse to children
    for child in get_next_fields(domain, field_ref, st.session_state.get(widget_key)):
        child_q = df_q[
            (df_q["domain"] == domain)
            & (df_q["field_ref"] == child)
        ].iloc[0]
        display_question(domain, child_q, indent + 1)

def build_rule_tree(domain):
    dot = Digraph()
    dot.attr(rankdir="TB", size="15,20", dpi="150", fontsize="10")
    dot.node_attr.update(shape="box", style="rounded,filled", fillcolor="lightyellow")

    q_domain = df_q[df_q["domain"] == domain]
    a_domain = df_a[df_a["domain"] == domain]

    for _, q in q_domain.iterrows():
        label = f"{q['field_ref']}\n{q['questions_text'][:50]}"
        dot.node(q["field_ref"], label=label)

    for _, r in a_domain.iterrows():
        if pd.notna(r["next_field_ref"]):
            dot.edge(r["field_ref"], r["next_field_ref"], label=str(r["answer_value"]))

    return dot



# -----------------------------
# Tabs by domain
# -----------------------------
DOMAIN_LABELS = {
    "safeguarding": "Safeguarding",
    "police": "Police",
    "fire": "Fire"
}

domains = [d for d in DOMAIN_LABELS if d in df_q["domain"].unique()]
tabs = st.tabs(
    [DOMAIN_LABELS[d] for d in domains] + ["Rule Tree"]
)


for tab, domain in zip(tabs, domains):
    with tab:
        st.header(DOMAIN_LABELS[domain])

        domain_q = df_q[df_q["domain"] == domain]
        domain_a = df_a[df_a["domain"] == domain]

        # Progress indicator
        answered = sum(
            st.session_state.get(f"{domain}__{r}") is not None
            for r in domain_q["field_ref"]
        )
        total = len(domain_q)

        progress = answered / total if total else 0

        st.progress(progress)
        st.caption(f"{answered} of {total} questions answered")

        with st.spinner(f"Updating {DOMAIN_LABELS[domain]} questions…"):
            top_questions = domain_q[
                ~domain_q["field_ref"].isin(
                    domain_a["next_field_ref"].dropna()
                )
            ]

            for _, q in top_questions.iterrows():
                display_question(domain, q)

with tabs[-1]:
    st.header("Rule Trees")

    rule_tabs = st.tabs([DOMAIN_LABELS[d] for d in domains])

    for rt_tab, domain in zip(rule_tabs, domains):
        with rt_tab:
            st.subheader(f"{DOMAIN_LABELS[domain]} Rule Tree")
            st.graphviz_chart(build_rule_tree(domain))



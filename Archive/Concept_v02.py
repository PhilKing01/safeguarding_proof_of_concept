import streamlit as st
import pandas as pd
import os

st.set_page_config(layout="wide", page_title="Safeguarding Form")

# -----------------------------
# Load Excel
# -----------------------------
excel_file = "/home/king/projects/Safeguarding_POC/Data/Safeguarding specification v0.1 2025_12_19_PK.xlsx"
if not os.path.exists(excel_file):
    st.error(f"File not found: {excel_file}")
    st.stop()

try:
    df_q = pd.read_excel(excel_file, sheet_name="Safeguarding_Q")
    df_a = pd.read_excel(excel_file, sheet_name="Safeguarding_A")
except Exception as e:
    st.error(f"Error loading Excel: {e}")
    st.stop()

# -----------------------------
# Initialize session state for answers
# -----------------------------
for key in df_q['field_ref']:
    if key not in st.session_state:
        st.session_state[key] = None
    if key + "_prev" not in st.session_state:
        st.session_state[key + "_prev"] = None

# -----------------------------
# Nuclear Reset
# -----------------------------
if st.button("Reset All"):
    for key in df_q['field_ref']:
        st.session_state[key] = None
        st.session_state[key + "_prev"] = None
    st.experimental_rerun()  # standard rerun to refresh all widgets

# -----------------------------
# Helper functions
# -----------------------------
def get_next_fields(field_ref, value):
    """Return the next_field_ref(s) for a given answer value"""
    matches = df_a[(df_a['field_ref'] == field_ref) & (df_a['answer_value'] == str(value))]
    return matches['next_field_ref'].dropna().tolist()

def clear_children(field_ref):
    """Recursively clear answers of child questions"""
    children = df_a[df_a['field_ref'] == field_ref]['next_field_ref'].dropna().tolist()
    for child in children:
        if child in st.session_state:
            st.session_state[child] = None
        clear_children(child)

def display_question(q, indent_level=0):
    """Display a single question with proper widget and indentation"""
    key = q['field_ref']
    
    # Check if question should be shown
    parent_rows = df_a[df_a['next_field_ref'] == key]
    show_question = True
    for _, pr in parent_rows.iterrows():
        parent_val = st.session_state.get(pr['field_ref'])
        if parent_val != pr['answer_value']:
            show_question = False
    if not show_question:
        return

    # Prepare options
    init_val = st.session_state.get(key)
    options = []
    if q['answer_type'] in ["radio", "select"]:
        raw_options = str(q.get('answer_options','')).split(";")
        options = [o.replace("\n","").replace("\r","").strip() for o in raw_options if o.strip()]

    selected_index = options.index(init_val) if init_val in options else 0 if options else 0

    # Display in 3 columns with indentation
    col_q, col_a, col_next = st.columns([3,3,1])
    with col_q:
        st.markdown("&nbsp;" * 4 * indent_level + f"**{q['questions_text']}**", unsafe_allow_html=True)
    with col_a:
        if q['answer_type'] == "radio":
            st.radio("", options=options, index=selected_index, key=key)
        elif q['answer_type'] == "select":
            st.selectbox("", options=options, index=selected_index, key=key)
        elif q['answer_type'] == "free_text":
            st.text_input("", value=init_val or "", key=key)
        elif q['answer_type'] == "numeric":
            st.number_input("", value=float(init_val) if init_val else 0.0, key=key)
        elif q['answer_type'] == "date":
            st.date_input("", value=init_val if init_val else pd.Timestamp.today(), key=key)
    with col_next:
        st.markdown(f"*{key}*", unsafe_allow_html=True)

    # Clear child answers if changed
    if st.session_state[key + "_prev"] != st.session_state[key]:
        clear_children(key)
        st.session_state[key + "_prev"] = st.session_state[key]

    # Display child questions recursively
    next_fields = get_next_fields(key, st.session_state[key])
    for child_key in next_fields:
        child_q = df_q[df_q['field_ref'] == child_key].iloc[0]
        display_question(child_q, indent_level=indent_level+1)

# -----------------------------
# Tabs for multiple domains
# -----------------------------
tabs = st.tabs(["Safeguarding", "Fire", "Police & Prevent"])

# Currently only Safeguarding sheet is implemented
with tabs[0]:
    st.header("Safeguarding Form")
    # Display top-level questions (no parent)
    top_questions = df_q[~df_q['field_ref'].isin(df_a['next_field_ref'].dropna())]
    for _, q in top_questions.iterrows():
        display_question(q)

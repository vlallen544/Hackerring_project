import streamlit as st

st.set_page_config(page_title="VidyaPath", page_icon="V", layout="wide")

st.title("VidyaPath")
role = st.sidebar.radio("Workspace", ["Faculty", "Student"])

if role == "Faculty":
    st.header("Faculty workspace")
    sources_tab, trust_tab = st.tabs(["Sources", "Trust Board"])
    with sources_tab:
        st.subheader("Sources")
        st.info("No sources added yet.")
    with trust_tab:
        st.subheader("Trust Board")
        st.info("Trust metrics will appear here.")
else:
    st.header("Student workspace")
    viva_tab, lesson_tab = st.tabs(["Viva", "My Lesson"])
    with viva_tab:
        st.subheader("Viva")
        st.info("Your viva practice will appear here.")
    with lesson_tab:
        st.subheader("My Lesson")
        st.info("Your lesson will appear here.")
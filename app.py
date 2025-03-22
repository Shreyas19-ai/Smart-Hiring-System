import streamlit as st
from login_ui import LoginUI
from hr_ui import HRUI
from candidate_ui import CandidateUI
from database import initialize_db

initialize_db()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["progress"] = {}

if not st.session_state["logged_in"]:
    login_ui = LoginUI(st.session_state)
    login_ui.render()
elif st.session_state["user_role"] == "hr":
    hr_ui = HRUI(st.session_state)
    hr_ui.render()
else:
    candidate_ui = CandidateUI(st.session_state)
    candidate_ui.render()
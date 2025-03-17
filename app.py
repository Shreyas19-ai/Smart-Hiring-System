import streamlit as st
from streamlit_ui import render_login, render_main_app, render_hr_app
from database import initialize_db

initialize_db()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["progress"] = {}

if not st.session_state["logged_in"]:
    render_login()
elif st.session_state["user_role"] == "hr":
    render_hr_app()
else:
    render_main_app()



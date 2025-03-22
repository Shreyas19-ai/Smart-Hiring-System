import streamlit as st
import os

from database import initialize_db
from pdf_processor import input_pdf_text
from config import job_roles

class CandidateUI:
    def __init__(self, session_state):
        self.session_state = session_state

    def render(self):
        st.sidebar.title(f"Welcome, {self.session_state['username']} 👋")
        if st.sidebar.button("Logout"):
            self.session_state["logged_in"] = False
            self.session_state["username"] = None
            st.rerun()

        self.clear_session_state()

        st.title("Apply for a Job")
        selected_role = st.selectbox("Select a Job Role:", list(job_roles.keys()))

        conn, cursor = initialize_db()
        cursor.execute("SELECT job_role FROM resumes WHERE username = ? AND job_role = ?", (self.session_state["username"], selected_role))
        applied_roles = [role[0] for role in cursor.fetchall()]
        conn.close()

        if applied_roles:
            st.warning(f"You have already applied for the '{selected_role}' role.")
            return

        uploaded_file = st.file_uploader("📂 Upload Your Resume (PDF)", type="pdf")

        if uploaded_file:
            resume_text = input_pdf_text(uploaded_file)
            st.success("✅ Resume Uploaded Successfully")

            file_name = f"{self.session_state['username']}_{selected_role}.pdf"
            file_path = os.path.join("resumes", file_name)
            os.makedirs("resumes", exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            conn, cursor = initialize_db()
            cursor.execute(
                "INSERT INTO resumes (username, resume_text, job_role, resume_path) VALUES (?, ?, ?, ?)",
                (self.session_state["username"], resume_text, selected_role, file_path),
            )

            cursor.execute(
                "UPDATE resumes SET evaluation = ?, match_response = ?, roadmap = ? WHERE id = (SELECT MAX(id) FROM resumes WHERE username = ? AND job_role = ?)",
                (
                    None,
                    None,
                    None,
                    self.session_state["username"],
                    selected_role,
                ),
            )

            print("render_main_app - Database update executed")
            conn.commit()
            conn.close()

    def clear_session_state(self):
        if "evaluation" in self.session_state:
            del self.session_state["evaluation"]
        if "match_response" in self.session_state:
            del self.session_state["match_response"]
        if "roadmap" in self.session_state:
            del self.session_state["roadmap"]
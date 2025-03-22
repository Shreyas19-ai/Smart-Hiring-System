import streamlit as st
import pandas as pd
import io
import os
import re
import base64

from database import initialize_db
from pdf_processor import input_pdf_text
from ai_response import get_gemini_response, parse_roadmap, process_bulk_resumes
from config import job_roles

class HRUI:
    def __init__(self, session_state):
        self.session_state = session_state

    def render(self):
        self.render_sidebar()
        self.render_dashboard_title()
        self.render_job_role_selection()
        self.render_actions()

    def render_sidebar(self):
        st.sidebar.title(f"Welcome, {self.session_state['username']} 👋")
        if st.sidebar.button("Logout"):
            self.session_state["logged_in"] = False
            self.session_state["username"] = None
            st.rerun()

    def render_dashboard_title(self):
        st.title("HR Dashboard")

    def render_job_role_selection(self):
        job_roles_list = list(job_roles.keys())
        self.selected_job_role = st.selectbox("Select Job Role", job_roles_list)

    def render_actions(self):
        action = st.radio("Select Action", ["Screen Resumes", "View Analysis"])

        if action == "Screen Resumes":
            self.handle_screen_resumes()
        elif action == "View Analysis":
            self.handle_view_analysis()

    def handle_screen_resumes(self):
        if st.button("Start Screening"):
            self.clear_session_state()
            with st.spinner("Processing Resumes..."):
                ranked_resumes = process_bulk_resumes(self.selected_job_role) # use the imported function

                if not ranked_resumes:
                    st.warning(f"No candidates have applied for the '{self.selected_job_role}' job role yet.")
                    return

                new_ranked_resumes = []
                for i, result in enumerate(ranked_resumes):
                    result["Index"] = i + 1
                    result["Email"] = f'<a href="mailto:{result["Email"]}">{result["Email"]}</a>'

                    if result["Resume Path"]:
                        absolute_path = os.path.abspath(result["Resume Path"])
                        if os.path.exists(absolute_path):
                            try:
                                with open(absolute_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                result["Resume"] = f'<a href="data:application/octet-stream;base64,{b64}" download="resume_{result["Name"]}.pdf">📝</a>'
                            except FileNotFoundError:
                                result["Resume"] = "File not found"
                            except Exception as e:
                                result["Resume"] = f"Error: {e}"
                        else:
                            result["Resume"] = "File not found"
                    else:
                        result["Resume"] = "Resume path not available"

                    new_ranked_resumes.append(result)

                st.markdown("---")
                df = pd.DataFrame(new_ranked_resumes)
                df = df[["Index", "Name", "Email", "Score", "Resume"]]
                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

    def handle_view_analysis(self):
        self.render_candidate_selection()
        self.render_analysis_display()

    def render_candidate_selection(self):
        if self.selected_job_role:
            conn, cursor = initialize_db()
            cursor.execute("SELECT username FROM resumes WHERE job_role = ?", (self.selected_job_role,))
            usernames = [row[0] for row in cursor.fetchall()]
            conn.close()

            if usernames:
                self.selected_username = st.selectbox("Select Candidate", usernames)
            else:
                self.selected_username = None
                st.warning(f"No candidates have applied for the '{self.selected_job_role}' role yet.")
        else:
            self.selected_username = None

    def render_analysis_display(self):
        if self.selected_username:
            conn, cursor = initialize_db()
            cursor.execute("SELECT evaluation, match_response, roadmap FROM resumes WHERE username = ? AND job_role = ?", (self.selected_username, self.selected_job_role))
            result = cursor.fetchone()
            conn.close()

            if result:
                self.session_state["evaluation"], self.session_state["match_response"], self.session_state["roadmap"] = result

                if "roadmap" in self.session_state and self.session_state["roadmap"] is not None:
                    roadmap_parsed = parse_roadmap(self.session_state["roadmap"])
                    self.session_state["free_courses"] = roadmap_parsed["free_courses"]
                    self.session_state["paid_courses"] = roadmap_parsed["paid_courses"]
                else:
                    roadmap_parsed = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

                self.display_analysis_tabs(roadmap_parsed)
            else:
                st.error("Could not retrieve analysis.")


    def display_analysis_tabs(self, roadmap_parsed):
        tab1, tab2, tab3, tab4 = st.tabs(["📋 User Persona", "📊 Compatibility Score", "📚 Learning Pathway", "📈 Progress Tracking"])

        with tab1:
            self.display_persona(tab1)
        with tab2:
            self.display_compatibility(tab2)
        with tab3:
            self.display_learning_pathway(tab3, roadmap_parsed)
        with tab4:
            self.display_progress_tracking(tab4, roadmap_parsed)

    def clear_session_state(self):
        if "evaluation" in self.session_state:
            del self.session_state["evaluation"]
        if "match_response" in self.session_state:
            del self.session_state["match_response"]
        if "roadmap" in self.session_state:
            del self.session_state["roadmap"]
        if "free_courses" in self.session_state:
            del self.session_state["free_courses"]
        if "paid_courses" in self.session_state:
            del self.session_state["paid_courses"]

    def display_persona(self, tab):
        st.subheader("📝 User Persona")
        if "evaluation" in st.session_state and st.session_state["evaluation"] is not None:
            try:
                # Extract the table from the evaluation response
                table_start = st.session_state["evaluation"].find("| Category |")
                if table_start != -1:
                    table_markdown = st.session_state["evaluation"][table_start:]
                    # Convert Markdown to CSV-like string for pandas
                    import io
                    table_csv = io.StringIO(table_markdown.replace("| ", "|").replace(" |", "|"))

                    df = pd.read_csv(table_csv, sep='|', index_col=False)

                    # Remove unnecessary columns
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                    df = df.loc[:, ~df.columns.str.contains('Unnamed')]

                    df.dropna(how='all', inplace=True)
                    if df.iloc[-1].all() == '-':
                        df = df.iloc[:-1]

                    # Display the table HTML
                    st.markdown(
                        df.to_html(index=False, escape=False),
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("Table not found in Gemini's response.")
                    st.write(st.session_state["evaluation"])

            except Exception as e:
                st.error(f"Could not display User Persona in table format: {e}")
                st.write(st.session_state["evaluation"])

    def display_compatibility(self, tab):
        st.subheader("📊 Compatibility Score")
        if "match_response" in st.session_state and st.session_state["match_response"] is not None:
            try:
                # Extract the table from the match_response
                table_start = st.session_state["match_response"].find("| Category |")
                if table_start != -1:
                    table_markdown = st.session_state["match_response"][table_start:]
                    # Convert Markdown to CSV-like string for pandas
                    import io
                    table_csv = io.StringIO(table_markdown.replace("| ", "|").replace(" |", "|"))

                    df = pd.read_csv(table_csv, sep='|', index_col=False)

                    # Remove unnecessary columns
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                    df = df.loc[:, ~df.columns.str.contains('Unnamed')]

                    df.dropna(how='all', inplace=True)
                    if df.iloc[-1].all() == '-':
                        df = df.iloc[:-1]

                    # Display the table HTML
                    st.markdown(
                        df.to_html(index=False, escape=False),
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("Table not found in Gemini's response.")
                    st.write(st.session_state["match_response"])

            except Exception as e:
                st.error(f"Could not display Compatibility Score in table format: {e}")
                st.write(st.session_state["match_response"])

    def display_learning_pathway(self, tab, roadmap_parsed):
        st.subheader("📚 Learning Pathway")
        # Collapsible Section: Missing Skills
        with st.expander("🔍 Missing Skills"):
            if roadmap_parsed["missing_skills"]:
                st.write("Here are the key skills you need to focus on:")
                for skill in roadmap_parsed["missing_skills"]:
                    st.write(f"- {skill}")
            else:
                st.warning("No missing skills identified.")

        # Collapsible Section: Step-by-Step Roadmap
        with st.expander("🗺️ Step-by-Step Learning Roadmap"):
            if roadmap_parsed["roadmap_steps"]:
                st.write("Follow this structured plan to upskill effectively:")
                for step in roadmap_parsed["roadmap_steps"]:
                    st.write(f"- {step}")
            else:
                st.warning("No roadmap steps found.")

    def display_progress_tracking(self, tab, roadmap_parsed):
        with st.expander("🎓 Free Course Links"):
            if roadmap_parsed["free_courses"]:
                st.write("Here are some free resources to get started:")
                for name, link in roadmap_parsed["free_courses"]:
                    st.markdown(f"- [{name}]({link})")
            else:
                st.warning("No free courses found.")

        # Collapsible Section: Paid Courses
        with st.expander("💳 Paid Course Links"):
            if roadmap_parsed["paid_courses"]:
                st.write("Here are some paid resources for deeper learning:")
                for name, link in roadmap_parsed["paid_courses"]:
                    st.markdown(f"- [{name}]({link})")
            else:
                st.warning("No paid courses found.")
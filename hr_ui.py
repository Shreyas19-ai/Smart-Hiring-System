import streamlit as st
import pandas as pd
import io
import os
import re
import base64

from database import initialize_db, get_candidate_profile, get_resume_analysis, get_application_resumes
from utils import calculate_similarity_score
from pdf_processor import input_pdf_text
from ai_response import  parse_roadmap
from candidate_ui import CandidateUI 

ci = CandidateUI(st.session_state)

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
        conn, cursor = initialize_db()
        # Fetch job roles posted by the current HR
        cursor.execute("SELECT job_role FROM job_postings WHERE posted_by = ?", (self.session_state["user_id"],))
        job_roles_list = [row[0] for row in cursor.fetchall()]
        conn.close()

        if job_roles_list:
            self.selected_job_role = st.selectbox("Select Job Role", job_roles_list)
        else:
            st.warning("You have not posted any job openings yet.")
            self.selected_job_role = None

    def render_actions(self):
        action = st.radio("Select Action", ["Screen Resumes", "View Analysis", "Scan Candidates", "Post Job Openings"])

        if action == "Screen Resumes":
            self.handle_screen_resumes()
        elif action == "View Analysis":
            self.handle_view_analysis()
        elif action == "Scan Candidates":
            self.handle_scan_candidates()
        elif action == "Post Job Openings":
            self.handle_post_job_openings()

    def handle_post_job_openings(self):
        st.subheader("Post a New Job Opening")
        job_role = st.text_input("Job Role")
        job_description = st.text_area("Job Description")

        if st.button("Post Job"):
            if job_role and job_description:
                conn, cursor = initialize_db()

                # Check if the job role already exists
                cursor.execute("SELECT job_id FROM job_postings WHERE job_role = ?", (job_role,))
                job_exists = cursor.fetchone()

                if job_exists:
                    st.warning("Job role already exists.")
                else:
                    # Insert the new job posting
                    cursor.execute("INSERT INTO job_postings (job_role, job_description, posted_by) VALUES (?, ?, ?)", 
                                (job_role, job_description, self.session_state["user_id"]))

                    # Fetch all existing candidates
                    cursor.execute("SELECT user_id, resume_path FROM candidate_profiles")
                    candidates = cursor.fetchall()

                    if candidates:
                        # Calculate similarity scores for all candidates
                        for candidate_id, resume_path in candidates:
                            try:
                                with open(resume_path, "rb") as f:
                                    resume_text = f.read().decode('utf-8', errors='ignore')
                                similarity_score = calculate_similarity_score(resume_text, job_description)
                                cursor.execute("INSERT INTO resumes (candidate_profile_id, job_role, similarity_score) VALUES (?, ?, ?)", 
                                            (candidate_id, job_role, similarity_score))
                            except FileNotFoundError:
                                print(f"Resume file not found for candidate ID {candidate_id}")
                    else:
                        # Mark the job posting as pending for future candidates
                        cursor.execute("INSERT INTO pending_jobs (job_role) VALUES (?)", (job_role,))

                    conn.commit()
                    st.success("Job posted successfully!")
                conn.close()
            else:
                st.warning("Please fill in both the Job Role and Job Description.")


    def handle_scan_candidates(self):
        st.subheader("🔍 Scan Candidates for Job Role")

        if not self.selected_job_role:
            st.warning("Please select a job role first.")
            return

        # Fetch candidates and their stored similarity scores
        conn, cursor = initialize_db()
        cursor.execute('''
            SELECT candidate_profiles.user_id, candidate_profiles.full_name, candidate_profiles.email, resumes.similarity_score, candidate_profiles.resume_path
            FROM resumes
            JOIN candidate_profiles ON resumes.candidate_profile_id = candidate_profiles.user_id
            WHERE resumes.job_role = ?
        ''', (self.selected_job_role,))
        candidates = cursor.fetchall()
        conn.close()

        if not candidates:
            st.info(f"No candidates found for the role '{self.selected_job_role}'.")
            return

        # Hardcoded threshold: 75%
        threshold = 75
        results = []
        candidate_options = {"Select a Candidate": None}  # Add placeholder option
        for candidate in candidates:
            user_id, full_name, email, similarity_score, resume_path = candidate
            if similarity_score is not None and similarity_score >= threshold:  # Apply threshold filter
                results.append({
                    "Name": full_name,
                    "Email": email,
                    "Similarity Score": f"{similarity_score:.2f}%" if similarity_score is not None else "N/A",
                    "Resume Path": resume_path
                })
                candidate_options[f"{full_name} ({email})"] = user_id

        if results:
            st.success(f"Found {len(results)} candidates for the role '{self.selected_job_role}' above the threshold of {threshold}%.")
            df = pd.DataFrame(results)
            df = df[["Name", "Email", "Similarity Score"]]
            st.markdown(df.to_html(index=False, escape=False), unsafe_allow_html=True)
        else:
            st.warning(f"No candidates meet the threshold of {threshold}%.")
            return

        # Dropdown to select a candidate
        selected_candidate = st.selectbox("Select a Candidate to View Persona", list(candidate_options.keys()), index=0)

        # Display persona only if a valid candidate is selected
        if selected_candidate != "Select a Candidate":
            candidate_id = candidate_options[selected_candidate]
            ci.view_persona(candidate_id)

    def handle_screen_resumes(self):
        if st.button("Start Screening"):
            self.clear_session_state()
            with st.spinner("Processing Resumes..."):
                # Fetch candidates who have applied for the selected job role
                conn, cursor = initialize_db()
                cursor.execute('''
                    SELECT candidate_profiles.full_name, candidate_profiles.email, resumes.similarity_score, candidate_profiles.resume_path
                    FROM resumes
                    JOIN candidate_profiles ON resumes.candidate_profile_id = candidate_profiles.user_id
                    WHERE resumes.job_role = ? AND resumes.has_applied = 1
                ''', (self.selected_job_role,))
                ranked_resumes = cursor.fetchall()
                conn.close()

                if not ranked_resumes:
                    st.warning(f"No candidates have applied for the '{self.selected_job_role}' job role yet.")
                    return

                threshold = 75
                new_ranked_resumes = []
                for i, result in enumerate(ranked_resumes):
                    full_name, email, similarity_score, resume_path = result  # Unpack tuple
                    if similarity_score is not None and similarity_score >= threshold:  # Apply threshold filter
                        candidate_data = {
                            "Index": i + 1,
                            "Name": full_name,
                            "Email": f'<a href="mailto:{email}">{email}</a>',
                            "Score": f"{similarity_score:.2f}%" if similarity_score is not None else "N/A",
                        }

                        # Add resume download link if the file exists
                        if resume_path and os.path.exists(resume_path):
                            try:
                                with open(resume_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                candidate_data["Resume"] = f'<a href="data:application/octet-stream;base64,{b64}" download="resume_{full_name}.pdf">📝</a>'
                            except FileNotFoundError:
                                candidate_data["Resume"] = "File not found"
                            except Exception as e:
                                candidate_data["Resume"] = f"Error: {e}"
                        else:
                            candidate_data["Resume"] = "Resume path not available"

                        new_ranked_resumes.append(candidate_data)

                if new_ranked_resumes:
                    st.markdown("---")
                    df = pd.DataFrame(new_ranked_resumes)
                    df = df[["Index", "Name", "Email", "Score", "Resume"]]
                    st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
                else:
                    st.warning("No candidates meet the threshold of {threshold}% .")


    def handle_view_analysis(self):
        self.render_candidate_selection()
        if hasattr(self, 'selected_candidate_id') and self.selected_candidate_id:  # Check if a candidate is selected
            self.render_analysis_display()

    def render_candidate_selection(self):
        if self.selected_job_role:
            conn, cursor = initialize_db()
            # Fetch candidates and their persona (evaluation) for the selected job role
            cursor.execute(
                """
                SELECT DISTINCT candidate_profiles.full_name, resumes.candidate_profile_id, resumes.evaluation
                FROM resumes
                JOIN candidate_profiles ON resumes.candidate_profile_id = candidate_profiles.user_id
                WHERE resumes.job_role = ? AND resumes.has_applied = 1
                """,
                (self.selected_job_role,),
            )
            results = cursor.fetchall()
            conn.close()

            candidate_data = []
            if results:
                for full_name, candidate_profile_id, evaluation in results:  # Unpack all three values
                    if evaluation:
                        name_match = re.search(r"\| Name \| (.+?) \|", evaluation)  # Extract name from evaluation
                        if name_match:
                            candidate_data.append((name_match.group(1).strip(), candidate_profile_id))
                        else:
                            candidate_data.append((full_name, candidate_profile_id))  # Fallback to full_name
                    else:
                        candidate_data.append((full_name, candidate_profile_id))  # Fallback to full_name

            if candidate_data:
                candidate_names, candidate_ids = zip(*candidate_data)
                self.candidate_names = candidate_names
                self.candidate_ids = candidate_ids

                self.selected_candidate_name = st.selectbox(
                    "Select Candidate", candidate_names, index=None, placeholder="Select Candidate"
                )

                if st.button("View Analysis"):
                    if self.selected_candidate_name:
                        self.selected_candidate_id = candidate_ids[candidate_names.index(self.selected_candidate_name)]
                    else:
                        st.warning("Please select a candidate.")
            else:
                st.warning(f"No candidates have applied for the '{self.selected_job_role}' role yet.")
        else:
            self.selected_candidate_id = None
            
    def render_analysis_display(self):
        if self.selected_candidate_id:
            conn, cursor = initialize_db()
            
            # Fetch evaluation (persona) independent of job role
            cursor.execute("SELECT evaluation FROM resumes WHERE candidate_profile_id = ?", (self.selected_candidate_id,))
            persona_result = cursor.fetchone()

            # Fetch match_response and roadmap based on job role
            cursor.execute("SELECT match_response, roadmap FROM resumes WHERE candidate_profile_id = ? AND job_role = ?", (self.selected_candidate_id, self.selected_job_role))
            analysis_result = cursor.fetchone()
            conn.close()

            if persona_result:
                self.session_state["evaluation"] = persona_result[0]  # Persona from resumes table
            else:
                self.session_state["evaluation"] = None

            if analysis_result:
                self.session_state["match_response"], self.session_state["roadmap"] = analysis_result

                if "roadmap" in self.session_state and self.session_state["roadmap"] is not None:
                    roadmap_parsed = parse_roadmap(self.session_state["roadmap"])
                    self.session_state["free_courses"] = roadmap_parsed["free_courses"]
                    self.session_state["paid_courses"] = roadmap_parsed["paid_courses"]
                else:
                    roadmap_parsed = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

                # Corrected call to display_analysis_tabs
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
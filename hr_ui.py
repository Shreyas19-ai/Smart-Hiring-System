import streamlit as st
import pandas as pd
import io
import os
import re
import base64

from database import initialize_db, hire_candidate
from utils import calculate_similarity_score
from pdf_processor import input_pdf_text
from utils import format_name
from ai_response import parse_roadmap, generate_roadmap_for_candidate
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
        action = st.radio("Select Action", ["Screen Resumes", "View Analysis", "Generate Training Roadmaps", "Scan Candidates", "Post Job Openings"])

        if action == "Screen Resumes":
            self.handle_screen_resumes()
        elif action == "View Analysis":
            self.handle_view_analysis()
        elif action == "Generate Training Roadmaps":
            self.handle_generate_training_roadmaps()
        elif action == "Scan Candidates":
            self.handle_scan_candidates()
        elif action == "Post Job Openings":
            self.handle_post_job_openings()

    def handle_generate_training_roadmaps(self):
        st.subheader("🗺️ Generate Training Roadmaps")
        
        # Add a radio button to select between candidates and employees
        target_audience = st.radio("Select Target Audience", ["Employees", "All Candidates"])
        
        # Allow HR to enter job description or select from existing roles
        jd_input_method = st.radio("Input Method", ["Enter New Job Description", "Select Existing Job Role"])
        
        job_description = None
        job_role = None
        
        if jd_input_method == "Enter New Job Description":
            job_role = st.text_input("Job Role Title")
            job_description = st.text_area("Job Description", height=200, 
                                          placeholder="Enter the job description here. Include required skills, responsibilities, and qualifications.")
            if not job_role or not job_description:
                st.warning("Please enter both a job role title and description.")
                return
        else:
            # Use existing job role selection
            conn, cursor = initialize_db()
            cursor.execute("SELECT job_role FROM job_postings WHERE posted_by = ?", (self.session_state["user_id"],))
            job_roles_list = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not job_roles_list:
                st.warning("You have not posted any job openings yet. Please enter a new job description instead.")
                return
                
            job_role = st.selectbox("Select Job Role", job_roles_list)
            
            # Fetch the job description for the selected role
            conn, cursor = initialize_db()
            cursor.execute("SELECT job_description FROM job_postings WHERE job_role = ?", (job_role,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                job_description = result[0]
                st.info(f"Using job description for: {job_role}")
            else:
                st.error("Could not retrieve job description for the selected role.")
                return
        
        # Get candidates based on selection (employees or all candidates)
        conn, cursor = initialize_db()
        if target_audience == "Employees":
            cursor.execute('''
                SELECT user_id, full_name, resume_path 
                FROM candidate_profiles
                WHERE is_employee = 1
            ''')
        else:
            cursor.execute('''
                SELECT user_id, full_name, resume_path 
                FROM candidate_profiles
            ''')
        candidates = cursor.fetchall()
        conn.close()
        
        if not candidates:
            if target_audience == "Employees":
                st.warning("No employees found in the system. Hire candidates first.")
            else:
                st.warning("No candidates found in the system.")
            return
            
        # Button to generate roadmaps for all candidates
        if st.button("Analyze All"):
            with st.spinner(f"Generating training roadmaps for all {target_audience.lower()}..."):
                # Store the generated roadmaps in session state
                if "candidate_roadmaps" not in self.session_state:
                    self.session_state["candidate_roadmaps"] = {}
                    
                for candidate_id, full_name, resume_path in candidates:
                    try:
                        # Check if the resume file exists
                        if not os.path.exists(resume_path):
                            st.warning(f"Resume file not found for {full_name}")
                            continue
                            
                        # Read the resume text
                        with open(resume_path, "rb") as f:
                            resume_text = input_pdf_text(f)
                            
                        # Generate roadmap for this candidate based on the job description
                        roadmap = generate_roadmap_for_candidate(resume_text, job_description)
                        
                        # Parse the roadmap and store it
                        roadmap_parsed = parse_roadmap(roadmap)
                        self.session_state["candidate_roadmaps"][candidate_id] = {
                            "name": full_name,
                            "roadmap": roadmap,
                            "parsed": roadmap_parsed
                        }
                    except Exception as e:
                        st.error(f"Error processing {full_name}'s resume: {str(e)}")
                
                st.success(f"✅ Generated roadmaps for {len(self.session_state['candidate_roadmaps'])} {target_audience.lower()}!")
        
        # Display dropdown to select a candidate if roadmaps have been generated
        if "candidate_roadmaps" in self.session_state and self.session_state["candidate_roadmaps"]:
            candidate_options = {data["name"]: candidate_id for candidate_id, data in self.session_state["candidate_roadmaps"].items()}
            selected_candidate_name = st.selectbox("Select to View Roadmap", list(candidate_options.keys()))
            
            if selected_candidate_name:
                selected_candidate_id = candidate_options[selected_candidate_name]
                roadmap_data = self.session_state["candidate_roadmaps"][selected_candidate_id]
                
                # Get the candidate's persona
                conn, cursor = initialize_db()
                cursor.execute(
                    "SELECT evaluation FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                    (selected_candidate_id, "General")
                )
                persona = cursor.fetchone()
                conn.close()
                
                # Create tabs for roadmap and persona
                tab1, tab2 = st.tabs(["Training Roadmap", "Persona"])
                
                with tab1:
                    # Display the roadmap for the selected candidate
                    self.display_candidate_roadmap(roadmap_data["parsed"])
                
                with tab2:
                    # Display the persona
                    self.display_persona(persona)
            
            # Add notification button
            if st.button("Notify About Roadmaps"):
                with st.spinner("Sending notifications..."):
                    conn, cursor = initialize_db()
                    
                    # Save roadmaps to database for each candidate
                    for candidate_id, data in self.session_state["candidate_roadmaps"].items():
                        # Check if a roadmap entry already exists for this candidate and job role
                        cursor.execute(
                            "SELECT id FROM roadmap_notifications WHERE candidate_id = ? AND job_role = ?",
                            (candidate_id, job_role)
                        )
                        existing_entry = cursor.fetchone()
                        
                        roadmap_json = str(data["roadmap"])
                        
                        if existing_entry:
                            # Update existing entry
                            cursor.execute(
                                "UPDATE roadmap_notifications SET roadmap = ?, notification_date = CURRENT_TIMESTAMP, is_read = 0 WHERE id = ?",
                                (roadmap_json, existing_entry[0])
                            )
                        else:
                            # Create new entry
                            cursor.execute(
                                "INSERT INTO roadmap_notifications (candidate_id, job_role, roadmap, notification_date, is_read) VALUES (?, ?, ?, CURRENT_TIMESTAMP, 0)",
                                (candidate_id, job_role, roadmap_json)
                            )
                    
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Notifications sent to {len(self.session_state['candidate_roadmaps'])} {target_audience.lower()}!")

    def display_candidate_roadmap(self, roadmap_parsed):
        tab1, tab2 = st.tabs(["📚 Training Roadmap", "📈 Learning Resources"])
        
        with tab1:
            # Collapsible Section: Missing Skills
            with st.expander("🔍 Missing Skills", expanded=True):
                if roadmap_parsed["missing_skills"]:
                    st.write("Here are the key skills the candidate needs to focus on:")
                    for skill in roadmap_parsed["missing_skills"]:
                        st.write(f"- {skill}")
                else:
                    st.warning("No missing skills identified.")

            # Collapsible Section: Step-by-Step Roadmap
            with st.expander("🗺️ Step-by-Step Learning Roadmap", expanded=True):
                if roadmap_parsed["roadmap_steps"]:
                    st.write("Recommended learning plan:")
                    for step in roadmap_parsed["roadmap_steps"]:
                        st.write(f"- {step}")
                else:
                    st.warning("No roadmap steps found.")
        
        with tab2:
            with st.expander("🎓 Free Course Links", expanded=True):
                if roadmap_parsed["free_courses"]:
                    st.write("Free resources to recommend:")
                    for name, link in roadmap_parsed["free_courses"]:
                        st.markdown(f"- [{name}]({link})")
                else:
                    st.warning("No free courses found.")

            # Collapsible Section: Paid Courses
            with st.expander("💳 Paid Course Links", expanded=True):
                if roadmap_parsed["paid_courses"]:
                    st.write("Paid resources for deeper learning:")
                    for name, link in roadmap_parsed["paid_courses"]:
                        st.markdown(f"- [{name}]({link})")
                else:
                    st.warning("No paid courses found.")

    def handle_post_job_openings(self):
        st.subheader("Post a New Job Opening")
        job_role = st.text_input("Job Role")
        job_description = st.text_area("Job Description")
        job_type = st.selectbox("Job Type", ["Full-time", "Part-time", "Internship"])
        internship_duration = None
        if job_type == "Internship":
            internship_duration = st.number_input("Internship Duration (in months)", min_value=1, step=1)

        if st.button("Post Job"):
            if job_role and job_description and job_type:
                conn, cursor = initialize_db()

                # Check if the job role already exists
                cursor.execute("SELECT job_id FROM job_postings WHERE job_role = ?", (job_role,))
                job_exists = cursor.fetchone()

                if job_exists:
                    st.warning("Job role already exists.")
                else:
                    # Insert the new job posting
                    cursor.execute(
                        "INSERT INTO job_postings (job_role, job_description, job_type, internship_duration, posted_by) VALUES (?, ?, ?, ?, ?)",
                        (job_role, job_description, job_type, internship_duration, self.session_state["user_id"]),
                    )

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
                                cursor.execute(
                                    "INSERT INTO resumes (candidate_profile_id, job_role, similarity_score) VALUES (?, ?, ?)",
                                    (candidate_id, job_role, similarity_score),
                                )
                            except FileNotFoundError:
                                print(f"Resume file not found for candidate ID {candidate_id}")
                    else:
                        # Mark the job posting as pending for future candidates
                        cursor.execute("INSERT INTO pending_jobs (job_role) VALUES (?)", (job_role,))

                    conn.commit()
                    st.success("Job posted successfully!")
                conn.close()
            else:
                st.warning("Please fill in all the required fields.")


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
        threshold = 30
        results = []
        candidate_options = {"Select a Candidate": None}  # Add placeholder option
        for candidate in candidates:
            user_id, full_name, email, similarity_score, resume_path = candidate
            # Format the name properly using the format_name function
            formatted_name = format_name(full_name)
            
            if similarity_score is not None and similarity_score >= threshold:  # Apply threshold filter
                results.append({
                    "Name": formatted_name,
                    "Email": email,
                    "Similarity Score": f"{similarity_score:.2f}%" if similarity_score is not None else "N/A",
                    "Resume Path": resume_path
                })
                candidate_options[f"{formatted_name} ({email})"] = user_id

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
        # Add import at the top of the fil   
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

                threshold = 0
                new_ranked_resumes = []
                for i, result in enumerate(ranked_resumes):
                    full_name, email, similarity_score, resume_path = result  # Unpack tuple
                    if similarity_score is not None and similarity_score >= threshold:  # Apply threshold filter
                        # Format the name properly using the format_name function
                        formatted_name = format_name(full_name)
                        
                        candidate_data = {
                            "Index": i + 1,
                            "Name": formatted_name,
                            "Email": f'<a href="mailto:{email}">{email}</a>',
                            "Score": f"{similarity_score:.2f}%" if similarity_score is not None else "N/A",
                        }

                        # Add resume download link if the file exists
                        if resume_path and os.path.exists(resume_path):
                            try:
                                with open(resume_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                # Use formatted name for the download filename
                                candidate_data["Resume"] = f'<a href="data:application/octet-stream;base64,{b64}" download="resume_{formatted_name}.pdf">📝</a>'
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
                    st.warning(f"No candidates meet the threshold of {threshold}%.")


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
                SELECT DISTINCT candidate_profiles.full_name, resumes.candidate_profile_id, resumes.evaluation, 
                candidate_profiles.is_employee
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
                for full_name, candidate_profile_id, evaluation, is_employee in results:  # Unpack all values
                    # Format the name properly using format_name function
                    formatted_name = format_name(full_name)
                    
                    if evaluation:
                        name_match = re.search(r"\| Name \| (.+?) \|", evaluation)  # Extract name from evaluation
                        if name_match:
                            candidate_data.append((formatted_name, candidate_profile_id, is_employee))
                        else:
                            candidate_data.append((formatted_name, candidate_profile_id, is_employee))  # Use formatted name
                    else:
                        candidate_data.append((formatted_name, candidate_profile_id, is_employee))  # Use formatted name

            if candidate_data:
                # Unpack the data including employee status
                candidate_names, candidate_ids, employee_statuses = zip(*candidate_data)
                self.candidate_names = candidate_names
                self.candidate_ids = candidate_ids
                self.employee_statuses = employee_statuses

                # Create a formatted list for the selectbox with employee status indicators
                display_names = [
                    f"{name} {'(Employee)' if is_employee else ''}" 
                    for name, is_employee in zip(candidate_names, employee_statuses)
                ]

                selected_index = st.selectbox(
                    "Select Candidate", display_names, index=None, placeholder="Select Candidate"
                )

                if selected_index is not None:
                    # Get the index of the selected candidate
                    selected_idx = display_names.index(selected_index)
                    self.selected_candidate_name = candidate_names[selected_idx]
                    self.selected_candidate_id = candidate_ids[selected_idx]
                    self.is_employee = employee_statuses[selected_idx]
                    
                    # Display analysis and hire button in columns
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        if st.button("View Analysis"):
                            if self.selected_candidate_name:
                                # Set the selected candidate ID for rendering analysis
                                pass
                            else:
                                st.warning("Please select a candidate.")
                    
                    with col2:
                        # Only show hire button if not already an employee
                        if not self.is_employee:
                            if st.button(f"Hire {self.selected_candidate_name}"):
                                # Call function to hire the candidate
                                if hire_candidate(self.selected_candidate_id, self.selected_job_role):
                                    st.success(f"✅ {self.selected_candidate_name} has been hired as an employee!")
                                    st.info("You can now create training roadmaps for this employee.")
                                    # Force refresh to update the UI
                                    st.rerun()
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

            # Fetch match_response based on job role
            cursor.execute("SELECT match_response FROM resumes WHERE candidate_profile_id = ? AND job_role = ?", (self.selected_candidate_id, self.selected_job_role))
            analysis_result = cursor.fetchone()
            conn.close()

            if persona_result:
                self.session_state["evaluation"] = persona_result[0]  # Persona from resumes table
            else:
                self.session_state["evaluation"] = None

            if analysis_result:
                self.session_state["match_response"] = analysis_result[0]
                
                # Display only the persona and compatibility tabs
                self.display_analysis_tabs()
            else:
                st.error("Could not retrieve analysis.")
                
    def display_analysis_tabs(self):
        tab1, tab2 = st.tabs(["📋 User Persona", "📊 Compatibility Score"])

        with tab1:
            self.display_persona(tab1)
        with tab2:
            self.display_compatibility(tab2)

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
        if "candidate_roadmaps" in self.session_state:
            del self.session_state["candidate_roadmaps"]

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
        st.subheader("📚 Training Roadmap")
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
import streamlit as st
import os
from database import initialize_db, get_candidate_profile
from pdf_processor import input_pdf_text
from ai_response import get_gemini_response
from utils import calculate_similarity_score_simple
from utils import calculate_similarity_score
import datetime
import pandas as pd
from utils import summarize_job_description


class CandidateUI:
    def __init__(self, session_state):
        self.session_state = session_state
        # Initialize navigation state
        if "current_view" not in self.session_state:
            self.session_state["current_view"] = "Search Jobs"  # Default view

    def render(self):
        # Render navigation buttons
        self.render_navigation()

        # Render the selected view
        if self.session_state["current_view"] == "Search Jobs":
            self.search_jobs()
        elif self.session_state["current_view"] == "View Persona":
            self.view_persona(candidate_id=self.session_state["user_id"])
        elif self.session_state["current_view"] == "Update Profile":
            self.update_profile()
        elif self.session_state["current_view"] == "Applied Jobs":  # New view for Applied Jobs
            self.display_applied_jobs()

    def render_navigation(self):
        st.sidebar.title(f"Welcome, {self.session_state['username']} 👋")
        if st.sidebar.button("Search Jobs"):
            self.session_state["current_view"] = "Search Jobs"
        if st.sidebar.button("View Persona"):
            self.session_state["current_view"] = "View Persona"
        if st.sidebar.button("Update Profile"):
            self.session_state["current_view"] = "Update Profile"
        if st.sidebar.button("Applied Jobs"):  # New button for Applied Jobs
            self.session_state["current_view"] = "Applied Jobs"
        if st.sidebar.button("Logout"):
            self.session_state["logged_in"] = False
            self.session_state["username"] = None
            st.rerun()

    def update_profile(self):
        """Allow candidates to update their profile by re-uploading a new resume."""
        st.title("Update Profile")
        st.subheader("Upload a new resume to update your profile and persona.")

        # File uploader for the new resume
        new_resume = st.file_uploader("Upload your new resume (PDF only)", type=["pdf"])

        # Add a unique key to the button
        if new_resume and st.button("Update Profile", key="update_profile_button"):
            try:
                # Save the uploaded resume to a temporary location
                temp_resume_path = f"temp_{self.session_state['user_id']}.pdf"
                with open(temp_resume_path, "wb") as f:
                    f.write(new_resume.read())

                # Update the profile in the database
                success = self.update_profile_in_db(temp_resume_path)

                if success:
                    st.success("✅ Profile updated successfully!")
                    st.info("Your new persona and similarity scores have been updated.")
                else:
                    st.error("❌ Failed to update profile. Please try again.")
            except Exception as e:
                st.error(f"An error occurred while updating your profile: {e}")

    def display_applied_jobs(self):
        """Display jobs the candidate has already applied for."""
        st.title("📋 Applied Jobs")
        conn, cursor = initialize_db()

        # Fetch applied jobs for the candidate
        cursor.execute(
            """
            SELECT job_postings.job_role, job_postings.job_description
            FROM resumes
            JOIN job_postings ON resumes.job_role = job_postings.job_role
            WHERE resumes.candidate_profile_id = ? AND resumes.has_applied = 1
            """,
            (self.session_state["user_id"],)
        )
        applied_jobs = cursor.fetchall()
        conn.close()

        if applied_jobs:
            for job_role, job_description in applied_jobs:
                st.markdown(f"### {job_role}")
                try:
                    # Attempt to summarize the job description
                    if job_description:
                        summarized_jd = summarize_job_description(job_description)
                    else:
                        summarized_jd = "No job description available."
                except Exception as e:
                    summarized_jd = f"Error summarizing job description: {e}"

                # Display the summarized job description in a dropdown
                with st.expander("View Job Description"):
                    st.write(summarized_jd)

                st.success(f"You have already applied for the '{job_role}' role.")
        else:
            st.info("You have not applied for any jobs yet.")

    def update_profile_in_db(self, resume_path):
        """Update the candidate's profile in the database."""
        try:
            conn, cursor = initialize_db()

            # Read the new resume text
            with open(resume_path, "rb") as f:
                resume_text = input_pdf_text(f)

            # Generate a new persona (evaluation)
            evaluation_prompt = """
                You are an HR analyst tasked with creating a user persona from a resume. Analyze the provided resume and output the persona in a table format.
                        The table should have two columns: "Category" and "Details".
                        The "Category" column must include the following rows:
                        * Name
                        * Profession
                        * Education
                        * Key Strengths
                        * Areas for Development
                        * Technical Skills
                        * Relevant Experience
                        * Achievements
                        * Certifications
                        The "Details" column should contain the corresponding information extracted from the resume, formatted as follows:
                        * **Name:** The full name of the candidate.
                        * **Profession:** The candidate's current profession (e.g., student, software engineer).
                        * **Education:** The candidate's educational qualifications (degrees, institutions, and dates).
                        * **Key Strengths:** A concise summary of the candidate's core skills and abilities. Use bullet points for each strength. **Keep descriptions very brief and to the point (no more than 3-5 words per bullet point).**
                        * **Areas for Development:** Potential areas where the candidate could grow or needs more experience. Use bullet points. **Keep descriptions very brief and to the point (no more than 3-5 words per bullet point).**
                        * **Technical Skills:** A list of technical skills, including programming languages, frameworks, tools, etc.
                        * **Relevant Experience:** A concise summary of the candidate's work history, projects, and internships. Use bullet points to list each experience. **Summarize each experience in no more than 5-7 words.**
                        * **Achievements:** Notable accomplishments and awards. Use bullet points. **Summarize each achievement in no more than 5-7 words.**
                        * **Certifications:** List of certifications. Use bullet points. **Summarize each certification in no more than 5-7 words.**
                        Formatting and Style Guidelines:
                        * The output must be in a table format.
                        * Do not include any HTML tags or special characters.
                        * Use concise language.
                        * Extract information directly from the resume. Do not add any external information or make assumptions.
                        Example Output Format:
                        | Category | Details |
                        |---|---|
                        | Name | [Full Name] |
                        | Profession | [Profession] |
                        | Education | [Education Details] |
                        | Key Strengths | * [Strength 1] <br> * [Strength 2] |
                        | Areas for Development | * [Development Area 1] <br> * [Development Area 2] |
                        | Technical Skills | [List of Skills] |
                        | Relevant Experience | * [Experience 1] <br> * [Experience 2] |
                        | Achievements | * [Achievement 1] <br> * [Achievement 2] |
                        | Certifications | * [Certification 1] <br> * [Certification 2] |
                        Here is the inputs:
                        Resume: {text}
            """
            evaluation = get_gemini_response(evaluation_prompt.format(text=resume_text), resume_text, None)

            # Update the evaluation in the resumes table for the "General" job role
            cursor.execute(
                "UPDATE resumes SET evaluation = ? WHERE candidate_profile_id = ? AND job_role = ?",
                (evaluation, self.session_state["user_id"], "General"),
            )

            # Fetch all job roles and their descriptions
            cursor.execute("SELECT job_role, job_description FROM job_postings")
            job_postings = cursor.fetchall()

            # Recalculate similarity scores for all job roles
            for job_role, job_description in job_postings:
                similarity_score = calculate_similarity_score(resume_text, job_description)
                cursor.execute(
                    "UPDATE resumes SET similarity_score = ? WHERE candidate_profile_id = ? AND job_role = ?",
                    (similarity_score, self.session_state["user_id"], job_role),
                )

            # Update the resume path in the candidate_profiles table
            cursor.execute(
                "UPDATE candidate_profiles SET resume_path = ? WHERE user_id = ?",
                (resume_path, self.session_state["user_id"]),
            )

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error updating profile: {e}")
            return False

    def view_persona(self, candidate_id):
        """Allow candidates to view their persona."""
        st.subheader("📝 User Persona")
        conn, cursor = initialize_db()
        try:
            # Fetch the evaluation (persona) from the database
            cursor.execute(
                "SELECT evaluation FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                (candidate_id, "General"),  # "General" is the placeholder job role for persona
            )
            result = cursor.fetchone()

            if result and result[0]:  # Check if the evaluation exists
                evaluation = result[0]

                # Extract the table from the evaluation response
                table_start = evaluation.find("| Category |")
                if table_start != -1:
                    table_markdown = evaluation[table_start:]
                    # Convert Markdown to CSV-like string for pandas
                    import io
                    table_csv = io.StringIO(table_markdown.replace("| ", "|").replace(" |", "|"))

                    df = pd.read_csv(table_csv, sep='|', index_col=False)

                    # Remove unnecessary columns
                    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
                    df.dropna(how='all', inplace=True)
                    if df.iloc[-1].all() == '-':
                        df = df.iloc[:-1]

                    # Display the table HTML
                    st.markdown(
                        df.to_html(index=False, escape=False),
                        unsafe_allow_html=True,
                    )
                else:
                    st.error("Table not found in the persona response.")
                    st.write(evaluation)
            else:
                st.warning("No persona found. Please upload your resume during registration.")
        except Exception as e:
            st.error(f"Could not display User Persona in table format: {e}")
        finally:
            conn.close()

    def search_jobs(self):
        st.title("Search for Jobs")

        # Add filters for job type and internship duration
        job_type_filter = st.selectbox("Job Type", ["All", "Full-time", "Part-time", "Internship"])
        internship_duration_filter = None
        if job_type_filter == "Internship":
            internship_duration_filter = st.number_input("Minimum Internship Duration (in months)", min_value=1, step=1)

        # Add a button to toggle between Recommended Jobs and Available Jobs
        if "show_recommended" not in self.session_state:
            self.session_state["show_recommended"] = False

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Recommended Jobs"):
                self.session_state["show_recommended"] = True
        with col2:
            if st.button("Available Jobs"):
                self.session_state["show_recommended"] = False

        st.markdown("---")

        # Show Recommended Jobs if toggled
        if self.session_state["show_recommended"]:
            self.display_recommended_jobs(job_type_filter, internship_duration_filter)
        else:
            self.display_available_jobs(job_type_filter, internship_duration_filter)

    def get_recommended_jobs(self):
        """Fetch recommended jobs based on resume similarity."""
        conn, cursor = initialize_db()

        # Fetch the candidate's resume path
        cursor.execute("SELECT resume_path FROM candidate_profiles WHERE user_id = ?", (self.session_state["user_id"],))
        resume_path = cursor.fetchone()[0]

        # Fetch job roles the candidate has already applied for
        cursor.execute(
            "SELECT job_role FROM resumes WHERE candidate_profile_id = ? AND has_applied = 1",
            (self.session_state["user_id"],)
        )
        applied_jobs = {row[0] for row in cursor.fetchall()}  # Use a set for faster lookups
        conn.close()

        if not resume_path or not os.path.exists(resume_path):
            return []

        try:
            with open(resume_path, "rb") as f:
                resume_text = input_pdf_text(f)

            conn, cursor = initialize_db()
            cursor.execute("SELECT job_id, job_role, job_description, job_type, internship_duration FROM job_postings")
            jobs = cursor.fetchall()
            conn.close()

            recommendations = []
            for job_id, job_role, job_description, job_type, internship_duration in jobs:
                # Skip jobs the candidate has already applied for
                if job_role in applied_jobs:
                    continue

                # Use the simple similarity logic for recommendations
                similarity_score = calculate_similarity_score_simple(resume_text, job_description)
                if similarity_score >= 80:  # Threshold for recommendations
                    recommendations.append({
                        "job_id": job_id,
                        "job_role": job_role,
                        "summary": summarize_job_description(job_description),
                        "similarity_score": similarity_score,
                        "job_type": job_type,
                        "internship_duration": internship_duration,
                    })

            # Sort recommendations by similarity score (descending)
            recommendations.sort(key=lambda x: x["similarity_score"], reverse=True)
            return recommendations
        except Exception as e:
            print(f"Error generating recommendations: {e}")
            return []

    def display_recommended_jobs(self, job_type_filter=None, internship_duration_filter=None):
        """Display recommended jobs based on resume similarity and filters."""
        st.subheader("🔍 Recommended Jobs for You")
        recommended_jobs = self.get_recommended_jobs()

        # Apply filters to the recommended jobs
        if job_type_filter and job_type_filter != "All":
            recommended_jobs = [
                job for job in recommended_jobs if job.get("job_type") == job_type_filter
            ]
        if internship_duration_filter:
            recommended_jobs = [
                job for job in recommended_jobs if job.get("internship_duration", 0) >= internship_duration_filter
            ]

        if recommended_jobs:
            for job in recommended_jobs:
                st.markdown(f"### {job['job_role']} ({job.get('job_type', 'N/A')})")
                with st.expander("View Job Description"):
                    st.write(job['summary'])  # Display the summarized job description in the dropdown

                # Check if the candidate has already applied for this job
                conn, cursor = initialize_db()
                cursor.execute(
                    "SELECT has_applied FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                    (self.session_state["user_id"], job['job_role']),
                )
                applied_status = cursor.fetchone()
                conn.close()

                if applied_status and applied_status[0] == 1:
                    st.warning(f"You have already applied for the '{job['job_role']}' role.")
                else:
                    if st.button(f"Apply for {job['job_role']}", key=f"apply_recommended_{job['job_id']}"):
                        self.apply_for_job(job['job_role'])
        else:
            st.info("No personalized recommendations available based on the selected filters.")

    def display_available_jobs(self, job_type_filter, internship_duration_filter):
        """Display all available jobs with pagination and filters."""
        st.subheader("📋 Available Jobs")

        # Fetch all jobs with pagination and filters
        conn, cursor = initialize_db()
        jobs_per_page = 10
        if "page" not in self.session_state:
            self.session_state["page"] = 0

        offset = self.session_state["page"] * jobs_per_page
        query = """
            SELECT job_id, job_role, job_description, job_type, internship_duration
            FROM job_postings
            WHERE job_role NOT IN (
                SELECT job_role FROM resumes WHERE candidate_profile_id = ? AND has_applied = 1
            )
        """
        params = [self.session_state["user_id"]]

        # Apply filters
        if job_type_filter != "All":
            query += " AND job_type = ?"
            params.append(job_type_filter)
        if internship_duration_filter:
            query += " AND (internship_duration >= ? OR internship_duration IS NULL)"
            params.append(internship_duration_filter)

        query += " LIMIT ? OFFSET ?"
        params.extend([jobs_per_page, offset])

        cursor.execute(query, tuple(params))
        jobs = cursor.fetchall()

        # Fetch total job count for pagination
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM job_postings
            WHERE job_role NOT IN (
                SELECT job_role FROM resumes WHERE candidate_profile_id = ? AND has_applied = 1
            )
        """
            + (" AND job_type = ?" if job_type_filter != "All" else "")
            + (" AND (internship_duration >= ? OR internship_duration IS NULL)" if internship_duration_filter else ""),
            tuple(params[:-2]),
        )
        total_jobs = cursor.fetchone()[0]
        conn.close()

        if jobs:
            for job_id, job_role, job_description, job_type, internship_duration in jobs:
                st.markdown(f"### {job_role} ({job_type})")
                summarized_jd = summarize_job_description(job_description)
                with st.expander("View Job Description"):
                    st.write(summarized_jd)
                if job_type == "Internship" and internship_duration:
                    st.write(f"Duration: {internship_duration} months")
                if st.button("Apply", key=f"apply_{job_id}"):
                    self.apply_for_job(job_role)

            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if self.session_state["page"] > 0:
                    if st.button("Previous"):
                        self.session_state["page"] -= 1
            with col3:
                if (self.session_state["page"] + 1) * jobs_per_page < total_jobs:
                    if st.button("Next"):
                        self.session_state["page"] += 1
        else:
            st.info("No job postings available at the moment.")

    def apply_for_job(self, selected_role):
        """Handle job application and generate match_response and roadmap."""
        candidate_profile = get_candidate_profile(self.session_state["user_id"])
        if candidate_profile and candidate_profile[7]:  # Check if resume_path exists
            resume_path = candidate_profile[7]
            try:
                with open(resume_path, "rb") as f:
                    resume_text = input_pdf_text(f)
                st.success("✅ Resume Retrieved Successfully")

                conn, cursor = initialize_db()

                # Check if the candidate already has a record for the selected job role
                cursor.execute(
                    "SELECT id FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                    (self.session_state["user_id"], selected_role),
                )
                existing_record = cursor.fetchone()

                if existing_record:
                    # Update the has_applied column if the record already exists
                    cursor.execute(
                        "UPDATE resumes SET has_applied = 1, application_date = ? WHERE candidate_profile_id = ? AND job_role = ?",
                        (datetime.datetime.now(), self.session_state["user_id"], selected_role),
                    )
                else:
                    # Insert a new record if it doesn't exist
                    cursor.execute(
                        "INSERT INTO resumes (candidate_profile_id, job_role, application_date, has_applied) VALUES (?, ?, ?, ?)",
                        (self.session_state["user_id"], selected_role, datetime.datetime.now(), 1),
                    )

                # Generate match_response and roadmap
                input_prompts = {
                    "match_response": """
                        You are an AI assistant designed to analyze resumes against job descriptions.
                        Analyze the following resume and job description.
                        Evaluate the resume based on the following core categories:
                        * Core Skills
                        * Education
                        * Industry Experience
                        * Projects
                        In addition to these core categories, identify 2-3 more categories that are highly relevant to this specific job description. Examples of additional categories include: AI/ML Development, Application of AI/ML, Deployment, Key Strengths, Areas for Focus, Communication Skills, Leadership Experience, Research Experience, etc.
                        For each identified category (both core and additional):
                        1. Assess the strength of alignment between the resume and the job description for that category.
                        2. If the resume demonstrates strong alignment with the job description for the category, precede the category with a checkmark (✔️).
                        3. If the resume demonstrates poor alignment with the job description for the category, precede the category with a warning symbol (⚠️).
                        4. When determining the Assessment use these guidelines: "Strong" means a very high level of compatibility, "Moderate" means some compatibility, and "Poor" means low or no compatibility.
                        Provide the output in a markdown table format. The table should have four columns: 'Category', 'Job Description Highlights', 'Resume Alignment', and 'Assessment'.
                        The first row of the table should be the header row with the column names:
                        For the 'Category' column, list the categories (both core and additional), each preceded by the appropriate symbol (✔️ or ⚠️) as described above.
                        For the 'Job Description Highlights' column, extract key requirements and responsibilities from the job description provided. Keep the descriptions **very brief and to the point**, focusing on the essential keywords. Do not exceed 15 words.
                        For the 'Resume Alignment' column, provide a **concise and descriptive analysis** of how the resume aligns with the corresponding job description highlight. Focus on the key strengths and relevant experience. Keep the descriptions **very brief and to the point**. Do not exceed 15 words.
                        For the 'Assessment' column, use one of these values: 'Strong', 'Good', 'Moderate'.
                        Here are the inputs:
                        JD:{jd}
                        Resume:{text}
                        Output the table in markdown format.
                    """,
                    "roadmap": """
                        Suggest a structured learning plan to fill skill gaps.
                        - **Missing Skills** (List only key missing skills)
                        - **Free Course Links** (For each missing skill and its link and name only, no description)
                        - **Paid Course Links** (For each missing skill and its link and name only, no description)
                        - **Step-by-Step Learning Roadmap** - Mention learning steps **along with estimated time required (in weeks/months)**
                        Resume: {text}
                        JD: {jd}
                    """
                }

                for key in input_prompts:
                    prompt = input_prompts[key].format(text=resume_text, jd=selected_role)
                    self.session_state[key] = get_gemini_response(prompt, resume_text, selected_role)

                cursor.execute(
                    "UPDATE resumes SET match_response = ?, roadmap = ? WHERE candidate_profile_id = ? AND job_role = ?",
                    (
                        self.session_state["match_response"],
                        self.session_state["roadmap"],
                        self.session_state["user_id"],
                        selected_role,
                    ),
                )

                conn.commit()
                conn.close()

                st.success("✅ Application submitted successfully!")

            except FileNotFoundError:
                st.error("❌ Resume file not found.")

        else:
            st.error("❌ Resume not found")

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
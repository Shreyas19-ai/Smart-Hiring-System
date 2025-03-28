import streamlit as st
import os
from database import initialize_db, get_candidate_profile
from pdf_processor import input_pdf_text
from ai_response import get_gemini_response, parse_roadmap
import datetime
from utils import summarize_job_description

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

        # Single option for candidates: Search Jobs
        self.search_jobs()

    def search_jobs(self):
        st.title("Search for Jobs")
        conn, cursor = initialize_db()
        cursor.execute("SELECT job_id, job_role, job_description FROM job_postings")
        jobs = cursor.fetchall()
        conn.close()

        if jobs:
            job_roles = [job[1] for job in jobs]
            selected_job = st.selectbox("Available Jobs", job_roles, index=0, placeholder="Select a job role")

            if selected_job:
                job_details = next(job for job in jobs if job[1] == selected_job)
                st.write(f"**Job Role:** {job_details[1]}")
                summarized_jd = summarize_job_description(job_details[2])

                with st.expander("View Job Description"):
                    st.write(summarized_jd)

                # Check if the candidate has already applied for this job
                conn, cursor = initialize_db()
                cursor.execute(
                    "SELECT has_applied FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                    (self.session_state["user_id"], job_details[1]),
                )
                applied_status = cursor.fetchone()
                conn.close()

                if applied_status and applied_status[0] == 1:
                    st.warning(f"You have already applied for the '{job_details[1]}' role.")
                else:
                    if st.button("Apply for this Job"):
                        self.apply_for_job(job_details[1])
        else:
            st.info("No job postings available at the moment.")

    def apply_for_job(self, selected_role):
        candidate_profile = get_candidate_profile(self.session_state["user_id"])
        if candidate_profile and candidate_profile[7]:  # Check if resume_path exists
            resume_path = candidate_profile[7]
            try:
                with open(resume_path, "rb") as f:
                    resume_text = input_pdf_text(f)
                st.success("✅ Resume Retrieved Successfully")

                conn, cursor = initialize_db()

                # Generate persona (evaluation) from the resume
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

                # Check if the candidate already has a record for the selected job role
                cursor.execute(
                    "SELECT id FROM resumes WHERE candidate_profile_id = ? AND job_role = ?",
                    (self.session_state["user_id"], selected_role),
                )
                existing_record = cursor.fetchone()

                if existing_record:
                    # Update the evaluation and has_applied column if the record already exists
                    cursor.execute(
                        "UPDATE resumes SET evaluation = ?, has_applied = 1, application_date = ? WHERE candidate_profile_id = ? AND job_role = ?",
                        (evaluation, datetime.datetime.now(), self.session_state["user_id"], selected_role),
                    )
                else:
                    # Insert a new record with the evaluation if it doesn't exist
                    cursor.execute(
                        "INSERT INTO resumes (candidate_profile_id, job_role, evaluation, application_date, has_applied) VALUES (?, ?, ?, ?, ?)",
                        (self.session_state["user_id"], selected_role, evaluation, datetime.datetime.now(), 1),
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
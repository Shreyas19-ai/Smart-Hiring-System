import streamlit as st
import os
from database import initialize_db
from pdf_processor import input_pdf_text
from config import job_roles
from ai_response import get_gemini_response, parse_roadmap

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

            # Generate Analysis for all 4 tabs
            input_prompts = {
                "evaluation": """
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
                            | Name | \[Full Name] |
                            | Profession | \[Profession] |
                            | Education | \[Education Details] |
                            | Key Strengths | \* \[Strength 1] <br> \* \[Strength 2] |
                            | Areas for Development | \* \[Development Area 1] <br> \* \[Development Area 2] |
                            | Technical Skills | \[List of Skills] |
                            | Relevant Experience | \* \[Experience 1] <br> \* \[Experience 2] |
                            | Achievements | \* \[Achievement 1] <br> \* \[Achievement 2] |
                            | Certifications | \* \[Certification 1] <br> \* \[Certification 2] |

                            Here are the inputs:

                            Resume: {text}
                            JD: {jd}
                        """,
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
                prompt = input_prompts[key].format(text=resume_text, jd=job_roles[selected_role])
                self.session_state[key] = get_gemini_response(prompt, resume_text, job_roles[selected_role])

            if "roadmap" in self.session_state and self.session_state["roadmap"] is not None:
                roadmap_parsed = parse_roadmap(self.session_state["roadmap"])
                self.session_state["free_courses"] = roadmap_parsed["free_courses"]
                self.session_state["paid_courses"] = roadmap_parsed["paid_courses"]
            else:
                roadmap_parsed = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

            # Store the analysis in the database
            cursor.execute(
                "UPDATE resumes SET evaluation = ?, match_response = ?, roadmap = ? WHERE id = (SELECT MAX(id) FROM resumes WHERE username = ? AND job_role = ?)",
                (
                    self.session_state["evaluation"],
                    self.session_state["match_response"],
                    self.session_state["roadmap"],
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
        if "free_courses" in self.session_state:
            del self.session_state["free_courses"]
        if "paid_courses" in self.session_state:
            del self.session_state["paid_courses"]
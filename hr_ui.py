import streamlit as st
import pandas as pd
import io
import os
import re
import base64

from database import initialize_db
from pdf_processor import input_pdf_text
from ai_response import get_gemini_response, parse_roadmap, process_bulk_resumes # import the function
from config import job_roles

class HRUI:
    def __init__(self, session_state):
        self.session_state = session_state

    def render(self):
        self.render_sidebar()
        self.render_dashboard_title()
        self.render_job_role_selection()
        self.render_action_selection()

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

    def render_action_selection(self):
        if self.selected_job_role:
            self.action = st.radio("Choose an action:", ("Screen Resumes", "View Analysis"))
            if self.action == "Screen Resumes":
                self.handle_screen_resumes()
            elif self.action == "View Analysis":
                self.handle_view_analysis()
        else:
            st.error("Please select a job role.")

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
        uploaded_file = st.file_uploader("Upload a Resume (PDF)", type="pdf")

        if uploaded_file:
            resume_text = input_pdf_text(uploaded_file)
            st.success("Resume Uploaded Successfully")

            file_name = f"uploaded_resume_{self.selected_job_role}.pdf"
            file_path = os.path.join("resumes", file_name)
            os.makedirs("resumes", exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            conn, cursor = initialize_db()
            cursor.execute(
                "INSERT INTO resumes (username, resume_text, job_role, resume_path) VALUES (?, ?, ?, ?)",
                ("hr_upload", resume_text, self.selected_job_role, file_path),
            )

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
                prompt = input_prompts[key].format(text=resume_text, jd=job_roles[self.selected_job_role])
                self.session_state[key] = get_gemini_response(prompt, resume_text, job_roles[self.selected_job_role])

            cursor.execute(
                "UPDATE resumes SET evaluation = ?, match_response = ?, roadmap = ? WHERE id = (SELECT MAX(id) FROM resumes WHERE username = ? AND job_role = ?)",
                (
                    self.session_state["evaluation"],
                    self.session_state["match_response"],
                    self.session_state["roadmap"],
                    "hr_upload",
                    self.selected_job_role,
                ),
            )
            conn.commit()
            conn.close()

            if "roadmap" in self.session_state and self.session_state["roadmap"] is not None:
                roadmap_parsed = parse_roadmap(self.session_state["roadmap"])
                self.session_state["free_courses"] = roadmap_parsed["free_courses"]
                self.session_state["paid_courses"] = roadmap_parsed["paid_courses"]
            else:
                roadmap_parsed = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

            self.display_analysis_tabs(roadmap_parsed)

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
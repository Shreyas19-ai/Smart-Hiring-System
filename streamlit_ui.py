import streamlit as st
from database import register_user, login_user, initialize_db
from pdf_processor import input_pdf_text
from ai_response import get_gemini_response, process_bulk_resumes, clear_cache
import re
import sqlite3
import pandas as pd
import uuid
import base64
import os
from config import job_roles

def render_login():
    st.title("🔑 Login")
    role = st.radio("Select Role:", ("Candidate", "HR"))
    if role == "Candidate":
        menu = ["Login", "Sign Up"]
        choice = st.radio("Select an option", menu)

        if choice == "Sign Up":
            new_user = st.text_input("Username")
            new_password = st.text_input("Password", type="password")

            if st.button("Register"):
                if register_user(new_user, new_password, "candidate"):
                    st.success("✅ Account Created! Go to Login Page.")
                else:
                    st.error("❌ Username already taken. Try another.")

        elif choice == "Login":
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")

            if st.button("Login"):
                user = login_user(username, password)

                if user:
                    if len(user) >= 3:
                        if role.lower() == user[2].lower():
                            st.session_state["user_role"] = user[2]
                            st.session_state["logged_in"] = True
                            st.session_state["username"] = username
                            if st.session_state["user_role"] == "candidate":
                                st.session_state["progress"][username] = {}
                            st.success(f"✅ Welcome, {username}!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid Role for this user.")
                    else:
                        st.error("❌ Database error: User role not found.")
                else:
                    st.error("❌ Invalid Credentials. Try Again!")

    elif role == "HR":
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = login_user(username, password)

            if user:
                if len(user) >= 3:
                    if role.lower() == user[2].lower():
                        st.session_state["user_role"] = user[2]
                        st.session_state["logged_in"] = True
                        st.session_state["username"] = username
                        st.success(f"✅ Welcome, {username}!")
                        st.rerun()

                    else:
                        st.error("❌ Invalid Role for this user.")
                else:
                    st.error("❌ Database error: User role not found.")
            else:
                st.error("❌ Invalid Credentials. Try Again!")


def render_hr_app():
    st.sidebar.title(f"Welcome, {st.session_state['username']} (HR) 👋")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.session_state["user_role"] = None
        st.rerun()

    st.title("HR Resume Screening")
    conn, cursor = initialize_db()
    cursor.execute("SELECT DISTINCT job_role FROM resumes")
    job_roles_list = cursor.fetchall()
    job_roles_list = [role[0] for role in job_roles_list]
    conn.close()

    selected_job_role = st.selectbox("Select Job Role", job_roles_list)
    if st.button("Screen Resumes"):
        clear_cache()
        if selected_job_role:
            with st.spinner("Processing Resumes..."):
                ranked_resumes = process_bulk_resumes(selected_job_role)  # Call directly

                new_ranked_resumes = []
                for i, result in enumerate(ranked_resumes):
                    result["Index"] = i + 1
                    result["Email"] = f'<a href="mailto:{result["Email"]}">{result["Email"]}</a>'

                    if result["Resume Path"]:
                        print(f"Checking for file: {result['Resume Path']}")
                        absolute_path = os.path.abspath(result["Resume Path"])
                        print(f"Absolute path: {absolute_path}")
                        if os.path.exists(absolute_path):
                            print("File exists.")
                            try:
                                with open(absolute_path, "rb") as f:
                                    b64 = base64.b64encode(f.read()).decode()
                                result["Resume"] = f'<a href="data:application/octet-stream;base64,{b64}" download="resume_{result["Name"]}.pdf">📝</a>'
                            except FileNotFoundError:
                                print("FileNotFoundError occurred.")
                                result["Resume"] = "File not found"
                            except Exception as e:
                                print(f"An error occurred: {e}")
                                result["Resume"] = f"Error: {e}"
                        else:
                            print("File does not exist.")
                            result["Resume"] = "File not found"  # Or handle this case differently
                    else:
                        print("Resume Path is empty.")
                        result["Resume"] = "Resume path not available"

                    new_ranked_resumes.append(result)

                st.markdown("---")
                df = pd.DataFrame(new_ranked_resumes)
                df = df[["Index", "Name", "Email", "Score", "Resume"]]
                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

        else:
            st.error("Please select a job role.")

def parse_roadmap(roadmap_text):
    parsed_data = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

    if roadmap_text is None:
        return parsed_data
    missing_skills_section = re.search(r"Missing Skills.*?(?=Free Course Links)", roadmap_text, re.DOTALL)

    if missing_skills_section:
        parsed_data["missing_skills"] = [skill.strip() for skill in missing_skills_section.group(0).split("\n") if skill.strip()]
    free_courses_section = re.search(r"Free Course Links.*?(?=Paid Course Links)", roadmap_text, re.DOTALL)

    if free_courses_section:
        parsed_data["free_courses"] = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", free_courses_section.group(0))
    paid_courses_section = re.search(r"Paid Course Links.*?(?=Step-by-Step Learning Roadmap)", roadmap_text, re.DOTALL)

    if paid_courses_section:
        parsed_data["paid_courses"] = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", paid_courses_section.group(0))
    roadmap_section = re.search(r"Step-by-Step Learning Roadmap.*", roadmap_text, re.DOTALL)

    if roadmap_section:
        parsed_data["roadmap_steps"] = [step.strip() for step in roadmap_section.group(0).split("\n") if step.strip()]
    return parsed_data

def clear_session_state():
    if "evaluation" in st.session_state:
        del st.session_state["evaluation"]
    if "match_response" in st.session_state:
        del st.session_state["match_response"]
    if "roadmap" in st.session_state:
        del st.session_state["roadmap"]
    if "free_courses" in st.session_state:
        del st.session_state["free_courses"]
    if "paid_courses" in st.session_state:
        del st.session_state["paid_courses"]


def render_main_app():
    st.sidebar.title(f"Welcome, {st.session_state['username']} 👋")
    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.session_state["username"] = None
        st.rerun()

    clear_session_state()

    st.title("🔍 Skill Gap Analysis & Upskilling Roadmap")
    selected_role = st.selectbox("Select a Job Role:", list(job_roles.keys()))
    uploaded_file = st.file_uploader("📂 Upload Your Resume (PDF)", type="pdf")

    if uploaded_file:
        conn, cursor = initialize_db()
        cursor.execute(
            "SELECT COUNT(*) FROM resumes WHERE username = ? AND job_role = ?",
            (st.session_state["username"], selected_role),
        )
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            st.warning(f"You have already uploaded a resume for the '{selected_role}' role. Displaying the previous analysis.")
            cursor.execute(
                "SELECT evaluation, match_response, roadmap FROM resumes WHERE username = ? AND job_role = ? ORDER BY id ASC LIMIT 1",
                (st.session_state["username"], selected_role),
            )
            existing_responses = cursor.fetchone()

            if existing_responses:
                st.session_state["evaluation"] = existing_responses[0]
                st.session_state["match_response"] = existing_responses[1]
                st.session_state["roadmap"] = existing_responses[2]
            else:
                st.error("Error retrieving existing analysis.")
        else:
            resume_text = input_pdf_text(uploaded_file)
            st.success("✅ Resume Uploaded Successfully")

            file_name = f"{st.session_state['username']}_{selected_role}.pdf"
            file_path = os.path.join("resumes", file_name)
            os.makedirs("resumes", exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            cursor.execute(
                "INSERT INTO resumes (username, resume_text, job_role, resume_path) VALUES (?, ?, ?, ?)",
                (st.session_state["username"], resume_text, selected_role, file_path),
            )

            input_prompts = {
                "evaluation": """
                    Evaluate the resume against the job description.
                    - **Strengths** (Highlight relevant skills)
                    - **Weaknesses** (List missing skills)
                    - **Overall Fit Summary** (Concise job match evaluation)
                    Resume: {text}
                    JD: {jd}
                """,
                "match_response": """
                    Analyze the resume and job description.
                    - **Missing Keywords** (Important job-related terms not in the resume)
                    - **Final Thoughts** (Brief improvement suggestions)
                    Resume: {text}
                    JD: {jd}
                """,
                "roadmap": """
                    Suggest a structured learning plan to fill skill gaps.
                    - **Missing Skills** (List only key missing skills)
                    - **Free Course Links** (For each missing skill and its link and name only, no description)
                    - **Paid Course Links** (For each missing skill and its link and name only, no description)
                    - **Step-by-Step Learning Roadmap** - Mention learning steps **along with estimated time required (in weeks/months)**
                    Resume: {text}
                    JD: {jd}
                """,
            }

            for key in input_prompts:
                prompt = input_prompts[key].format(text=resume_text, jd=job_roles[selected_role])
                st.session_state[key] = get_gemini_response(prompt, resume_text, job_roles[selected_role])

            cursor.execute(
                "UPDATE resumes SET evaluation = ?, match_response = ?, roadmap = ? WHERE id = (SELECT MAX(id) FROM resumes WHERE username = ? AND job_role = ?)",
                (
                    st.session_state["evaluation"],
                    st.session_state["match_response"],
                    st.session_state["roadmap"],
                    st.session_state["username"],
                    selected_role,
                ),
            )
            conn.commit()
            conn.close()

        if "roadmap" in st.session_state and st.session_state["roadmap"] is not None:
            roadmap_parsed = parse_roadmap(st.session_state["roadmap"])
            st.session_state["free_courses"] = roadmap_parsed["free_courses"]
            st.session_state["paid_courses"] = roadmap_parsed["paid_courses"]
        else:
            roadmap_parsed = {"missing_skills": [], "free_courses": [], "paid_courses": [], "roadmap_steps": []}

        tab1, tab2, tab3, tab4 = st.tabs(["📋 User Persona", "📊 Compatibility Score", "📚 Learning Pathway", "📈 Progress Tracking"])

        with tab1:
            st.subheader("📝 User Persona")
            if "evaluation" in st.session_state and st.session_state["evaluation"] is not None:
                st.write(st.session_state["evaluation"])

        with tab2:
            st.subheader("📊 Compatibility Score")
            if "match_response" in st.session_state and st.session_state["match_response"] is not None:
                st.write(st.session_state["match_response"])

        with tab3:
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

        with tab4:
            # Collapsible Section: Free Courses
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
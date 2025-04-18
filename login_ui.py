import streamlit as st
from database import register_user, login_user
from ai_response import extract_details_with_gemini
from pdf_processor import input_pdf_text

class LoginUI:
    def __init__(self, session_state):
        self.session_state = session_state

    def render(self):
        st.title("🔑 Login")
        role = st.radio("Select Role:", ("Candidate", "HR"))

        if role == "Candidate":
            menu = ["Login", "Sign Up"]
            choice = st.radio("Select an option", menu)

            if choice == "Sign Up":
                new_user = st.text_input("Username")
                new_password = st.text_input("Password", type="password")
                uploaded_file = st.file_uploader("Upload Resume (PDF)", type="pdf")

                if st.button("Register"):
                    if uploaded_file:
                        file_path = f"resumes/{new_user}.pdf"
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getvalue())

                        # Extract details from the resume using Gemini
                        with open(file_path, "rb") as f:
                            resume_text = input_pdf_text(f)

                        # Use Gemini to extract details from the resume
                        extracted_data = extract_details_with_gemini(resume_text)

                        if extracted_data:
                            full_name = extracted_data.get("full_name")
                            email = extracted_data.get("email")
                            phone_number = extracted_data.get("phone_number")
                            education = extracted_data.get("education")
                            skills = extracted_data.get("skills")
                            experience = extracted_data.get("experience")

                            if register_user(new_user, new_password, "candidate", full_name, email, phone_number, education, skills, experience, file_path, None):
                                st.success("✅ Account Created! Go to Login Page.")
                            else:
                                st.error("❌ Username already taken. Try another.")
                        else:
                            st.error("❌ Could not extract details from the resume. Please try again.")
                    else:
                        st.error("Please upload a resume")

            elif choice == "Login":
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")

                if st.button("Login"):
                    user = login_user(username, password)

                    if user:
                        if len(user) >= 3:
                            if role.lower() == user[2].lower():
                                self.session_state["user_id"] = user[0]
                                self.session_state["user_role"] = user[2]
                                self.session_state["logged_in"] = True
                                self.session_state["username"] = username
                                if self.session_state["user_role"] == "candidate":
                                    if "progress" not in self.session_state:
                                        self.session_state["progress"] = {}
                                    self.session_state["progress"][username] = {}
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
                            self.session_state["user_id"] = user[0]
                            self.session_state["user_role"] = user[2]
                            self.session_state["logged_in"] = True
                            self.session_state["username"] = username
                            st.success(f"✅ Welcome, {username}!")
                            st.rerun()
                        else:
                            st.error("❌ Invalid Role for this user.")
                    else:
                        st.error("❌ Database error: User role not found.")
                else:
                    st.error("❌ Invalid Credentials. Try Again!")
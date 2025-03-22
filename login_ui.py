import streamlit as st
from database import register_user, login_user

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
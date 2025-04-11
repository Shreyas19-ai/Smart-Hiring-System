import sqlite3
import hashlib
import os
from utils import calculate_similarity_score_simple, calculate_similarity_score
from ai_response import get_gemini_response
from pdf_processor import input_pdf_text
import datetime

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_db():
    db_file = "users.db"
    print(f"Database file: {os.path.abspath(db_file)}")
    new_db = not os.path.exists(db_file)

    # Set a timeout to handle database locks
    conn = sqlite3.connect(db_file, check_same_thread=False, timeout=30)
    cursor = conn.cursor()

    # Enable Write-Ahead Logging (WAL) mode for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL;")

    if new_db:
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                email TEXT
            )
        ''')

        # Create candidate_profiles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candidate_profiles (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone_number TEXT,
                education TEXT,
                skills TEXT,
                experience TEXT,
                resume_path TEXT,
                additional_information TEXT,
                is_employee INTEGER DEFAULT 0,
                hire_date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS employee_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            job_role TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            FOREIGN KEY (employee_id) REFERENCES candidate_profiles (user_id)
        )
    ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS roadmap_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            job_role TEXT NOT NULL,
            roadmap TEXT,
            notification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER DEFAULT 0,
            FOREIGN KEY (candidate_id) REFERENCES candidate_profiles (user_id)
        )
    ''')

        # Create resumes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_profile_id INTEGER,
                job_role TEXT NOT NULL,
                evaluation TEXT,
                match_response TEXT,
                roadmap TEXT,
                application_date TEXT,
                similarity_score REAL,
                personalized_similarity_score REAL,
                has_applied INTEGER DEFAULT 0,       
                FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles (user_id)
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_role TEXT NOT NULL,
            job_description TEXT NOT NULL,
            job_type TEXT,
            internship_duration INTEGER,
            posted_by INTEGER NOT NULL,
            FOREIGN KEY (posted_by) REFERENCES users (id)
        )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_candidates (
                candidate_profile_id INTEGER PRIMARY KEY,
                FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles (user_id)
            )
        ''')

        # Create pending_jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_jobs (
                job_role TEXT PRIMARY KEY
            )
        ''')

        # Predefined HR users (example)
        hr_users = [
            ("hr1", hash_password("hrpass1"), "hr"),
            ("hr2", hash_password("hrpass2"), "hr"),
        ]

        for user in hr_users:
            try:
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", user)
            except sqlite3.IntegrityError:
                pass
        conn.commit()
    else:
        # Check if columns exist, if not, add them.
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN application_date TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    return conn, cursor


def register_user(username, password, role, full_name, email, phone_number, education, skills, experience, resume_path, additional_information):
    try:
        hashed_password = hash_password(password)
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()

            # Insert user into the users table
            cursor.execute("INSERT INTO users (username, password, role, email) VALUES (?, ?, ?, ?)", 
                           (username, hashed_password, role, email))
            user_id = cursor.lastrowid

            # Insert candidate profile into the candidate_profiles table
            cursor.execute("INSERT INTO candidate_profiles (user_id, full_name, email, phone_number, education, skills, experience, resume_path, additional_information) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                           (user_id, full_name, email, phone_number, education, skills, experience, resume_path, additional_information))

            # Read the resume text
            with open(resume_path, "rb") as f:
                resume_text = input_pdf_text(f)

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

            # Store the persona in the resumes table with a placeholder job role ("General")
            cursor.execute("INSERT INTO resumes (candidate_profile_id, job_role, evaluation) VALUES (?, ?, ?)", 
                           (user_id, "General", evaluation))

            # Fetch all job roles and their descriptions
            cursor.execute("SELECT job_role, job_description FROM job_postings")
            job_postings = cursor.fetchall()

            if job_postings:
                # Calculate similarity scores for each job role
                for job_role, job_description in job_postings:
                    # Use advanced logic for shortlisting
                    similarity_score = calculate_similarity_score(resume_text, job_description)
                    # Use simple logic for personalized recommendations
                    personalized_similarity_score = calculate_similarity_score_simple(resume_text, job_description)

                    # Store both scores in the database
                    cursor.execute("""
                        INSERT INTO resumes (candidate_profile_id, job_role, similarity_score, personalized_similarity_score) 
                        VALUES (?, ?, ?, ?)
                    """, (user_id, job_role, similarity_score, personalized_similarity_score))
            else:
                # Mark the candidate as pending for future job postings
                cursor.execute("INSERT INTO pending_candidates (candidate_profile_id) VALUES (?)", (user_id,))

            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Error during registration: {e}")
        return False

def login_user(username, password):
    hashed_password = hash_password(password)
    conn, cursor = initialize_db()
    try:
        cursor.execute("SELECT id, username, role FROM users WHERE username = ? AND password = ?", (username, hashed_password))
        return cursor.fetchone()
    finally:
        conn.close()

def get_candidate_profile(user_id):
    """
    Fetch the entire candidate profile using the user_id.
    """
    conn, cursor = initialize_db()
    try:
        cursor.execute("SELECT * FROM candidate_profiles WHERE user_id = ?", (user_id,))
        return cursor.fetchone()
    finally:
        conn.close()

def get_application_resumes(job_role):
    conn, cursor = initialize_db()
    try:
        cursor.execute('''
            SELECT candidate_profiles.full_name, candidate_profiles.email, resumes.evaluation, resumes.match_response, resumes.roadmap, candidate_profiles.resume_path, resumes.candidate_profile_id
            FROM resumes
            JOIN candidate_profiles ON resumes.candidate_profile_id = candidate_profiles.user_id
            WHERE resumes.job_role = ?
        ''', (job_role,))
        return cursor.fetchall()
    finally:
        conn.close()

def get_candidate_profile_by_id(candidate_id):
    conn, cursor = initialize_db()
    try:
        cursor.execute("SELECT full_name, email, skills, experience FROM candidate_profiles WHERE user_id = ?", (candidate_id,))
        result = cursor.fetchone()
        if result:
            return {
                'full_name': result[0],
                'email': result[1],
                'skills': result[2],
                'experience': result[3],
            }
        else:
            return None
    finally:
        conn.close()

    
def get_resume_analysis(candidate_profile_id, job_role):
    conn, cursor = initialize_db()
    try:
        cursor.execute('''
            SELECT evaluation, match_response, roadmap
            FROM resumes
            WHERE candidate_profile_id = ? AND job_role = ?
        ''', (candidate_profile_id, job_role,))
        return cursor.fetchone()
    finally:
        conn.close()

def process_pending_scores():
    conn, cursor = initialize_db()

    # Process pending candidates
    cursor.execute("SELECT candidate_profile_id FROM pending_candidates")
    pending_candidates = cursor.fetchall()

    cursor.execute("SELECT job_role, job_description FROM job_postings")
    job_postings = cursor.fetchall()

    for candidate_id, in pending_candidates:
        cursor.execute("SELECT resume_path FROM candidate_profiles WHERE user_id = ?", (candidate_id,))
        resume_path = cursor.fetchone()[0]
        try:
            with open(resume_path, "rb") as f:
                resume_text = f.read().decode('utf-8', errors='ignore')
            for job_role, job_description in job_postings:
                # Calculate both scores
                similarity_score = calculate_similarity_score(resume_text, job_description)
                personalized_similarity_score = calculate_similarity_score_simple(resume_text, job_description)

                # Store both scores in the database
                cursor.execute("""
                    INSERT INTO resumes (candidate_profile_id, job_role, similarity_score, personalized_similarity_score) 
                    VALUES (?, ?, ?, ?)
                """, (candidate_id, job_role, similarity_score, personalized_similarity_score))
            cursor.execute("DELETE FROM pending_candidates WHERE candidate_profile_id = ?", (candidate_id,))
        except FileNotFoundError:
            print(f"Resume file not found for candidate ID {candidate_id}")

    conn.commit()
    conn.close()

def get_candidate_roadmaps(candidate_id):
    conn, cursor = initialize_db()
    cursor.execute('''
        SELECT id, job_role, roadmap, notification_date, is_read 
        FROM roadmap_notifications 
        WHERE candidate_id = ? 
        ORDER BY notification_date DESC
    ''', (candidate_id,))
    roadmaps = cursor.fetchall()
    conn.close()
    return roadmaps

# Add a function to mark a notification as read
def mark_roadmap_as_read(notification_id):
    conn, cursor = initialize_db()
    cursor.execute("UPDATE roadmap_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()
    return True

def hire_candidate(candidate_id, job_role):
    """
    Mark a candidate as hired (employee) and record the hire date
    """
    conn, cursor = initialize_db()
    hire_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Update the candidate profile to mark as employee
    cursor.execute(
        "UPDATE candidate_profiles SET is_employee = 1, hire_date = ? WHERE user_id = ?",
        (hire_date, candidate_id)
    )
    
    # Record the job role they were hired for
    cursor.execute(
        "INSERT INTO employee_roles (employee_id, job_role, start_date) VALUES (?, ?, ?)",
        (candidate_id, job_role, hire_date)
    )
    
    conn.commit()
    conn.close()
    return True

# Create a function to get all employees
def get_all_employees():
    """
    Get all users who are marked as employees
    """
    conn, cursor = initialize_db()
    cursor.execute('''
        SELECT user_id, full_name, email, resume_path, hire_date 
        FROM candidate_profiles 
        WHERE is_employee = 1
    ''')
    employees = cursor.fetchall()
    conn.close()
    return employees

# Create a function to check if a user is an employee
def is_employee(user_id):
    """
    Check if a user is an employee
    """
    conn, cursor = initialize_db()
    cursor.execute("SELECT is_employee FROM candidate_profiles WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] == 1 if result else False
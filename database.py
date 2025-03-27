import sqlite3
import hashlib
import os
from utils import calculate_similarity_score

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_db():
    db_file = "users.db"
    print(f"Database file: {os.path.abspath(db_file)}")
    new_db = not os.path.exists(db_file)

    conn = sqlite3.connect(db_file, check_same_thread=False)
    cursor = conn.cursor()

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
                FOREIGN KEY (user_id) REFERENCES users (id)
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
                has_applied INTEGER DEFAULT 0,       
                FOREIGN KEY (candidate_profile_id) REFERENCES candidate_profiles (user_id)
            )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS job_postings (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_role TEXT NOT NULL,
            job_description TEXT NOT NULL,
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
                resume_text = f.read().decode('utf-8', errors='ignore')

            # Fetch all job roles and their descriptions
            cursor.execute("SELECT job_role, job_description FROM job_postings")
            job_postings = cursor.fetchall()

            if job_postings:
                # Calculate similarity score for each job role and store in the database
                for job_role, job_description in job_postings:
                    similarity_score = calculate_similarity_score(resume_text, job_description)
                    cursor.execute("INSERT INTO resumes (candidate_profile_id, job_role, similarity_score) VALUES (?, ?, ?)", 
                                   (user_id, job_role, similarity_score))
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
                similarity_score = calculate_similarity_score(resume_text, job_description)
                cursor.execute("INSERT INTO resumes (candidate_profile_id, job_role, similarity_score) VALUES (?, ?, ?)", 
                               (candidate_id, job_role, similarity_score))
            cursor.execute("DELETE FROM pending_candidates WHERE candidate_profile_id = ?", (candidate_id,))
        except FileNotFoundError:
            print(f"Resume file not found for candidate ID {candidate_id}")

    # Process pending jobs
    cursor.execute("SELECT job_role FROM pending_jobs")
    pending_jobs = cursor.fetchall()

    cursor.execute("SELECT user_id, resume_path FROM candidate_profiles")
    candidates = cursor.fetchall()

    for job_role, in pending_jobs:
        cursor.execute("SELECT job_description FROM job_postings WHERE job_role = ?", (job_role,))
        job_description = cursor.fetchone()[0]
        for candidate_id, resume_path in candidates:
            try:
                with open(resume_path, "rb") as f:
                    resume_text = f.read().decode('utf-8', errors='ignore')
                similarity_score = calculate_similarity_score(resume_text, job_description)
                cursor.execute("INSERT INTO resumes (candidate_profile_id, job_role, similarity_score) VALUES (?, ?, ?)", 
                               (candidate_id, job_role, similarity_score))
            except FileNotFoundError:
                print(f"Resume file not found for candidate ID {candidate_id}")
        cursor.execute("DELETE FROM pending_jobs WHERE job_role = ?", (job_role,))

    conn.commit()
    conn.close()
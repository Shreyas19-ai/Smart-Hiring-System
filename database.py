'''
this code includes logic for resume upload path

this code is after dinner
'''

import sqlite3
import hashlib
import os

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def initialize_db():
    db_file = "users.db"
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

        # Create resumes table with resume_path column
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                resume_text TEXT NOT NULL,
                job_role TEXT NOT NULL,
                score REAL,
                evaluation TEXT,
                match_response TEXT,
                roadmap TEXT,
                resume_path TEXT,
                FOREIGN KEY (username) REFERENCES users (username)
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
        # Check if columns exist, if not, add them
        try:
            cursor.execute("ALTER TABLE resumes ADD COLUMN evaluation TEXT")
            cursor.execute("ALTER TABLE resumes ADD COLUMN match_response TEXT")
            cursor.execute("ALTER TABLE resumes ADD COLUMN roadmap TEXT")
            cursor.execute("ALTER TABLE resumes ADD COLUMN resume_path TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            # Columns already exist
            pass

    return conn, cursor

def register_user(username, password, role):
    try:
        hashed_password = hash_password(password)
        with sqlite3.connect("users.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, hashed_password, role))
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def login_user(username, password):
    hashed_password = hash_password(password)
    conn, cursor = initialize_db()
    try:
        cursor.execute("SELECT username, password, role FROM users WHERE username = ? AND password = ?", (username, hashed_password))
        return cursor.fetchone()
    finally:
        conn.close()
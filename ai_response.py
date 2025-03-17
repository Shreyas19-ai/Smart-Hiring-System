import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
from config import job_roles
import uuid
from database import initialize_db
import pandas as pd
import streamlit as st
import time
import json

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_gemini_response(prompt, resume_text, jd_text):
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = model.generate_content(prompt)
    return response.text if response and response.text else "No response generated."

@st.cache_data
def process_bulk_resumes(job_role):
    conn, cursor = initialize_db()
    results = []
    cursor.execute("SELECT username, resume_text, resume_path FROM resumes WHERE job_role = ?", (job_role,))
    resumes = cursor.fetchall()
    conn.close()

    seen_candidates = set()  # Keep track of processed candidates

    for username, resume_text, resume_path in resumes:
        job_description = job_roles[job_role]
        prompt = f"""
            Analyze the resume and job description.
            Find the candidate's full name. It is typically the largest text at the top of the resume.
            Provide the following information in JSON format:
            {{
                "Name": "<candidate's full name>",
                "Email": "<candidate's email address>",
                "Matching Percentage": "<percentage>%"
            }}

            If you cannot find the name, email, or matching percentage, provide default values.

            Resume: {resume_text}
            JD: {job_description}
        """

        response = get_gemini_response(prompt, resume_text, job_description)
        time.sleep(1)
        print(f"Gemini API Response: {response}")
        try:
            # Remove markdown code block
            json_string = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(json_string)
            name = data.get("Name", "Name not found")
            email = data.get("Email", "Email not found")
            score = int(data.get("Matching Percentage", "0%").replace("%", ""))

            # Check if candidate has already been processed
            candidate_key = (name, email)  # Use name and email as a unique key

            if candidate_key not in seen_candidates:
                results.append({"Name": name, "Email": email, "Score": score, "Resume Path": resume_path}) # added resume path
                seen_candidates.add(candidate_key)  # Add candidate to seen set
            else:
                print(f"Skipping duplicate candidate: {name}, {email}")

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}, Response: {response}")
            name, email = extract_name_email_from_response(response)
            score = extract_score_from_response(response)
            results.append({"Name": name, "Email": email, "Score": score, "Resume Path": resume_path}) #added resume path

    results.sort(key=lambda x: x["Score"], reverse=True)
    return results


def extract_name_email_from_response(response):
    """Fallback function to extract name and email using regular expressions."""
    name_match = re.search(r"Name: (.+)\n", response)
    email_match = re.search(r"Email: (.+)\n", response)
    name = name_match.group(1).strip() if name_match else "Name not found"
    email = email_match.group(1).strip() if email_match else "Email not found"
    return name, email

def extract_score_from_response(response):
    """Fallback function to extract score using regular expressions."""
    try:
        match = re.search(r"Matching Percentage:\s*(\d+)%", response, re.IGNORECASE)
        if match:
            return int(match.group(1))
        else:
            return 0
    except Exception as e:
        return 0

def clear_cache():
    process_bulk_resumes.clear()

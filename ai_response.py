import google.generativeai as genai
import os
from dotenv import load_dotenv
import re
import uuid
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


def extract_details_with_gemini(resume_text):
    """
    Use Gemini to extract structured details from the resume text.
    """
    try:
        # Define the prompt for Gemini
        prompt = f"""
        You are an AI assistant designed to extract structured information from resumes.
        Extract the following details from the resume text provided:
        {{
        - Full Name : <candidate's full name> 
        - Email : <candidate's email address>
        - Phone Number : <candidate's phone number>
        - Education : <candidate's education details>
        - Skills : <candidate's skills>
        - Experience : <candidate's work experience>
        }}

        Provide the output in JSON format with keys: full_name, email, phone_number, education, skills, experience.
        If any field is not found, use an empty string instead of null.

        Resume Text:
        {resume_text}
        """

        # Generate response using Gemini
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        print(f"Gemini API Response: {response}")

        # Extract the text content from the response
        response_text = response.text if response and response.text else None

        if response_text:
            # More robust JSON extraction
            # First, try to find JSON pattern in the response
            json_match = re.search(r'({[\s\S]*})', response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                # If no clear JSON pattern, clean up markdown formatting
                json_str = response_text.replace('```json', '').replace('```', '').strip()
            
            # Parse the JSON
            data = json.loads(json_str)
            
            # Replace any None/null values with empty strings
            for key in data:
                if data[key] is None:
                    data[key] = ""
                    
            # Generate a unique identifier to append to username if needed
            unique_id = str(uuid.uuid4())[:8]
            
            # If email is empty, create a placeholder
            if not data.get("email"):
                data["email"] = f"user_{unique_id}@example.com"
                
            # Ensure full_name is unique by adding a unique identifier if needed
            if data.get("full_name"):
                data["original_full_name"] = data["full_name"]
                data["full_name"] = f"{data['full_name']}_{unique_id}"
            
            return data
        else:
            print("No response text received from Gemini.")
            # Return default values with unique identifiers
            unique_id = str(uuid.uuid4())[:8]
            return {
                "full_name": f"User_{unique_id}",
                "email": f"user_{unique_id}@example.com",
                "phone_number": "",
                "education": "",
                "skills": "",
                "experience": ""
            }
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}, Response: {response.text if response else 'No response'}")
        # Return default values with unique identifiers
        unique_id = str(uuid.uuid4())[:8]
        return {
            "full_name": f"User_{unique_id}",
            "email": f"user_{unique_id}@example.com",
            "phone_number": "",
            "education": "",
            "skills": "",
            "experience": ""
        }
    except Exception as e:
        print(f"Error extracting details with Gemini: {e}")
        # Return default values with unique identifiers
        unique_id = str(uuid.uuid4())[:8]
        return {
            "full_name": f"User_{unique_id}",
            "email": f"user_{unique_id}@example.com",
            "phone_number": "",
            "education": "",
            "skills": "",
            "experience": ""
        }


def generate_roadmap_for_candidate(resume_text, job_description):
    """
    Generate a learning roadmap for a candidate based on their resume and the job description.
    
    Args:
        resume_text (str): The text content of the candidate's resume
        job_description (str): The job description or job role
        
    Returns:
        str: A structured roadmap with missing skills and recommended courses
    """
    try:
        # Define the prompt for roadmap generation
        roadmap_prompt = f"""
        You are a career development expert. Analyze the candidate's resume against the job description to identify skill gaps.
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Create a structured learning plan with the following sections:
        
        1. Missing Skills
        List the key skills that the candidate needs to develop based on the job requirements (list only 5-7 most important skills).
        
        2. Free Course Links
        For each missing skill, recommend one free online course or resource. Include the course name and URL in markdown format: [Course Name](URL)
        
        3. Paid Course Links
        For each missing skill, recommend one paid course that offers more comprehensive learning. Include the course name and URL in markdown format: [Course Name](URL)
        
        4. Step-by-Step Learning Roadmap
        Create a structured learning path with 5-7 steps, each with an estimated time frame (in weeks/months).
        
        Format your response with clear section headers.
        """
        
        # Generate the roadmap using Gemini
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(roadmap_prompt)
        return response.text if response and response.text else "No roadmap generated."
    except Exception as e:
        print(f"Error generating roadmap: {e}")
        return f"Error generating roadmap: {str(e)}"

    
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
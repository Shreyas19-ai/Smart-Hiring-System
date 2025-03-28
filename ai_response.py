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

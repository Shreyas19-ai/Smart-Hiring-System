from dotenv import load_dotenv
import google.generativeai as genai
import os

# Load environment variables and configure the Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def calculate_similarity_score(resume_text, job_description, job_requirements=None):
    """
    Calculate a multi-factor similarity score between a resume and a job description.
    """
    try:
        # Step 1: Semantic Similarity
        prompt = f"""
        Evaluate the semantic similarity between the following two texts and provide a similarity score between 0 and 100:
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide only the similarity score as a number.
        """
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        semantic_similarity = float(response.text.strip())
        
        # Step 2: Keyword Matching
        if job_requirements:
            required_keywords = job_requirements.get("keywords", [])
            resume_keywords = resume_text.lower().split()
            keyword_matches = len(set(required_keywords) & set(resume_keywords))
            keyword_match_score = (keyword_matches / len(required_keywords)) * 100 if required_keywords else 0
        else:
            keyword_match_score = 0

        # Step 3: Experience Matching
        required_experience = job_requirements.get("experience", 0) if job_requirements else 0
        candidate_experience = extract_experience_from_resume(resume_text)  # Custom function to extract experience
        experience_score = 100 if candidate_experience >= required_experience else (candidate_experience / required_experience) * 100

        # Step 4: Education Matching
        required_education = job_requirements.get("education", "").lower() if job_requirements else ""
        candidate_education = extract_education_from_resume(resume_text).lower()  # Custom function to extract education
        education_score = 100 if required_education in candidate_education else 0

        # Step 5: Final Weighted Score
        final_score = (0.6 * semantic_similarity) + (0.2 * keyword_match_score) + (0.1 * experience_score) + (0.1 * education_score)
        return round(final_score, 2)
    except Exception as e:
        print(f"Error calculating similarity score: {e}")
        return 0
    
def extract_experience_from_resume(resume_text):
    """
    Extract the total years of experience from the resume using the Gemini API.
    """
    try:
        # Define the prompt for extracting experience
        prompt = f"""
        Analyze the following resume and extract the total years of professional experience. 
        If the experience is not explicitly mentioned, estimate it based on the roles and durations described in the resume:
        
        Resume:
        {resume_text}
        
        Provide only the total years of experience as a number (e.g., `5`). If it cannot be determined, return `0`.
        """
        # Use the Gemini API to extract experience
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        # Extract and validate the experience
        experience_text = response.text.strip()
        if experience_text.isdigit() or experience_text.replace('.', '', 1).isdigit():
            experience = float(experience_text)
        else:
            print(f"Non-numeric experience response: {experience_text}")
            experience = 0  # Default to 0 if the response is not numeric

        print(f"Extracted Experience: {experience} years")
        return experience
    except Exception as e:
        print(f"Error extracting experience from resume: {e}")
        return 0  # Default to 0 if extraction fails


def extract_education_from_resume(resume_text):
    """
    Extract the highest level of education from the resume using the Gemini API.
    """
    try:
        # Define the prompt for extracting education
        prompt = f"""
        Analyze the following resume and extract the highest level of education achieved by the candidate 
        (e.g., `Bachelor's`, `Master's`, `PhD`). If multiple degrees are mentioned, provide only the highest qualification.
        If it cannot be determined, return `Unknown`.
        
        Resume:
        {resume_text}
        
        Provide only the highest level of education as a single word or phrase.
        """
        # Use the Gemini API to extract education
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        # Extract and validate the education level
        education = response.text.strip()
        if not education or "cannot determine" in education.lower():
            print(f"Unclear education response: {education}")
            education = "Unknown"  # Default to "Unknown" if the response is unclear

        print(f"Extracted Education: {education}")
        return education
    except Exception as e:
        print(f"Error extracting education from resume: {e}")
        return "Unknown"  # Default to "Unknown" if extraction fails
        
        

def summarize_job_description(job_description):
    """
    Summarize the job description using the Gemini API.
    """
    try:
        # Define the prompt for summarization
        prompt = f"""
        Summarize the following job description into key elements such as required skills, qualifications, and responsibilities:
        {job_description}
        """
        # Use the Gemini API to generate the summary
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        
        # Extract and return the summary
        return response.text if response and response.text else "Error: No summary generated."
    except Exception as e:
        print(f"Error summarizing job description using Gemini: {e}")
        return "Error summarizing job description."
    

# Similarity for personalized job recommendations
def calculate_similarity_score_simple(resume_text, job_description):
    """
    Calculate the semantic similarity score between a resume and a job description using a prompt-based approach with the Gemini API.
    """
    try:
        # Define the prompt for similarity evaluation
        prompt = f"""
        Evaluate the semantic similarity between the following two texts and provide a similarity score between 0 and 100:
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide only the similarity score as a number.
        """
        
        # Use the Gemini API to generate the similarity score
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        response = model.generate_content(prompt)
        print(f"Gemini API Response: {response}")
        
        # Extract the similarity score from the response
        similarity_score = float(response.text.strip())
        print(f"Gemini API Similarity Score: {similarity_score}")
        
        return round(similarity_score, 2)
    except Exception as e:
        print(f"Error calculating semantic similarity score: {e}")
        return 0


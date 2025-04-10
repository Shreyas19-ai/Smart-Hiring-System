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
        # Step 1: Semantic Similarity - Keep this as it's working well
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
        
        # Step 2: Direct AI-based skill matching instead of keyword extraction
        skills_prompt = f"""
        Analyze the following resume and job description. Identify the skills mentioned in the job description 
        and check if they appear in the resume. Return a score from 0 to 100 representing the percentage of 
        required skills that are present in the resume.
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide only the skills match percentage as a number between 0 and 100.
        """
        
        skills_response = model.generate_content(skills_prompt)
        skills_match_score = float(skills_response.text.strip())
        
        # Step 3: Direct AI-based experience matching
        experience_prompt = f"""
        Analyze the following resume and job description. The job description may mention required years of experience.
        Based on the resume, determine if the candidate meets the experience requirements.
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Return a score from 0 to 100:
        - 100 if the candidate exceeds the required experience
        - 75 if the candidate meets the required experience
        - 50 if the candidate is slightly below the required experience
        - 25 if the candidate has relevant experience but not enough
        - 0 if the candidate has no relevant experience
        
        Provide only the score as a number.
        """
        
        experience_response = model.generate_content(experience_prompt)
        experience_score = float(experience_response.text.strip())
        
        # Step 4: Final Weighted Score - adjusted weights to emphasize skills and semantic similarity
        # Removed education component and redistributed weights
        final_score = (0.5 * semantic_similarity) + (0.35 * skills_match_score) + (0.15 * experience_score)
        
        return round(final_score, 2)
    except Exception as e:
        print(f"Error calculating similarity score: {e}")
        return 0        
        

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

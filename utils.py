from dotenv import load_dotenv
import google.generativeai as genai
import os

# Load environment variables and configure the Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def calculate_similarity_score(resume_text, job_description):
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


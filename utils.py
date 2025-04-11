from dotenv import load_dotenv
import google.generativeai as genai
import os

# Load environment variables and configure the Gemini API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def calculate_similarity_score(resume_text, job_description, job_requirements=None):
    """
    Calculate the contextual similarity score between a resume and a job description.
    """
    try:
        # Define the prompt for contextual similarity evaluation
        prompt = f"""
        Evaluate the contextual similarity between the following two texts and provide a similarity score between 0 and 100:
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide only the similarity score as a  between 0 - 100.
        """
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content(prompt)
        return float(response.text.strip())
    except Exception as e:
        print(f"Error calculating contextual similarity score: {e}")
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
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content(prompt)
        
        # Extract and return the summary
        return response.text if response and response.text else "Error: No summary generated."
    except Exception as e:
        print(f"Error summarizing job description using Gemini: {e}")
        return "Error summarizing job description."
    

# Similarity for personalized job recommendations
def calculate_similarity_score_simple(resume_text, job_description):
    """
    Calculate the contextual similarity score between a resume and a job description.
    """
    try:
        # Define the prompt for contextual similarity evaluation
        prompt = f"""
        Evaluate the contextual similarity between the following two texts and provide a similarity score between 0 and 100:
        
        Resume:
        {resume_text}
        
        Job Description:
        {job_description}
        
        Provide only the similarity score as a number between 0 - 100.
        """
        model = genai.GenerativeModel('gemini-2.0-flash-lite')
        response = model.generate_content(prompt)
        return float(response.text.strip())
    except Exception as e:
        print(f"Error calculating contextual similarity score: {e}")
        return 0

def format_name(raw_name):
    """
    Format the raw name by removing underscores and unique identifiers.
    """
    try:
        # Check if the name contains an underscore
        if '_' in raw_name:
            # Split by the last underscore to preserve compound names
            name_parts = raw_name.rsplit('_', 1)
            
            # If the last part looks like a UUID (alphanumeric and 8 chars), remove it
            if len(name_parts) > 1 and len(name_parts[1]) == 8 and name_parts[1].isalnum():
                formatted_name = name_parts[0]
            else:
                # If it doesn't look like a UUID, join with space
                formatted_name = ' '.join(name_parts)
                
            return formatted_name.title()
        else:
            # If no underscore, just return the name as is
            return raw_name.title()
    except Exception as e:
        print(f"Error formatting name: {e}")
        return raw_name
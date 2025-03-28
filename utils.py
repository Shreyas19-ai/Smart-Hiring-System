from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import google.generativeai as genai

def calculate_similarity_score(resume_text, job_description):
    """
    Calculate the similarity score between a resume and a job description using TF-IDF and cosine similarity.
    """
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([job_description, resume_text])
        similarity_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0] * 100
        return round(similarity_score, 2)
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
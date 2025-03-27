from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
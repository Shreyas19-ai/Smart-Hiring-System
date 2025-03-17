import PyPDF2 as pdf

def input_pdf_text(uploaded_file):
    reader = pdf.PdfReader(uploaded_file)
    text = "".join([page.extract_text() or "" for page in reader.pages])
    return text.strip()
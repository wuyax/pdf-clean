# python-sidecar/src/scanner.py
import fitz
import re
import os

def classify_pdf(file_path: str) -> str:
    """
    Classifies a PDF file into one of four categories:
    - TYPE_1: Normal PDF (Valid text layer) -> DO NOT AUTO-SELECT
    - TYPE_2: Decoy/Hidden Text PDF -> AUTO-SELECT
    - TYPE_3: PDF with valid OCR -> DO NOT AUTO-SELECT
    - TYPE_4: Pure Image PDF -> AUTO-SELECT
    """
    if not os.path.exists(file_path):
        return "TYPE_UNKNOWN"

    try:
        doc = fitz.open(file_path)
    except Exception:
        return "TYPE_UNKNOWN"

    if len(doc) == 0:
        doc.close()
        return "TYPE_UNKNOWN"
    
    # Check page 1 (or 2 if available to avoid cover images)
    page_idx = 1 if len(doc) > 1 else 0
    page = doc[page_idx]
    
    # 1. Extract raw text
    text = page.get_text("text").strip()
    
    # TYPE 4: Pure Image
    if len(text) < 10:
        doc.close()
        return "TYPE_4"
    
    # TYPE 2: Decoy Heuristics
    # Heuristic A: High ratio of non-alphanumeric characters
    # We include Chinese characters in the 'good' count
    alphanumeric = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
    
    # If the text is mostly whitespace, punctuation, or control chars, it's likely a decoy
    if len(text) > 0:
        ratio = len(alphanumeric) / len(text)
        if ratio < 0.3:
            doc.close()
            return "TYPE_2"
            
    # Heuristic B: Check for overlapping or suspicious text blocks
    # (Simplified for now: if it passes the ratio test and has significant text, 
    # we assume it's Type 1 or Type 3 which we don't need to process)
    
    doc.close()
    return "TYPE_1"

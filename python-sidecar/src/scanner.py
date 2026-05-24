# python-sidecar/src/scanner.py
import fitz
import re
import os
import numpy as np
from difflib import SequenceMatcher

def get_ocr_for_scan():
    """
    Lazy load OCR specifically for scanning. 
    We use the shared instance from processor if available.
    """
    try:
        from processor import get_ocr
        return get_ocr()
    except Exception:
        return None

def classify_pdf(file_path: str) -> str:
    """
    Classifies a PDF file into one of four categories:
    - TYPE_1: Normal PDF (Valid text layer)
    - TYPE_2: Decoy/Hidden Text PDF (Gibberish or mismatched text)
    - TYPE_3: PDF with valid OCR (Matches image content)
    - TYPE_4: Pure Image PDF (No text layer)
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
    
    # 1. Primary Check: Text Layer Content
    text = page.get_text("text").strip()
    
    # TYPE 4: Pure Image (Extremely low character count)
    if len(text) < 5:
        doc.close()
        return "TYPE_4"
    
    # 2. Fast Path: Image Density Analysis
    # Scanned PDFs or Decoy PDFs almost always consist of a page-filling background image.
    # Normal (Born-digital) PDFs usually have no background image or only small ones (logos).
    page_area = page.rect.width * page.rect.height
    has_large_background_image = False
    
    image_list = page.get_images()
    for img in image_list:
        xref = img[0]
        rects = page.get_image_rects(xref)
        for r in rects:
            # If any image covers more than 70% of the page, it's a potential scanned/decoy candidate
            if (r.width * r.height) / page_area > 0.7:
                has_large_background_image = True
                break
        if has_large_background_image:
            break
            
    # If no large background image is detected, it's highly likely a normal born-digital PDF.
    # We can skip the expensive OCR sampling.
    if not has_large_background_image:
        doc.close()
        return "TYPE_1"

    # 3. Heuristic Check: Gibberish/Decoy detection
    # Heuristic A: Ratio of meaningful characters (Alphanumeric + Chinese)
    alphanumeric = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
    
    # Decoy detection: If the text is mostly symbols or has extremely low semantic density
    if len(text) > 0:
        density = len(alphanumeric) / len(text)
        if density < 0.2:
            doc.close()
            return "TYPE_2"

    # 3. Advanced Check: Small-scale OCR Sampling (The Ultimate Truth)
    # If we have text but aren't sure if it matches the image, we do a quick OCR check
    ocr = get_ocr_for_scan()
    if ocr:
        # Get a low-DPI pixmap for fast processing
        pix = page.get_pixmap(dpi=72, alpha=False)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
        img_np = img_np[:, :, ::-1] # RGB to BGR
        
        # Run OCR
        res = ocr.ocr(img_np)
        
        if res and res[0]:
            # Extract OCR text
            text_blocks = []
            if hasattr(res[0], '__contains__') and 'rec_texts' in res[0]:
                text_blocks = res[0]['rec_texts']
            elif isinstance(res[0], list):
                text_blocks = [line[1][0] for line in res[0]]
            
            ocr_text = "".join(text_blocks)
            ocr_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', ocr_text)
            pdf_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
            
            # Advanced Semantic Comparison:
            # 1. Length ratio check
            if len(ocr_clean) > 5 and len(pdf_clean) > 5:
                len_ratio = min(len(ocr_clean), len(pdf_clean)) / max(len(ocr_clean), len(pdf_clean))
                
                # 2. Fuzzy similarity check
                sim_ratio = SequenceMatcher(None, ocr_clean, pdf_clean).ratio()
                
                # Decoy Detection:
                # If similarity is very low, or if the length mismatch is extreme, it's a decoy
                if sim_ratio < 0.25 or len_ratio < 0.2:
                    doc.close()
                    return "TYPE_2"
                
                # If similarity is high, it's a valid text/OCR PDF
                if sim_ratio > 0.8:
                    doc.close()
                    return "TYPE_3"

    doc.close()
    return "TYPE_1"

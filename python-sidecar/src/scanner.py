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
    # Scanned PDFs or Decoy PDFs almost always consist of page-filling images.
    # Normal (Born-digital) PDFs usually have no background image or only small ones (logos).
    page_area = page.rect.width * page.rect.height
    total_image_area = 0
    
    image_list = page.get_images()
    processed_xrefs = set()
    
    for img in image_list:
        xref = img[0]
        if xref in processed_xrefs: continue
        processed_xrefs.add(xref)
        
        rects = page.get_image_rects(xref)
        for r in rects:
            total_image_area += (r.width * r.height)
            
    # Refined Image Heavy definition: 
    # Normal PDFs usually have < 5% image area (just logos/icons).
    # Anything above 10% is suspicious enough to warrant deeper inspection.
    is_image_heavy = (total_image_area / page_area) > 0.10
    
    # 3. Heuristic Check: Gibberish/Decoy detection
    # Heuristic A: Ratio of meaningful characters (Alphanumeric + Chinese)
    alphanumeric = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
    
    # Decoy detection: 
    if len(text) > 0:
        density = len(alphanumeric) / len(text)
        # If it's image heavy but has very little text layer content, 
        # it's almost certainly a decoy or a poor OCR.
        if density < 0.25 or (is_image_heavy and len(text) < 300):
            doc.close()
            return "TYPE_2"

    # 4. Advanced Check: Small-scale OCR Sampling (The Ultimate Truth)
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
            if len(ocr_clean) > 5:
                # 1. Length ratio check: If OCR found 5x more text than the PDF layer, it's a decoy.
                # 2. Fuzzy similarity check: If the small amount of text doesn't match the OCR.
                len_ratio = len(pdf_clean) / len(ocr_clean)
                sim_ratio = SequenceMatcher(None, ocr_clean, pdf_clean).ratio()
                
                # Decoy Detection:
                if sim_ratio < 0.35 or len_ratio < 0.3:
                    doc.close()
                    return "TYPE_2"
                
                # If similarity is high, it's a valid text/OCR PDF
                if sim_ratio > 0.8:
                    doc.close()
                    return "TYPE_3"

    doc.close()
    return "TYPE_1"

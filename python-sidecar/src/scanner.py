# python-sidecar/src/scanner.py
import fitz
import re
import os
import numpy as np
from difflib import SequenceMatcher

def get_ocr_for_scan():
    try:
        from processor import get_ocr
        return get_ocr()
    except Exception:
        return None

def classify_pdf(file_path: str) -> str:
    """
    Advanced PDF Classification based on structural fingerprints:
    - TYPE_1: Normal PDF (Natural text or Mixed layout)
    - TYPE_2: Decoy/Hidden Text PDF (Sliced images + sparse/mismatched text)
    - TYPE_3: Valid OCR (Image-based but text layer correctly represents pixels)
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
    
    # Analyze Page 1 (or 2)
    page_idx = 0
    if len(doc) > 1:
        # Check if page 1 is just a large cover image
        p1_imgs = doc[0].get_images()
        if len(p1_imgs) == 1:
            page_idx = 1 # Better check page 2 for structure
            
    page = doc[page_idx]
    rect = page.rect
    page_area = rect.width * rect.height
    
    # --- 1. Structural Analysis (Physical Fingerprints) ---
    image_list = page.get_images()
    num_images = len(image_list)
    
    total_img_area = 0
    unique_xrefs = set()
    for img in image_list:
        xref = img[0]
        if xref not in unique_xrefs:
            unique_xrefs.add(xref)
            img_rects = page.get_image_rects(xref)
            for r in img_rects:
                total_img_area += (r.width * r.height)
                
    img_coverage = total_img_area / page_area
    text = page.get_text("text").strip()
    
    # Pure Image Check
    if len(text) < 10 and img_coverage > 0.5:
        doc.close()
        return "TYPE_4"

    # --- 2. Quick Path (Normal Document Heuristics) ---
    # Case A: Natural Document - Low image count, standard layout
    if num_images < 15 and img_coverage < 0.3:
        doc.close()
        return "TYPE_1"
    
    # Case B: Standard Certificate/Poster - One big image + some text
    if num_images < 5 and img_coverage > 0.8:
        # We'll still do a quick similarity check below to be sure it's not a scanned decoy
        pass

    # --- 3. Deep Verification (OCR Sampling) ---
    # Triggered if image count is high (Slicing behavior) or coverage is high
    is_suspiciously_sliced = num_images > 25
    is_image_heavy = img_coverage > 0.4
    
    if is_suspiciously_sliced or is_image_heavy:
        ocr = get_ocr_for_scan()
        if ocr:
            # Low-DPI scan for speed
            pix = page.get_pixmap(dpi=72, alpha=False)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).copy()
            img_np = img_np[:, :, ::-1] 
            
            res = ocr.ocr(img_np)
            if res and res[0]:
                text_blocks = []
                if hasattr(res[0], '__contains__') and 'rec_texts' in res[0]:
                    text_blocks = res[0]['rec_texts']
                elif isinstance(res[0], list):
                    text_blocks = [line[1][0] for line in res[0]]
                
                ocr_text = "".join(text_blocks)
                ocr_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', ocr_text)
                pdf_clean = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
                
                if len(ocr_clean) > 5:
                    len_ratio = len(pdf_clean) / len(ocr_clean)
                    sim_ratio = SequenceMatcher(None, ocr_clean, pdf_clean).ratio()
                    
                    # LOGIC:
                    # If it's a decoy:
                    # - Many images (Slicing) AND (Low similarity OR extreme length mismatch)
                    if is_suspiciously_sliced and (sim_ratio < 0.3 or len_ratio < 0.4):
                        doc.close()
                        return "TYPE_2"
                    
                    # If similarity is very low even without slicing (normal scanned decoy)
                    if sim_ratio < 0.2 or len_ratio < 0.2:
                        doc.close()
                        return "TYPE_2"
                        
                    # If similarity is high, it's valid (Normal text or good OCR)
                    if sim_ratio > 0.7:
                        doc.close()
                        return "TYPE_3"
                elif len(pdf_clean) > 20:
                    # OCR detected almost nothing (<= 5 chars) but the PDF text layer has significant text (> 20 chars).
                    # This indicates hidden/decoy text on an image.
                    doc.close()
                    return "TYPE_2"

    # Default to TYPE_1 for all other natural/mixed documents
    doc.close()
    return "TYPE_1"

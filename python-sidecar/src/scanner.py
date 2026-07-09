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

def _classify_page(doc, page_idx: int) -> str:
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
                
    img_coverage = total_img_area / page_area if page_area > 0 else 0
    text = page.get_text("text").strip()
    
    # Pure Image Check
    if len(text) < 10 and img_coverage > 0.5:
        return "TYPE_4"

    # --- 2. Quick Path (Normal Document Heuristics) ---
    # Case A: Natural Document - Low image count, standard layout
    if num_images < 15 and img_coverage < 0.3:
        return "TYPE_1"

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
            
            ocr_res = ocr(img_np)
            if ocr_res is not None:
                results, elapse = ocr_res
                text_blocks = []
                if results:
                    for line in results:
                        if isinstance(line, (list, tuple)) and len(line) > 1 and line[1]:
                            text_blocks.append(str(line[1]))
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
                        return "TYPE_2"
                    
                    # If similarity is very low even without slicing (normal scanned decoy)
                    if sim_ratio < 0.2 or len_ratio < 0.2:
                        return "TYPE_2"
                        
                    # If similarity is high, it's valid (Normal text or good OCR)
                    if sim_ratio > 0.7:
                        return "TYPE_3"
                elif len(pdf_clean) > 20:
                    # OCR detected almost nothing (<= 5 chars) but the PDF text layer has significant text (> 20 chars).
                    # This indicates hidden/decoy text on an image.
                    return "TYPE_2"

    # Default to TYPE_1 for all other natural/mixed documents
    return "TYPE_1"

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
        with fitz.open(file_path) as doc:
            if doc.is_encrypted:
                return "TYPE_ENCRYPTED"
            if len(doc) == 0:
                return "TYPE_UNKNOWN"
                
            # 采样前、中、后最多3页
            page_indices = sorted(list(set([0, len(doc) // 2, len(doc) - 1])))
            page_types = []
            
            for idx in page_indices:
                try:
                    page_types.append(_classify_page(doc, idx))
                except Exception as e:
                    print(f"Error scanning page {idx}: {e}")
                    
            if not page_types:
                return "TYPE_UNKNOWN"
                
            # 聚合策略：
            # 1. 任何一页有干扰，整份文档定为 TYPE_2
            if "TYPE_2" in page_types:
                return "TYPE_2"
            # 2. 如果全都是纯图片，才是 TYPE_4
            if all(t == "TYPE_4" for t in page_types):
                return "TYPE_4"
            # 3. 如果包含 TYPE_4 但还有其他文字页，归类为 TYPE_1 混合文档
            if "TYPE_4" in page_types:
                return "TYPE_1"
            # 4. 如果有 TYPE_3 且其余都是 TYPE_1，归为 TYPE_3
            if "TYPE_3" in page_types:
                return "TYPE_3"
                
            return "TYPE_1"
    except Exception as e:
        print(f"Error classifying {file_path}: {e}")
        return "TYPE_UNKNOWN"

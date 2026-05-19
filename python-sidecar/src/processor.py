import os

# 1. Mandatory Environment Variables
os.environ["FLAGS_allocator_strategy"] = "auto_growth"
os.environ["FLAGS_eager_delete_tensor_gb"] = "0.0"
os.environ["OMP_NUM_THREADS"] = "1"

import fitz  # PyMuPDF
import numpy as np
import gc

# Global OCR instance
ocr_instance = None

def get_ocr():
    global ocr_instance
    if ocr_instance is not None:
        return ocr_instance
        
    try:
        from paddleocr import PaddleOCR
        print("Initializing PaddleOCR 3.5.0 Engine...")
        # In 3.5.0, many old arguments (use_gpu, enable_mkldnn) are removed or handled differently.
        # We only pass the absolutely necessary and supported arguments.
        ocr_instance = PaddleOCR(
            use_angle_cls=True, 
            lang="ch"
        )
        return ocr_instance
    except Exception as e:
        print(f"OCR initialization failed: {e}")
        return None

def process_pdf(input_path: str, output_path: str):
    ocr = get_ocr()
    if ocr is None:
        raise Exception("OCR Engine could not be initialized. Check backend logs.")

    print(f"Dual-Res Processing: {input_path}")
    
    doc_src = fitz.open(input_path)
    doc_out = fitz.open()
    
    try:
        for page_num in range(len(doc_src)):
            print(f"--- Page {page_num + 1}/{len(doc_src)} ---")
            
            try:
                page_src = doc_src[page_num]
                
                # 1. HIGH-RES BACKGROUND (200 DPI)
                # Used only for the visible PDF background to maintain visual quality
                pix_bg = page_src.get_pixmap(dpi=200)
                img_data = pix_bg.tobytes("jpg")
                
                # 2. LOW-RES OCR INPUT (100 DPI)
                # This is the secret to stopping the 20GB memory explosion!
                # By giving PaddleOCR a smaller image, its internal matrices stay small.
                pix_ocr = page_src.get_pixmap(dpi=100)
                
                img_np = np.frombuffer(pix_ocr.samples, dtype=np.uint8).reshape(pix_ocr.height, pix_ocr.width, 3).copy()
                img_np = img_np[:, :, ::-1] # RGB to BGR
                
                # Run OCR on the small image
                result = ocr.ocr(img_np)
                
                # Build output using High-Res dimensions
                page_out = doc_out.new_page(width=pix_bg.width, height=pix_bg.height)
                page_out.insert_image(fitz.Rect(0, 0, pix_bg.width, pix_bg.height), stream=img_data)
                
                # Calculate exact scale factors for both axes to prevent compounding errors
                scale_x = pix_bg.width / pix_ocr.width
                scale_y = pix_bg.height / pix_ocr.height
                
                # ... [OCR keys log omitted here, keep it below]
                print(f"  Raw OCR Result Keys: {type(result[0])} {result[0].keys() if isinstance(result[0], dict) else 'Not a dict'}")
                
                # Try to extract the actual text blocks list
                text_blocks = []
                
                # Check for the keys we saw in the logs ('rec_texts' plural, not singular)
                if hasattr(result[0], '__contains__'): 
                    if 'dt_polys' in result[0] and 'rec_texts' in result[0]:
                        polys = result[0]['dt_polys']
                        texts = result[0]['rec_texts']
                        
                        try:
                            scores = result[0]['rec_scores']
                        except KeyError:
                            scores = [1.0] * len(texts)
                            
                        for p, t, s in zip(polys, texts, scores):
                            text_blocks.append([p, (t, s)])
                    elif 'res' in result[0]: 
                        text_blocks = result[0]['res']
                elif isinstance(result[0], list):
                    text_blocks = result[0]

                if text_blocks:
                    print(f"  Detected {len(text_blocks)} text lines.")
                    for i, line in enumerate(text_blocks):
                        try:
                            if i == 0:
                                print(f"    Sample block structure: {line}")
                                
                            box = line[0]
                            text_data = line[1]
                            
                            if isinstance(text_data, (tuple, list)):
                                text = str(text_data[0])
                                conf = float(text_data[1])
                            else:
                                text = str(text_data)
                                conf = 1.0 
                                
                            if conf < 0.3: continue
                            
                            # Scale the coordinates up independently for X and Y
                            scaled_box = []
                            for pt in box:
                                x = float(pt[0]) * scale_x
                                y = float(pt[1]) * scale_y
                                scaled_box.append([x, y])
                                
                            rect = fitz.Quad(scaled_box).rect
                            
                            # Draw blue outline for debug
                            page_out.draw_rect(rect, color=(0, 0, 1), width=1)
                            
                            # Revert to insert_text: insert_textbox silently fails if the text is even 1 pixel too wide.
                            # We reduce the font size to 65% of the box height to prevent horizontal/vertical overflow.
                            # We shift the Y coordinate up slightly (approx 20% of height) to align the baseline.
                            fs = max(1, rect.height * 0.65)
                            baseline_pt = fitz.Point(rect.x0, rect.y1 - (rect.height * 0.20))
                            
                            try:
                                page_out.insert_text(
                                    baseline_pt, 
                                    text, 
                                    fontname="china-ss", 
                                    fontsize=fs, 
                                    color=(1, 0, 0), # Red text
                                    render_mode=0
                                )
                            except Exception as font_e:
                                page_out.insert_text(
                                    baseline_pt, 
                                    text, 
                                    fontsize=fs,
                                    color=(1, 0, 0),
                                    render_mode=0
                                )
                                
                        except Exception as e:
                            print(f"    Error processing line: {e}")
                            continue
                
                # Release memory immediately
                del img_np
                del img_data
                pix_bg = None
                pix_ocr = None
                gc.collect()
                
            except Exception as e:
                print(f"  Page {page_num} Error: {e}")
                continue
        
        print("Saving PDF...")
        doc_out.save(output_path, garbage=4, deflate=True)
        
    finally:
        doc_src.close()
        doc_out.close()
        gc.collect()
        
    return output_path

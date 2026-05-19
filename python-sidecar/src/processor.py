import os
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import fitz  # PyMuPDF
import io
import numpy as np

# Initialize OCR once (use English and Chinese)
# Loading the models here avoids 5-10s delay per request
ocr = PaddleOCR(use_angle_cls=True, lang="ch")

def process_pdf(input_path: str, output_path: str):
    # 1. Rasterize PDF to images
    images = convert_from_path(input_path, dpi=300)
    
    # 2. Create a new empty PDF
    doc = fitz.open()
    
    for page_num, img in enumerate(images):
        try:
            # Save image to bytes
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="JPEG")
            img_bytes = img_bytes.getvalue()
            
            img_np = np.array(img)
            result = ocr.ocr(img_np, cls=True)
            
            width, height = img.size
            page = doc.new_page(width=width, height=height)
            
            rect = fitz.Rect(0, 0, width, height)
            page.insert_image(rect, stream=img_bytes)
            
            if result and result[0]:
                for line in result[0]:
                    box = line[0]
                    text = line[1][0]
                    p0 = box[0]
                    p2 = box[2]
                    text_rect = fitz.Rect(p0[0], p0[1], p2[0], p2[1])
                    # render_mode=3 makes text invisible but selectable
                    page.insert_textbox(text_rect, text, color=(0,0,0), render_mode=3)
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            # Continue to next page or re-raise? 
            # For robustness, we try to finish the rest of the PDF
            continue
                
    doc.save(output_path)
    doc.close()
    return output_path

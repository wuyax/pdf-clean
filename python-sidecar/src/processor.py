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
        # CRITICAL: Disable document unwarping and orientation classify, otherwise 3.5.0 will warp
        # the image matrix and the returned OCR coordinates will NOT match the original PDF!
        ocr_instance = PaddleOCR(
            use_textline_orientation=True,
            use_doc_unwarping=False,
            use_doc_orientation_classify=False,
            lang="ch"
        )
        return ocr_instance
    except Exception as e:
        print(f"OCR initialization failed: {e}")
        return None

def insert_character_level_text(page, rect, text, fontname="china-ss", render_mode=3, color=(0, 0, 0), fill_opacity=1.0):
    """
    单字级精准定位文本插入函数（防止累计偏移，完美对齐划选框）
    """
    n = len(text)
    if n == 0:
        return
    
    # 更精细的字符宽度估算：PaddleOCR 给出的 bounding box 是紧贴文字的
    weights = []
    for char in text:
        if ord(char) > 127:
            weights.append(1.0) # 中文/全角字符
        elif char.isupper():
            weights.append(0.65) # 大写英文字母
        elif char.islower() or char.isdigit():
            weights.append(0.5) # 小写字母或数字
        else:
            weights.append(0.4) # 标点符号/空格
            
    total_units = sum(weights)
    if total_units == 0:
        total_units = n
        weights = [1.0] * n
        
    unit_width = rect.width / total_units
    
    # 调整字号：既然坐标已经完美对齐原图，我们可以把字号放大到更接近真实高度。
    # 设定为矩形高度的 95%
    fs = rect.height * 0.95
    if fs < 1:
        fs = 1
        
    # 垂直居中对齐逻辑：
    # PyMuPDF 插入文本的原点是字体的基线（Baseline）。
    # 对于大多数中文字体，基线上方(ascent)约占 fs*0.8，下方(descent)约占 fs*0.2。
    # 为了让文字在 rect 中垂直居中，基线位置应在矩形中心点往下约 fs*0.35 的位置。
    center_y = (rect.y0 + rect.y1) / 2
    baseline_y = center_y + (fs * 0.35)
    
    current_x = rect.x0
    for char, w in zip(text, weights):
        char_width = w * unit_width
        baseline_pt = fitz.Point(current_x, baseline_y)
        
        try:
            page.insert_text(
                baseline_pt, 
                char, 
                fontname=fontname, 
                fontsize=fs, 
                color=color, 
                fill_opacity=fill_opacity,
                render_mode=render_mode
            )
        except Exception:
            page.insert_text(
                baseline_pt, 
                char, 
                fontsize=fs, 
                color=color, 
                fill_opacity=fill_opacity,
                render_mode=render_mode
            )
            
        current_x += char_width

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
                
                # 0. Get true physical dimensions of the original PDF page in Points (72 DPI)
                rect_pts = page_src.rect
                
                # 1. HIGH-RES BACKGROUND (200 DPI)
                # alpha=False is CRITICAL to ensure 3-channel RGB. Otherwise it might be RGBA
                pix_bg = page_src.get_pixmap(dpi=200, alpha=False)
                img_data = pix_bg.tobytes("jpg")
                
                # 2. LOW-RES OCR INPUT (100 DPI)
                # alpha=False is CRITICAL! If a PDF has alpha, reshape(h, w, 3) will horribly skew the image,
                # causing OCR coordinates to be completely offset.
                pix_ocr = page_src.get_pixmap(dpi=100, alpha=False)
                
                img_np = np.frombuffer(pix_ocr.samples, dtype=np.uint8).reshape(pix_ocr.height, pix_ocr.width, 3).copy()
                img_np = img_np[:, :, ::-1] # RGB to BGR
                
                # Run OCR on the small image
                result = ocr.ocr(img_np)
                
                # Build output using EXACT original PDF points size to prevent oversized documents
                page_out = doc_out.new_page(width=rect_pts.width, height=rect_pts.height)
                
                # Insert background image spanning the exact physical points dimensions
                # keep_proportion=False is CRITICAL here to prevent PyMuPDF from auto-centering
                # due to minor rounding differences in pixel aspect ratios, which causes coordinate offsets.
                page_out.insert_image(rect_pts, stream=img_data, keep_proportion=False)
                
                # Calculate exact scale factors mapping from 100 DPI pixels directly to PDF Points!
                scale_x = rect_pts.width / pix_ocr.width
                scale_y = rect_pts.height / pix_ocr.height
                
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
                            
                            # 使用单字符级精确定位函数，避免累计字宽偏移，启用隐藏文本（render_mode=3）
                            insert_character_level_text(
                                page=page_out,
                                rect=rect,
                                text=text,
                                fontname="china-ss",
                                render_mode=3
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

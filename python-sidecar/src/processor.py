import os

# 1. 优化内存管理和减少多线程冲突的环境变量
os.environ["OMP_NUM_THREADS"] = "1"

import fitz  # PyMuPDF, 用于 PDF 读写和渲染
import numpy as np
import gc
from PIL import Image
import io

# 全局单例的 OCR 引擎实例，避免每处理一页就重新加载模型
ocr_instance = None

def get_ocr():
    """
    懒加载并返回 RapidOCR 实例。
    """
    global ocr_instance
    if ocr_instance is not None:
        return ocr_instance
    try:
        import sys
        from rapidocr_onnxruntime import RapidOCR
        model_dir = os.environ.get("MODEL_DIR") or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "models")
        )
        
        # Verify model files exist
        models_exist = all(
            os.path.exists(os.path.join(model_dir, f))
            for f in ["det.onnx", "rec.onnx", "cls.onnx"]
        )
        if not models_exist:
            if getattr(sys, 'frozen', False):
                print(f"CRITICAL ERROR: OCR ONNX models are missing in packaged app resources! Path searched: {model_dir}", file=sys.stderr)
                return None
            else:
                print("ONNX models not found in local models directory. Attempting automatic download for development...")
                try:
                    # Add parent directory of source code to path to allow importing download_models
                    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
                    from download_models import download_models
                    download_models()
                except Exception as dl_err:
                    print(f"Automatic model download failed: {dl_err}", file=sys.stderr)
                    return None

        print(f"Initializing RapidOCR Engine with models from: {model_dir}")
        ocr_instance = RapidOCR(
            det_model_path=os.path.join(model_dir, "det.onnx"),
            rec_model_path=os.path.join(model_dir, "rec.onnx"),
            cls_model_path=os.path.join(model_dir, "cls.onnx")
        )
        return ocr_instance
    except Exception as e:
        print(f"OCR initialization failed: {e}", file=sys.stderr)
        return None

def insert_character_level_text(page, rect, text, fontname="china-ss", render_mode=3, color=(0, 0, 0), fill_opacity=1.0):
    """
    单字级精准定位文本插入函数。
    由于 PyMuPDF 自带的 insert_textbox 在中英文混排、字体度量上容易产生累积的宽度偏移，
    此函数通过估算每个字符的相对权重，计算出每个字符应该占据的宽度，
    并逐个字符计算精准基线进行插入，从而实现文字与底层图片的完美对齐，方便高亮框选。
    """
    n = len(text)
    if n == 0:
        return
    
    # 估算每个字符的相对宽度权重，PaddleOCR 给出的 bounding box 是紧贴文字的。
    weights = []
    for char in text:
        if ord(char) > 127:
            weights.append(1.0)  # 中文/全角字符，占全宽
        elif char.isupper():
            weights.append(0.65) # 大写英文字母
        elif char.islower() or char.isdigit():
            weights.append(0.5)  # 小写字母或数字
        else:
            weights.append(0.4)  # 标点符号/空格
            
    total_units = sum(weights)
    if total_units == 0:
        total_units = n
        weights = [1.0] * n
        
    # 计算每一个单位权重在真实物理坐标中所代表的宽度
    unit_width = rect.width / total_units
    
    # 【字号设置】：
    # 既然我们已经完美对齐了 OCR 坐标到 PDF 物理坐标，我们可以把字号放大到几乎填满边界框。
    # 设定为矩形高度的 95%，预留 5% 防止极端情况下溢出。
    fs = max(1.0, rect.height * 0.95)
        
    # 【基线(Baseline)计算】：
    # 垂直居中对齐逻辑：PyMuPDF 插入文本的 Y 轴坐标原点是字体的基线，而不是矩形的左上角。
    # 对于大多数中文字体，基线上方(ascent)约占整体字高的 80%，下方(descent)约占 20%。
    # 为了让文字在识别框中绝对垂直居中，基线位置应设定在矩形垂直中点往下偏移 `fs * 0.35` 的位置。
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
            try:
                # 尝试二级回退：使用简体的内置 CJK 字体 china-s
                page.insert_text(
                    baseline_pt, 
                    char, 
                    fontname="china-s",
                    fontsize=fs, 
                    color=color, 
                    fill_opacity=fill_opacity,
                    render_mode=render_mode
                )
            except Exception:
                # 三级终极回退：无字体模式
                page.insert_text(
                    baseline_pt, 
                    char, 
                    fontsize=fs, 
                    color=color, 
                    fill_opacity=fill_opacity,
                    render_mode=render_mode
                )
            
        current_x += char_width

def process_pdf(input_path: str, output_path: str, progress_callback=None, dpi: int = 300, quality: int = 85):
    """
    主处理流程：
    1. 将 PDF 页面渲染为高分辨率(200 DPI)图片用于背景。
    2. 将 PDF 页面渲染为低分辨率(100 DPI)图片，传给 PaddleOCR 进行文字识别，大幅降低内存消耗。
    3. 构建新 PDF，贴入高分背景图，并利用 OCR 返回的坐标写入无色文字透明层。
    """
    ocr = get_ocr()
    if ocr is None:
        raise Exception("OCR Engine could not be initialized. Check backend logs.")

    print(f"Dual-Res Processing: {input_path}")
    
    doc_src = fitz.open(input_path)
    if doc_src.is_encrypted:
        raise ValueError("该 PDF 文件受密码保护或已被加密，请解密后重试。")
    total_pages = len(doc_src)
    doc_out = fitz.open()
    
    try:
        for page_num in range(total_pages):
            current_page_display = page_num + 1
            print(f"--- Page {current_page_display}/{total_pages} ---")
            
            if progress_callback:
                # 使用 page_num (从0开始) 代表“已经完成的页数”
                # 这样对于 1/1 的情况，进度条会停留在 0% 直到全部完成跳转到“已优化”
                progress_callback(page_num, total_pages, f"正在处理第 {current_page_display}/{total_pages} 页...")
            
            try:
                page_src = doc_src[page_num]
                
                # 0. 获取原始 PDF 页面真实的物理尺寸 (单位为 Points，即 72 DPI 下的尺寸)
                rect_pts = page_src.rect
                
                # 1. 【高分辨率背景图】 (300 DPI)
                # 这张图作为最终输出 PDF 的可见底层。300 DPI 是清晰度与体积的最佳平衡点。
                # 【极其重要】：alpha=False 强制丢弃透明通道。强制 colorspace=fitz.csRGB 确保灰度图也是 3 通道。
                pix_bg = page_src.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
                
                # 使用 PIL 进行高级 JPEG 压缩 (TinyJPG 风格)
                img_pil = Image.frombytes("RGB", [pix_bg.width, pix_bg.height], pix_bg.samples)
                img_bytes_io = io.BytesIO()
                img_pil.save(
                    img_bytes_io, 
                    format="JPEG", 
                    quality=quality, 
                    optimize=True, 
                    progressive=True,
                    subsampling=0 # 4:4:4 保持文字边缘锐利
                )
                img_data = img_bytes_io.getvalue()
                
                # 2. 【低分辨率 OCR 输入图】 (100 DPI)
                # 采用 100 DPI 极大减小了交给 PaddleOCR 处理的图像尺寸，这是解决 20GB 内存溢出导致程序崩溃的秘诀！
                # 【极其重要】：必须设置 alpha=False。如果源 PDF 含有 Alpha 通道，
                # 下方的 reshape(h, w, 3) 强转会直接把 4 通道的 RGBA 数据搓烂，导致图像扭曲斜边撕裂，OCR 坐标全部错位。
                # 强制 colorspace=fitz.csRGB 确保灰度图也是 3 通道。
                pix_ocr = page_src.get_pixmap(dpi=100, colorspace=fitz.csRGB, alpha=False)
                
                # 从内存字节流构建 numpy 矩阵，并将 RGB 转换为 BGR 给 PaddleOCR 使用
                img_np = np.frombuffer(pix_ocr.samples, dtype=np.uint8).reshape(pix_ocr.height, pix_ocr.width, 3).copy()
                img_np = img_np[:, :, ::-1] 
                
                # 在低分小图上执行 OCR 识别
                ocr_res = ocr(img_np)
                if ocr_res is not None:
                    result, elapse = ocr_res
                else:
                    result = None
                
                # 使用原始 PDF 精确的物理坐标尺寸 (Points) 创建新页面，防止生成的 PDF 版面被无端放大
                page_out = doc_out.new_page(width=rect_pts.width, height=rect_pts.height)
                
                # 将高分辨率的图片贴回物理尺寸的框内。
                # 【极其重要】：keep_proportion=False 必须设置。
                # 因为像素 DPI 缩放后的长宽比可能会有极微小的舍入误差，如果保持比例，PyMuPDF 会自作聪明地
                # 让图片在页面内居中，这会产生位移，导致我们后续计算的绝对文字坐标套不准底图。
                page_out.insert_image(rect_pts, stream=img_data, keep_proportion=False)
                
                # 精准计算从 100 DPI 像素坐标 -> 目标 PDF 物理 Points 坐标 的缩放映射比例！
                scale_x = rect_pts.width / pix_ocr.width
                scale_y = rect_pts.height / pix_ocr.height
                
                if result:
                    print(f"  Raw OCR Result length: {len(result)}")
                
                # 提取 OCR 返回的文字块列表
                text_blocks = result if result else []

                if text_blocks:
                    print(f"  Detected {len(text_blocks)} text lines.")
                    for i, line in enumerate(text_blocks):
                        try:
                            if i == 0:
                                print(f"    Sample block structure: {line}")
                                
                            box = line[0]
                            text = str(line[1])
                            conf = float(line[2])
                                
                            # 剔除置信度低于 0.3 的垃圾识别结果
                            if conf < 0.3: continue
                            
                            # 对识别框的四个顶点分别应用缩放比例，将其转换回 PDF 的物理 Points 坐标
                            scaled_box = []
                            for pt in box:
                                x = float(pt[0]) * scale_x
                                y = float(pt[1]) * scale_y
                                scaled_box.append([x, y])
                                
                            # 将多边形顶点转化为规则矩形 (Rect)
                            rect = fitz.Quad(scaled_box).rect
                            
                            # 使用单字符级精确定位函数注入文本。
                            # 设置 render_mode=3 意味着文本完全透明不可见，但用户可以在 PDF 阅读器中完美高亮框选和复制它。
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
                
                # 每处理完一页，立即显式释放 NumPy 矩阵和字节流内存，并执行垃圾回收，
                # 防止处理长篇 PDF 时发生内存泄漏。
                del img_np
                del img_data
                pix_bg = None
                pix_ocr = None
                gc.collect()
                
            except Exception as e:
                print(f"  Page {page_num} Error: {e}, falling back to original page copy.")
                try:
                    # 拷贝原 PDF 页面至输出 PDF，保留原样
                    doc_out.insert_pdf(doc_src, from_page=page_num, to_page=page_num)
                except Exception as fallback_err:
                    print(f"  Failed to insert original page fallback: {fallback_err}")
        
        print("Saving PDF...")
        # garbage=4 (最大程度压缩清理无用对象), deflate=True (开启流压缩)
        doc_out.save(output_path, garbage=4, deflate=True)
        
    finally:
        # 确保在使用完毕后，无论是否抛出异常都安全关闭文档句柄
        doc_src.close()
        doc_out.close()
        gc.collect()
        
    return output_path

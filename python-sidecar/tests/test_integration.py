import os
import sys
import pytest
import fitz

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_real_pdf_processing_integration(tmp_path):
    # Temporarily restore real rapidocr_onnxruntime to instantiate the engine
    saved_mock = sys.modules.get('rapidocr_onnxruntime')
    
    try:
        # Unmock rapidocr_onnxruntime if it is mocked
        if saved_mock is not None:
            if not hasattr(saved_mock, '__file__') or 'mock' in str(type(saved_mock)).lower():
                del sys.modules['rapidocr_onnxruntime']
        
        # Instantiate real RapidOCR
        from rapidocr_onnxruntime import RapidOCR
        from src import processor
        
        # Instantiate the real OCR engine
        model_dir = os.environ.get("MODEL_DIR") or os.path.abspath(
            os.path.join(os.path.dirname(processor.__file__), "..", "models")
        )
        real_ocr = RapidOCR(
            det_model_path=os.path.join(model_dir, "det.onnx"),
            rec_model_path=os.path.join(model_dir, "rec.onnx"),
            cls_model_path=os.path.join(model_dir, "cls.onnx")
        )
        
        # Inject the real OCR engine directly into processor's global ocr_instance
        processor.ocr_instance = real_ocr
        if 'processor' in sys.modules:
            sys.modules['processor'].ocr_instance = real_ocr
            
    finally:
        # Restore the mock back to sys.modules so other tests don't break
        if saved_mock is not None:
            sys.modules['rapidocr_onnxruntime'] = saved_mock

    # Import process_pdf from src.processor
    from src.processor import process_pdf

    # 定位根目录的测试 PDF 文件
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
    input_pdf = os.path.join(project_root, "test_plain_text.pdf")
    
    assert os.path.exists(input_pdf), f"Sample PDF not found at {input_pdf}"
    
    output_pdf = os.path.join(tmp_path, "output_clean.pdf")
    
    # 执行真实的 PDF 处理与 OCR
    result = process_pdf(input_pdf, output_pdf)
    
    # 验证返回路径
    assert result == output_pdf
    assert os.path.exists(output_pdf)
    assert os.path.getsize(output_pdf) > 0
    
    # 读取输出并校验结构
    doc_in = fitz.open(input_pdf)
    doc_out = fitz.open(output_pdf)
    
    try:
        assert len(doc_in) == len(doc_out)
        # 读取第一页
        page = doc_out[0]
        text = page.get_text().strip()
        
        # 确保能从中提取出有效的文本字符
        assert len(text) > 0
    finally:
        doc_in.close()
        doc_out.close()

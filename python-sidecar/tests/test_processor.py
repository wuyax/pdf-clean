import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock rapidocr_onnxruntime to prevent ModuleNotFoundError
sys.modules['rapidocr_onnxruntime'] = MagicMock()

from src.processor import process_pdf

@patch('src.processor.fitz')
@patch('src.processor.get_ocr')
def test_process_pdf(mock_get_ocr, mock_fitz, tmp_path):
    # Arrange
    mock_ocr = MagicMock()
    mock_get_ocr.return_value = mock_ocr
    results = [[[[0, 0], [10, 0], [10, 10], [0, 10]], 'test', 0.99]]
    mock_ocr.return_value = (results, 0.1)
    
    mock_doc = MagicMock()
    mock_doc.is_encrypted = False
    mock_fitz.open.return_value = mock_doc
    mock_doc.__len__.return_value = 1
    
    mock_page = MagicMock()
    mock_doc.__getitem__.return_value = mock_page
    mock_page.rect = MagicMock(width=500, height=800)
    
    # Mock PyMuPDF get_pixmap
    mock_pix = MagicMock()
    mock_pix.width = 100
    mock_pix.height = 100
    mock_pix.samples = b'\x00' * (100 * 100 * 3) # Mock RGB bytes
    mock_page.get_pixmap.return_value = mock_pix
    
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_text("dummy")
    output_pdf = tmp_path / "output.pdf"
    
    # Act
    result = process_pdf(str(input_pdf), str(output_pdf))
    
    # Assert
    assert result == str(output_pdf)
    mock_get_ocr.assert_called_once()
    mock_ocr.assert_called_once()
    mock_doc.save.assert_called_once()

@patch('src.processor.fitz')
@patch('src.processor.get_ocr')
def test_process_pdf_custom_dpi_quality(mock_get_ocr, mock_fitz, tmp_path):
    mock_ocr = MagicMock()
    mock_get_ocr.return_value = mock_ocr
    mock_ocr.return_value = (None, 0.1)
    mock_doc = MagicMock()
    mock_doc.is_encrypted = False
    mock_fitz.open.return_value = mock_doc
    mock_doc.__len__.return_value = 1
    mock_page = MagicMock()
    mock_doc.__getitem__.return_value = mock_page
    mock_page.rect = MagicMock(width=500, height=800)
    mock_pix = MagicMock()
    mock_pix.width = 100
    mock_pix.height = 100
    mock_pix.samples = b'\x00' * (100 * 100 * 3)
    mock_page.get_pixmap.return_value = mock_pix
    input_pdf = tmp_path / 'input.pdf'
    input_pdf.write_text('dummy')
    output_pdf = tmp_path / 'output.pdf'
    process_pdf(str(input_pdf), str(output_pdf), dpi=150, quality=75)
    mock_page.get_pixmap.assert_any_call(dpi=150, alpha=False)
    mock_page.get_pixmap.assert_any_call(dpi=100, alpha=False)

@patch('src.processor.fitz')
@patch('src.processor.get_ocr')
def test_process_pdf_encrypted(mock_get_ocr, mock_fitz, tmp_path):
    mock_ocr = MagicMock()
    mock_get_ocr.return_value = mock_ocr
    mock_doc = MagicMock()
    mock_doc.is_encrypted = True
    mock_fitz.open.return_value = mock_doc
    
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_text("dummy")
    output_pdf = tmp_path / "output.pdf"
    
    with pytest.raises(ValueError, match="该 PDF 文件受密码保护或已被加密，请解密后重试。"):
        process_pdf(str(input_pdf), str(output_pdf))

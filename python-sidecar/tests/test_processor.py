import pytest
import sys
from unittest.mock import patch, MagicMock

# Mock paddleocr to prevent ModuleNotFoundError
sys.modules['paddleocr'] = MagicMock()

from src.processor import process_pdf

@patch('src.processor.convert_from_path')
@patch('src.processor.ocr')
@patch('src.processor.fitz')
def test_process_pdf(mock_fitz, mock_ocr, mock_convert, tmp_path):
    # Arrange
    mock_img = MagicMock()
    mock_img.size = (800, 600)
    mock_convert.return_value = [mock_img] # 1 page
    
    mock_ocr.ocr.return_value = [[[[[0, 0], [10, 0], [10, 10], [0, 10]], ('test', 0.99)]]]
    
    mock_doc = MagicMock()
    mock_fitz.open.return_value = mock_doc
    
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_text("dummy")
    output_pdf = tmp_path / "output.pdf"
    
    # Act
    result = process_pdf(str(input_pdf), str(output_pdf))
    
    # Assert
    assert result == str(output_pdf)
    mock_convert.assert_called_once()
    mock_ocr.ocr.assert_called_once()
    mock_doc.save.assert_called_once()

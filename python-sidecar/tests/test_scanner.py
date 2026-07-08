# python-sidecar/tests/test_scanner.py
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from scanner import classify_pdf

@patch('os.path.exists', return_value=True)
def test_classify_pure_image(mock_exists):
    mock_doc = MagicMock()
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)
    mock_page = MagicMock()
    mock_page.get_text.return_value = "" # No text
    mock_page.rect = MagicMock(width=500, height=800)
    mock_page.get_images.return_value = [(123, 0, 500, 800, 8, 'RGB', '', 'img1', 'DCT', 0)]
    mock_page.get_image_rects.return_value = [MagicMock(width=500, height=800)]
    
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    with patch('fitz.open', return_value=mock_doc):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_4" # Pure Image

@patch('os.path.exists', return_value=True)
def test_classify_decoy_format(mock_exists):
    mock_doc = MagicMock()
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)
    mock_page = MagicMock()
    # Simulate decoy: text exists but is mostly special chars/whitespace
    mock_page.get_text.return_value = " \n!@#$%^&*()_+ \n " * 5 
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    # Mock a large background image AND slicing
    mock_page.rect = MagicMock(width=500, height=800)
    # 30 image strips to trigger "Suspiciously Sliced"
    mock_page.get_images.return_value = [(i, 0, 500, 20, 8, 'RGB', '', f'img{i}', 'DCT', 0) for i in range(30)]
    mock_page.get_image_rects.side_effect = lambda xref: [MagicMock(width=500, height=20)]

    # Mock OCR failing/returning mismatched text
    mock_ocr = MagicMock()
    results = [[[[0, 0], [10, 0], [10, 10], [0, 10]], 'completely different text', 0.99]]
    mock_ocr.return_value = (results, 0.1)
    
    # Mock pixmap rendering
    mock_pix = MagicMock()
    mock_pix.width = 100
    mock_pix.height = 100
    mock_pix.samples = b'\x00' * (100 * 100 * 3) # Mock RGB bytes
    mock_page.get_pixmap.return_value = mock_pix

    with patch('fitz.open', return_value=mock_doc), \
         patch('scanner.get_ocr_for_scan', return_value=mock_ocr):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_2" # Decoy

@patch('os.path.exists', return_value=True)
def test_classify_decoy_with_empty_ocr(mock_exists):
    mock_doc = MagicMock()
    mock_doc.__enter__ = MagicMock(return_value=mock_doc)
    mock_doc.__exit__ = MagicMock(return_value=False)
    mock_page = MagicMock()
    mock_page.get_text.return_value = "secret decoy text layer here" # 28 chars
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    mock_page.rect = MagicMock(width=500, height=800)
    # 1 image with large area to satisfy is_image_heavy
    mock_page.get_images.return_value = [(123, 0, 500, 800, 8, 'RGB', '', 'img1', 'DCT', 0)]
    mock_page.get_image_rects.return_value = [MagicMock(width=500, height=800)]

    # Mock OCR returning nothing
    mock_ocr = MagicMock()
    results = [[[[0, 0], [10, 0], [10, 10], [0, 10]], '', 0.0]]
    mock_ocr.return_value = (results, 0.1)
    
    mock_pix = MagicMock()
    mock_pix.width = 100
    mock_pix.height = 100
    mock_pix.samples = b'\x00' * (100 * 100 * 3)
    mock_page.get_pixmap.return_value = mock_pix

    with patch('fitz.open', return_value=mock_doc), \
         patch('scanner.get_ocr_for_scan', return_value=mock_ocr):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_2"

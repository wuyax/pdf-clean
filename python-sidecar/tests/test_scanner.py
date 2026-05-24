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
    mock_page = MagicMock()
    mock_page.get_text.return_value = "" # No text
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    with patch('fitz.open', return_value=mock_doc):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_4" # Pure Image

@patch('os.path.exists', return_value=True)
def test_classify_decoy_format(mock_exists):
    mock_doc = MagicMock()
    mock_page = MagicMock()
    # Simulate decoy: text exists but is mostly special chars/whitespace
    mock_page.get_text.return_value = " \n!@#$%^&*()_+ \n " * 5 
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    # Mock a large background image to avoid the TYPE_1 fast path
    mock_page.rect = MagicMock(width=500, height=800)
    mock_page.get_images.return_value = [(123, 0, 500, 800, 8, 'RGB', '', 'img1', 'DCT', 0)]
    mock_rect = MagicMock(width=500, height=800)
    mock_page.get_image_rects.return_value = [mock_rect]

    with patch('fitz.open', return_value=mock_doc):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_2" # Decoy

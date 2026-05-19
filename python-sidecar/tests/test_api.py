# python-sidecar/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Mock paddleocr to prevent ModuleNotFoundError
sys.modules['paddleocr'] = MagicMock()

# Ensure src is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("src.main.os.path.exists", return_value=True)
@patch("src.main.process_pdf")
def test_process_endpoint(mock_process, mock_exists):
    response = client.post("/process", json={"input_path": "dummy.pdf", "output_dir": "/tmp"})
    assert response.status_code == 200
    assert "task_id" in response.json()
    assert response.json()["output_path"] == "/tmp/dummy_clean.pdf"

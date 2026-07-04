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
@patch("src.main.os.path.isfile", return_value=True)
@patch("src.main.os.path.isdir", return_value=True)
@patch("src.main.process_pdf")
def test_process_endpoint(mock_process, mock_isdir, mock_isfile, mock_exists):
    response = client.post("/process", json={"input_path": "dummy.pdf", "output_dir": "/tmp"})
    assert response.status_code == 200
    assert "task_id" in response.json()
    assert response.json()["output_path"] == os.path.abspath("/tmp/dummy_clean.pdf")

def test_cors_validation():
    # Check that permitted origins work
    for origin in ["http://localhost:1420", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]:
        response = client.get("/health", headers={"Origin": origin})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == origin

    # Check that dis-allowed origins fail CORS
    response = client.get("/health", headers={"Origin": "http://evil.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers

@patch("src.main.os.path.exists", return_value=True)
@patch("src.main.os.path.isfile", return_value=True)
@patch("src.main.os.path.isdir")
@patch("src.main.process_pdf")
def test_process_path_traversal_validation(mock_process, mock_isdir, mock_isfile, mock_exists):
    # If the output directory is invalid (e.g. contains traversal characters and is not directory)
    mock_isdir.return_value = False
    response = client.post("/process", json={"input_path": "dummy.pdf", "output_dir": "/tmp/../etc"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid output directory"

@patch("src.main.os.path.exists", return_value=True)
@patch("src.main.os.path.isfile", return_value=True)
@patch("src.main.os.path.isdir", return_value=True)
@patch("src.main.process_pdf")
def test_process_path_traversal_escape(mock_process, mock_isdir, mock_isfile, mock_exists):
    # Simulate a path traversal attempt where the output file does not reside in the output directory
    def mock_abspath(path):
        if "clean" in path:
            return "/etc/passwd"
        if "dummy.pdf" in path:
            return "/tmp/safe/dummy.pdf"
        return "/tmp/safe"

    with patch("src.main.os.path.abspath", side_effect=mock_abspath):
        response = client.post("/process", json={"input_path": "dummy.pdf", "output_dir": "/tmp/safe"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Path traversal attempt detected" 


def test_stream_progress_cleanup():
    from src.main import tasks_status
    
    task_id = 'test-task-123'
    tasks_status[task_id] = {
        'status': 'completed',
        'current_page': 1,
        'total_pages': 1,
        'message': 'Done',
        'output_path': 'dummy_clean.pdf'
    }
    
    response = client.get(f'/stream/{task_id}')
    assert response.status_code == 200
    
    lines = list(response.iter_lines())
    assert len(lines) > 0
    
    assert task_id not in tasks_status


def test_tasks_status_capping():
    from src.main import tasks_status, run_process_task
    
    tasks_status.clear()
    for i in range(100):
        tasks_status[f'task-{i}'] = {'status': 'completed'}
        
    assert len(tasks_status) == 100
    
    with patch('src.main.process_pdf'):
        run_process_task('task-100', 'dummy.pdf', 'dummy_clean.pdf')
        
    assert len(tasks_status) == 100
    assert 'task-0' not in tasks_status
    assert 'task-100' in tasks_status


@patch("src.main.os.path.exists")
@patch("src.main.os.path.isfile", return_value=True)
@patch("src.main.os.path.isdir", return_value=True)
@patch("src.main.process_pdf")
def test_process_endpoint_conflict_rename(mock_process, mock_isdir, mock_isfile, mock_exists):
    # Simulate first _clean.pdf exists, but _clean_1.pdf does not
    def exists_side_effect(path):
        if path.endswith("_clean.pdf"):
            return True
        if path.endswith("_clean_1.pdf"):
            return False
        return True
        
    mock_exists.side_effect = exists_side_effect
    
    # We test that renaming works
    response = client.post("/process", json={
        "input_path": "dummy.pdf",
        "output_dir": "/tmp",
        "conflict_policy": "rename"
    })
    assert response.status_code == 200
    assert response.json()["output_path"] == os.path.abspath("/tmp/dummy_clean_1.pdf")


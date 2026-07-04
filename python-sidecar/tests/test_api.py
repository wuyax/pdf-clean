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

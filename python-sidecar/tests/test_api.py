import sys
import os
import json
import io
import runpy
import subprocess
from unittest.mock import patch, MagicMock

sys.modules['rapidocr_onnxruntime'] = MagicMock()

python_bin = sys.executable
main_script = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'main.py'))

def run_cli_in_process(args):
    # Save original sys.argv, sys.stdout, sys.stderr
    orig_argv = sys.argv
    orig_stdout = sys.stdout
    orig_stderr = sys.stderr

    # Redirect stdout and stderr
    new_stdout = io.StringIO()
    new_stderr = io.StringIO()
    sys.stdout = new_stdout
    sys.stderr = new_stderr
    sys.argv = [main_script] + args

    code = 0
    try:
        runpy.run_path(main_script, run_name="__main__")
    except SystemExit as e:
        code = e.code if e.code is not None else 0
    except Exception as e:
        import traceback
        new_stderr.write(traceback.format_exc())
        code = 1

    finally:
        # Restore sys.argv, sys.stdout, sys.stderr
        sys.argv = orig_argv
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr

    return code, new_stdout.getvalue(), new_stderr.getvalue()

def run_cli_subprocess(args):
    proc = subprocess.run(
        [python_bin, main_script] + args,
        capture_output=True,
        text=True
    )
    return proc.returncode, proc.stdout, proc.stderr

def test_subprocess_missing_args():
    # Verify running via actual subprocess works for error cases
    code, out, err = run_cli_subprocess([])
    assert code == 1
    data = json.loads(out.strip())
    assert data["type"] == "error"
    assert "Missing command" in data["message"]

@patch("scanner.classify_pdf", return_value="TYPE_1")
@patch("src.scanner.classify_pdf", return_value="TYPE_1")
@patch("os.path.exists", return_value=True)
def test_cli_scan(mock_exists, mock_classify1, mock_classify2):
    code, out, err = run_cli_in_process(["scan", "dummy.pdf"])
    assert code == 0
    data = json.loads(out.strip())
    assert data["type"] == "scan_result"
    assert data["results"]["dummy.pdf"] == "TYPE_1"

@patch("os.path.exists", return_value=True)
@patch("os.path.isfile", return_value=True)
@patch("os.path.isdir", return_value=True)
@patch("processor.process_pdf")
@patch("src.processor.process_pdf")
def test_cli_process(mock_proc1, mock_proc2, mock_isdir, mock_isfile, mock_exists):
    code, out, err = run_cli_in_process(["process", "--input", "dummy.pdf", "--output-dir", "/tmp", "--task-id", "t-1"])
    assert code == 0
    lines = out.strip().split("\n")
    data = json.loads(lines[-1])
    assert data["type"] == "completed"
    assert data["task_id"] == "t-1"

@patch("os.path.exists", return_value=True)
@patch("os.path.isfile", return_value=True)
@patch("os.path.isdir")
def test_process_path_traversal_validation(mock_isdir, mock_isfile, mock_exists):
    # If the output directory is not a directory
    mock_isdir.return_value = False
    code, out, err = run_cli_in_process(["process", "--input", "dummy.pdf", "--output-dir", "/tmp/../etc", "--task-id", "t-1"])
    assert code == 1
    data = json.loads(out.strip())
    assert data["type"] == "error"
    assert "Invalid output directory" in data["message"]

@patch("os.path.exists", return_value=True)
@patch("os.path.isfile", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_process_path_traversal_escape(mock_isdir, mock_isfile, mock_exists):
    real_abspath = os.path.abspath
    def mock_abspath(path):
        if path.endswith("_clean.pdf"):
            return "/etc/passwd"
        if "dummy.pdf" in path:
            return "/tmp/safe/dummy.pdf"
        if "safe" in path:
            return "/tmp/safe"
        return real_abspath(path)

    with patch("os.path.abspath", side_effect=mock_abspath):
        code, out, err = run_cli_in_process(["process", "--input", "dummy.pdf", "--output-dir", "/tmp/safe", "--task-id", "t-1"])
        assert code == 1
        data = json.loads(out.strip())
        assert data["type"] == "error"
        assert "Path traversal attempt detected" in data["message"]

@patch("os.path.exists", return_value=True)
@patch("os.path.isfile", return_value=True)
@patch("os.path.isdir", return_value=True)
def test_process_path_traversal_sibling_bypass(mock_isdir, mock_isfile, mock_exists):
    real_abspath = os.path.abspath
    def mock_abspath(path):
        if path.endswith("_clean.pdf"):
            return "/tmp/safe-sibling/dummy_clean.pdf"
        if "dummy.pdf" in path:
            return "/tmp/safe/dummy.pdf"
        if "safe" in path:
            return "/tmp/safe"
        return real_abspath(path)

    with patch("os.path.abspath", side_effect=mock_abspath):
        code, out, err = run_cli_in_process(["process", "--input", "dummy.pdf", "--output-dir", "/tmp/safe", "--task-id", "t-1"])
        assert code == 1
        data = json.loads(out.strip())


        assert data["type"] == "error"
        assert "Path traversal attempt detected" in data["message"]

@patch("os.path.isfile", return_value=True)
@patch("os.path.isdir", return_value=True)
@patch("processor.process_pdf")
@patch("src.processor.process_pdf")
def test_process_conflict_rename(mock_proc1, mock_proc2, mock_isdir, mock_isfile):
    # Simulate first _clean.pdf exists, but _clean_1.pdf does not
    def exists_side_effect(path):
        if path.endswith("_clean.pdf"):
            return True
        if path.endswith("_clean_1.pdf"):
            return False
        return True
        
    with patch("os.path.exists", side_effect=exists_side_effect):
        code, out, err = run_cli_in_process([
            "process",
            "--input", "dummy.pdf",
            "--output-dir", "/tmp",
            "--conflict", "rename",
            "--task-id", "t-1"
        ])
        assert code == 0
        lines = out.strip().split("\n")
        data = json.loads(lines[-1])
        assert data["type"] == "completed"
        assert "dummy_clean_1.pdf" in data["output_path"]

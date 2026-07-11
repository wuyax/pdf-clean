import os
import sys
import json
import contextlib
import threading

# Ensure current and parent directories are in path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from processor import process_pdf
    from scanner import classify_pdf
except ImportError:
    from src.processor import process_pdf
    from src.scanner import classify_pdf

def handle_scan(request):
    file_paths = request.get("paths", [])
    results = {}
    with contextlib.redirect_stdout(sys.stderr):
        for path in file_paths:
            if os.path.exists(path):
                try:
                    results[path] = classify_pdf(path)
                except Exception as e:
                    print(f"Error scanning {path}: {e}", file=sys.stderr)
                    results[path] = "TYPE_UNKNOWN"
            else:
                results[path] = "NOT_FOUND"
    return results

def handle_process(request):
    input_path = request.get("input_path")
    output_dir = request.get("output_dir")
    conflict_policy = request.get("conflict", "overwrite")
    task_id = request.get("task_id", "default")
    dpi = request.get("dpi", 300)
    quality = request.get("quality", 85)
    
    orig_stdout = sys.stdout
    if not input_path or not output_dir:
        orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Missing required arguments"}) + "\n")
        orig_stdout.flush()
        return
        
    input_path = os.path.abspath(input_path)
    output_dir = os.path.abspath(output_dir)
    
    if not os.path.exists(input_path) or not os.path.isfile(input_path):
        orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Input file not found"}) + "\n")
        orig_stdout.flush()
        return
        
    if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
        orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Invalid output directory"}) + "\n")
        orig_stdout.flush()
        return
        
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    
    if conflict_policy == "rename":
        counter = 0
        while counter < 1000:
            suffix = f"_clean_{counter}" if counter > 0 else "_clean"
            output_filename = f"{name}{suffix}{ext}"
            output_path = os.path.abspath(os.path.join(output_dir, output_filename))
            if not os.path.exists(output_path):
                break
            counter += 1
        else:
            orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Could not generate a unique filename"}) + "\n")
            orig_stdout.flush()
            return
    else:
        output_filename = f"{name}_clean{ext}"
        output_path = os.path.abspath(os.path.join(output_dir, output_filename))
        
    output_dir_prefix = output_dir if output_dir.endswith(os.sep) else output_dir + os.sep
    if not output_path.startswith(output_dir_prefix):
        orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Path traversal attempt detected"}) + "\n")
        orig_stdout.flush()
        return

    def progress_callback(current, total, msg):
        orig_stdout.write(json.dumps({
            "type": "progress",
            "task_id": task_id,
            "current_page": current,
            "total_pages": total,
            "message": msg
        }) + "\n")
        orig_stdout.flush()
        
    try:
        with contextlib.redirect_stdout(sys.stderr):
            process_pdf(input_path, output_path, progress_callback=progress_callback, dpi=dpi, quality=quality)
        
        orig_stdout.write(json.dumps({
            "type": "completed",
            "task_id": task_id,
            "current_page": 100,
            "total_pages": 100,
            "message": "已优化",
            "output_path": output_path
        }) + "\n")
        orig_stdout.flush()
    except Exception as e:
        orig_stdout.write(json.dumps({
            "type": "error",
            "task_id": task_id,
            "message": str(e)
        }) + "\n")
        orig_stdout.flush()

if __name__ == "__main__":
    orig_stdout = sys.stdout
    while True:
        line = sys.stdin.readline()
        if not line:
            break  # EOF, exit loop
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            action = req.get("action")
            if action == "scan":
                results = handle_scan(req)
                orig_stdout.write(json.dumps({"type": "scan_result", "results": results}) + "\n")
                orig_stdout.flush()
            elif action == "process":
                handle_process(req)
            else:
                orig_stdout.write(json.dumps({"type": "error", "message": f"Unknown action: {action}"}) + "\n")
                orig_stdout.flush()
        except Exception as e:
            orig_stdout.write(json.dumps({"type": "error", "message": f"Parse request error: {str(e)}"}) + "\n")
            orig_stdout.flush()

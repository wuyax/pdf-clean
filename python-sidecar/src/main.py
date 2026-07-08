import os
import sys
import json
import contextlib
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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"type": "error", "message": "Missing command"}))
        sys.exit(1)
        
    command = sys.argv[1]
    
    if command == "scan":
        file_paths = sys.argv[2:]
        results = {}
        orig_stdout = sys.stdout
        with contextlib.redirect_stdout(sys.stderr):
            for path in file_paths:
                if os.path.exists(path):
                    results[path] = classify_pdf(path)
                else:
                    results[path] = "NOT_FOUND"
        orig_stdout.write(json.dumps({"type": "scan_result", "results": results}) + "\n")
        orig_stdout.flush()
        
    elif command == "process":
        args = sys.argv[2:]
        input_path = None
        output_dir = None
        conflict_policy = "overwrite"
        task_id = "default"
        
        i = 0
        while i < len(args):
            if args[i] == "--input" and i + 1 < len(args):
                input_path = args[i+1]
                i += 2
            elif args[i] == "--output-dir" and i + 1 < len(args):
                output_dir = args[i+1]
                i += 2
            elif args[i] == "--conflict" and i + 1 < len(args):
                conflict_policy = args[i+1]
                i += 2
            elif args[i] == "--task-id" and i + 1 < len(args):
                task_id = args[i+1]
                i += 2
            else:
                i += 1
                
        orig_stdout = sys.stdout
        
        if not input_path or not output_dir:
            orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Missing required arguments"}) + "\n")
            orig_stdout.flush()
            sys.exit(1)
            
        input_path = os.path.abspath(input_path)
        output_dir = os.path.abspath(output_dir)
        
        if not os.path.exists(input_path) or not os.path.isfile(input_path):
            orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Input file not found"}) + "\n")
            orig_stdout.flush()
            sys.exit(1)
            
        if not os.path.exists(output_dir) or not os.path.isdir(output_dir):
            orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Invalid output directory"}) + "\n")
            orig_stdout.flush()
            sys.exit(1)
            
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
                sys.exit(1)
        else:
            output_filename = f"{name}_clean{ext}"
            output_path = os.path.abspath(os.path.join(output_dir, output_filename))
            
        # Validate path traversal
        output_dir_prefix = output_dir if output_dir.endswith(os.sep) else output_dir + os.sep
        if not output_path.startswith(output_dir_prefix):
            orig_stdout.write(json.dumps({"type": "error", "task_id": task_id, "message": "Path traversal attempt detected"}) + "\n")
            orig_stdout.flush()
            sys.exit(1)

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
                process_pdf(input_path, output_path, progress_callback=progress_callback)
            orig_stdout.write(json.dumps({
                "type": "completed",
                "task_id": task_id,
                "output_path": output_path,
                "message": "处理已完成"
            }) + "\n")
            orig_stdout.flush()
        except Exception as e:
            orig_stdout.write(json.dumps({
                "type": "error",
                "task_id": task_id,
                "message": str(e)
            }) + "\n")
            orig_stdout.flush()
            sys.exit(1)

    else:
        print(json.dumps({"type": "error", "message": f"Unknown command: {command}"}))
        sys.exit(1)

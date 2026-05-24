# python-sidecar/src/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import os
import uuid
import sys
import json
import asyncio

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global task state
tasks_status = {}

class ProcessRequest(BaseModel):
    input_path: str
    output_dir: str

class ProcessResponse(BaseModel):
    task_id: str
    output_path: str

class ScanRequest(BaseModel):
    file_paths: list[str]

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/scan")
def scan_endpoint(req: ScanRequest):
    results = {}
    for path in req.file_paths:
        if os.path.exists(path):
            results[path] = classify_pdf(path)
        else:
            results[path] = "NOT_FOUND"
    return results

def run_process_task(task_id: str, input_path: str, output_path: str):
    tasks_status[task_id] = {
        "status": "processing",
        "current_page": 0,
        "total_pages": 0,
        "message": "正在准备处理...",
        "output_path": output_path
    }
    
    def progress_callback(current, total, msg):
        tasks_status[task_id].update({
            "current_page": current,
            "total_pages": total,
            "message": msg
        })
        
    try:
        process_pdf(input_path, output_path, progress_callback=progress_callback)
        tasks_status[task_id]["status"] = "completed"
        tasks_status[task_id]["message"] = "处理已完成"
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        tasks_status[task_id]["status"] = "error"
        tasks_status[task_id]["message"] = str(e)

@app.post("/process", response_model=ProcessResponse)
def process_endpoint(req: ProcessRequest, background_tasks: BackgroundTasks):
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=404, detail="Input file not found")
        
    filename = os.path.basename(req.input_path)
    name, ext = os.path.splitext(filename)
    output_filename = f"{name}_clean{ext}"
    output_path = os.path.join(req.output_dir, output_filename)
    
    task_id = str(uuid.uuid4())
    
    # Start background task
    background_tasks.add_task(run_process_task, task_id, req.input_path, output_path)
        
    return ProcessResponse(task_id=task_id, output_path=output_path)

@app.get("/stream/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        while True:
            if task_id not in tasks_status:
                yield {
                    "event": "message",
                    "data": json.dumps({"status": "not_found", "message": "Task not found"})
                }
                break
            
            data = tasks_status[task_id]
            yield {
                "event": "message",
                "data": json.dumps(data)
            }
            
            if data["status"] in ["completed", "error"]:
                break
                
            await asyncio.sleep(0.5)
            
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    import uvicorn
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="127.0.0.1", port=port)

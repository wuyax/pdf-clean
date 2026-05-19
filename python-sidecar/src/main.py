# python-sidecar/src/main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import os
import uuid
from src.processor import process_pdf

app = FastAPI()

class ProcessRequest(BaseModel):
    input_path: str
    output_dir: str

class ProcessResponse(BaseModel):
    task_id: str
    output_path: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/process", response_model=ProcessResponse)
def process_endpoint(req: ProcessRequest):
    if not os.path.exists(req.input_path):
        raise HTTPException(status_code=404, detail="Input file not found")
        
    filename = os.path.basename(req.input_path)
    name, ext = os.path.splitext(filename)
    output_filename = f"{name}_clean{ext}"
    output_path = os.path.join(req.output_dir, output_filename)
    
    task_id = str(uuid.uuid4())
    
    try:
        process_pdf(req.input_path, output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return ProcessResponse(task_id=task_id, output_path=output_path)

if __name__ == "__main__":
    import uvicorn
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    uvicorn.run(app, host="127.0.0.1", port=port)

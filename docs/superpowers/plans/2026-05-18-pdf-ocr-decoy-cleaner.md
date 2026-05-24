# PDF OCR Decoy Cleaner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Tauri + Vue desktop app with a Python FastAPI sidecar to completely rasterize PDFs and reconstruct them with correct PaddleOCR text, stripping decoy layers.

**Architecture:** Tauri (Rust) shell running a Vue 3 frontend. A Python FastAPI sidecar bundled via PyInstaller handles heavy lifting. The frontend communicates with the sidecar via HTTP and SSE for progress.

**Tech Stack:** Tauri, Vue 3, TypeScript, TailwindCSS, Python, FastAPI, pdf2image, paddleocr, PyMuPDF.

---

### Task 1: Initialize Project Structure

**Files:**
- Create: `package.json`, `src-tauri/tauri.conf.json`, `python-sidecar/requirements.txt`

- [ ] **Step 1: Scaffold Tauri App**

```bash
npm create tauri-app@latest . -- --manager npm --template vue-ts
npm install
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

- [ ] **Step 2: Configure Tailwind**

Modify `tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```
Modify `src/style.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 3: Setup Python sidecar directory**

```bash
mkdir -p python-sidecar/src
mkdir -p python-sidecar/tests
touch python-sidecar/src/__init__.py
touch python-sidecar/tests/__init__.py
```

- [ ] **Step 4: Create requirements.txt**

```python
# python-sidecar/requirements.txt
fastapi==0.103.1
uvicorn==0.23.2
pdf2image==1.16.3
paddleocr==2.7.0.3
paddlepaddle==2.5.1
PyMuPDF==1.23.3
pytest==7.4.2
httpx==0.24.1
```

- [ ] **Step 5: Commit**

```bash
git add package.json src-tauri/ src/ tailwind.config.js python-sidecar/
git commit -m "chore: init Tauri Vue project and Python sidecar structure"
```

### Task 2: Implement PDF Processing Logic (Backend)

**Files:**
- Create: `python-sidecar/src/processor.py`
- Create: `python-sidecar/tests/test_processor.py`

- [ ] **Step 1: Write the failing test for PDF rasterization**

```python
# python-sidecar/tests/test_processor.py
import pytest
from unittest.mock import patch, MagicMock
from src.processor import process_pdf

@patch('src.processor.convert_from_path')
@patch('src.processor.PaddleOCR')
@patch('src.processor.fitz')
def test_process_pdf(mock_fitz, mock_paddle, mock_convert, tmp_path):
    # Arrange
    mock_convert.return_value = [MagicMock()] # 1 page
    mock_ocr_instance = MagicMock()
    mock_ocr_instance.ocr.return_value = [[[[[0, 0], [10, 0], [10, 10], [0, 10]], ('test', 0.99)]]]
    mock_paddle.return_value = mock_ocr_instance
    
    mock_doc = MagicMock()
    mock_fitz.open.return_value = mock_doc
    
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_text("dummy")
    output_pdf = tmp_path / "output.pdf"
    
    # Act
    result = process_pdf(str(input_pdf), str(output_pdf))
    
    # Assert
    assert result == str(output_pdf)
    mock_convert.assert_called_once()
    mock_ocr_instance.ocr.assert_called_once()
    mock_doc.save.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd python-sidecar
python -m pytest tests/test_processor.py -v
cd ..
```
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# python-sidecar/src/processor.py
import os
from pdf2image import convert_from_path
from paddleocr import PaddleOCR
import fitz  # PyMuPDF
import io

def process_pdf(input_path: str, output_path: str):
    # Initialize OCR (use English and Chinese)
    ocr = PaddleOCR(use_angle_cls=True, lang="ch")
    
    # 1. Rasterize PDF to images
    images = convert_from_path(input_path, dpi=300)
    
    # 2. Create a new empty PDF
    doc = fitz.open()
    
    for page_num, img in enumerate(images):
        # Save image to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")
        img_bytes = img_bytes.getvalue()
        
        import numpy as np
        img_np = np.array(img)
        result = ocr.ocr(img_np, cls=True)
        
        width, height = img.size
        page = doc.new_page(width=width, height=height)
        
        rect = fitz.Rect(0, 0, width, height)
        page.insert_image(rect, stream=img_bytes)
        
        if result and result[0]:
            for line in result[0]:
                box = line[0]
                text = line[1][0]
                p0 = box[0]
                p2 = box[2]
                text_rect = fitz.Rect(p0[0], p0[1], p2[0], p2[1])
                page.insert_textbox(text_rect, text, color=(0,0,0), render_mode=3)
                
    doc.save(output_path)
    doc.close()
    return output_path
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd python-sidecar
python -m pytest tests/test_processor.py -v
cd ..
```

- [ ] **Step 5: Commit**

```bash
git add python-sidecar/src/processor.py python-sidecar/tests/test_processor.py
git commit -m "feat: implement PDF processing logic with paddleocr and pymupdf"
```

### Task 3: Implement FastAPI Backend

**Files:**
- Create: `python-sidecar/src/main.py`
- Create: `python-sidecar/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
# python-sidecar/tests/test_api.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd python-sidecar
python -m pytest tests/test_api.py -v
cd ..
```

- [ ] **Step 3: Write minimal implementation**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd python-sidecar
python -m pytest tests/test_api.py -v
cd ..
```

- [ ] **Step 5: Commit**

```bash
git add python-sidecar/src/main.py python-sidecar/tests/test_api.py
git commit -m "feat: add FastAPI application for processing requests"
```

### Task 4: Frontend Tauri Integration

**Files:**
- Modify: `src/App.vue`

- [ ] **Step 1: Write the frontend code**

```vue
<!-- src/App.vue -->
<template>
  <div class="min-h-screen bg-gray-100 flex flex-col items-center justify-center p-4">
    <div class="bg-white p-8 rounded-lg shadow-lg w-full max-w-md">
      <h1 class="text-2xl font-bold mb-6 text-center text-gray-800">PDF OCR Cleaner</h1>
      
      <div 
        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:bg-gray-50 transition"
        @click="selectFile"
      >
        <p v-if="!selectedFile" class="text-gray-500">Click to select PDF</p>
        <p v-else class="text-green-600 font-medium">{{ selectedFile }}</p>
      </div>
      
      <div class="mt-6">
        <button 
          @click="processFile" 
          :disabled="!selectedFile || isProcessing"
          class="w-full bg-blue-600 text-white py-2 px-4 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ isProcessing ? 'Processing...' : 'Clean PDF' }}
        </button>
      </div>
      
      <div v-if="error" class="mt-4 p-3 bg-red-100 text-red-700 rounded">
        {{ error }}
      </div>
      
      <div v-if="successPath" class="mt-4 p-3 bg-green-100 text-green-700 rounded text-sm break-all">
        Success! Saved to:<br> {{ successPath }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { open } from '@tauri-apps/api/dialog';
import { fetch } from '@tauri-apps/api/http';

const selectedFile = ref('');
const isProcessing = ref(false);
const error = ref('');
const successPath = ref('');

const API_URL = 'http://127.0.0.1:8000';

async function selectFile() {
  try {
    const file = await open({
      filters: [{ name: 'PDF', extensions: ['pdf'] }],
      multiple: false,
    });
    if (file && typeof file === 'string') {
      selectedFile.value = file;
      error.value = '';
      successPath.value = '';
    }
  } catch (err) {
    error.value = 'Failed to select file';
  }
}

async function processFile() {
  if (!selectedFile.value) return;
  
  isProcessing.value = true;
  error.value = '';
  successPath.value = '';
  
  try {
    const lastSlash = Math.max(selectedFile.value.lastIndexOf('/'), selectedFile.value.lastIndexOf('\\'));
    const outputDir = selectedFile.value.substring(0, lastSlash);

    const response = await fetch(`${API_URL}/process`, {
      method: 'POST',
      body: {
        type: 'Json',
        payload: {
          input_path: selectedFile.value,
          output_dir: outputDir
        }
      }
    });

    if (response.ok) {
      const data = response.data as any;
      successPath.value = data.output_path;
    } else {
      error.value = `Server Error: ${response.status}`;
    }
  } catch (err: any) {
    error.value = `Error: ${err.message}`;
  } finally {
    isProcessing.value = false;
  }
}
</script>
```

- [ ] **Step 2: Update tauri.conf.json**

Modify `src-tauri/tauri.conf.json`:
```json
"allowlist": {
  "dialog": {
    "all": true,
    "open": true
  },
  "http": {
    "all": true,
    "request": true
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add src/App.vue src-tauri/tauri.conf.json
git commit -m "feat: build Vue frontend and connect to backend API"
```

### Task 5: Integrate Sidecar in Tauri

**Files:**
- Modify: `src-tauri/src/main.rs`
- Modify: `src-tauri/tauri.conf.json`

- [ ] **Step 1: Configure sidecar config**

Modify `src-tauri/tauri.conf.json` allowlist:
```json
"allowlist": {
  "shell": {
    "all": true,
    "execute": true,
    "sidecar": true
  }
}
```

- [ ] **Step 2: Write Tauri backend logic**

Modify `src-tauri/src/main.rs`:

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
  tauri::Builder::default()
    .setup(|_app| {
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
```

- [ ] **Step 3: Commit**

```bash
git add src-tauri/src/main.rs src-tauri/tauri.conf.json
git commit -m "feat: configure Tauri sidecar and shell commands"
```

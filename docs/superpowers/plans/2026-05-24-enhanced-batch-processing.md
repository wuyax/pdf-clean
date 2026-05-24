# Enhanced Batch Processing & Intelligent Compression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the PDF OCR Cleaner into a batch-processing tool with intelligent PDF classification and high-quality "TinyJPG-style" compression.

**Architecture:** Extend the FastAPI sidecar with a `Scanner` for pre-flight checks and a `Compressor` for optimized output. Implement SSE (Server-Sent Events) for real-time page-level progress. Update the Vue frontend to support a task queue and status visualization.

**Tech Stack:** Tauri, Vue 3, FastAPI, PyMuPDF, PaddleOCR, Pillow (with MozJPEG-style optimization).

---

### Task 1: Implement Intelligent Scanner (Backend)

**Files:**
- Create: `python-sidecar/src/scanner.py`
- Create: `python-sidecar/tests/test_scanner.py`

- [ ] **Step 1: Write failing tests for PDF classification**

```python
# python-sidecar/tests/test_scanner.py
import pytest
from unittest.mock import MagicMock, patch
from src.scanner import classify_pdf

def test_classify_pure_image():
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "" # No text
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    with patch('fitz.open', return_value=mock_doc):
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_4" # Pure Image

def test_classify_decoy_format():
    mock_doc = MagicMock()
    mock_page = MagicMock()
    # Simulate decoy: text exists but is gibberish or has weird coords
    mock_page.get_text.return_value = " \n \n \n " 
    mock_doc.__getitem__.return_value = mock_page
    mock_doc.__len__.return_value = 1
    
    with patch('fitz.open', return_value=mock_doc):
        # We'll refine heuristic in impl
        category = classify_pdf("dummy.pdf")
        assert category == "TYPE_2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python-sidecar && pytest tests/test_scanner.py`
Expected: FAIL

- [ ] **Step 3: Implement `classify_pdf` with heuristics**

```python
# python-sidecar/src/scanner.py
import fitz
import re

def classify_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    if len(doc) == 0:
        return "TYPE_UNKNOWN"
    
    # Check page 2 if exists, else page 1
    page_idx = 1 if len(doc) > 1 else 0
    page = doc[page_idx]
    
    text = page.get_text("text").strip()
    
    # Type 4: Pure Image
    if len(text) < 10:
        doc.close()
        return "TYPE_4"
    
    # Type 2 check: Heuristics for gibberish/decoy
    # 1. High ratio of whitespace/special chars vs alphanumeric
    alphanumeric = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', text)
    if len(text) > 0 and (len(alphanumeric) / len(text)) < 0.3:
        doc.close()
        return "TYPE_2"
        
    # 2. Check for hidden text (very small font size or overlapping)
    # For now, if it passes alpha check, assume Type 1 (Valid)
    doc.close()
    return "TYPE_1"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python-sidecar && pytest tests/test_scanner.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add python-sidecar/src/scanner.py python-sidecar/tests/test_scanner.py
git commit -m "feat: add intelligent PDF scanner for classification"
```

### Task 2: Implement SSE Progress Tracking (Backend)

**Files:**
- Modify: `python-sidecar/src/main.py`
- Modify: `python-sidecar/src/processor.py`

- [ ] **Step 1: Update `process_pdf` to accept a callback**

Modify `python-sidecar/src/processor.py` to take a `progress_callback(current, total, msg)` and call it inside the page loop.

- [ ] **Step 2: Add SSE endpoint in `main.py`**

```python
# python-sidecar/src/main.py
import asyncio
from sse_starlette.sse import EventSourceResponse

@app.get("/stream/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        while True:
            # Check global task state (we'll need a simple shared dict)
            data = get_task_progress(task_id) 
            yield {"data": json.dumps(data)}
            if data["status"] in ["completed", "error"]:
                break
            await asyncio.sleep(0.5)
    return EventSourceResponse(event_generator())
```

- [ ] **Step 3: Commit**

```bash
git add python-sidecar/src/main.py python-sidecar/src/processor.py
git commit -m "feat: implement SSE progress tracking in backend"
```

### Task 3: Implement High-Quality Compression (Backend)

**Files:**
- Modify: `python-sidecar/src/processor.py`

- [ ] **Step 1: Update image saving logic in `processor.py`**

Replace simple JPEG save with optimized save:
```python
# Inside process_pdf loop
img.save(
    img_bytes, 
    format="JPEG", 
    quality=85, 
    optimize=True, 
    progressive=True,
    subsampling=0 # 4:4:4 to keep text sharp, or 2 for high compression
)
```

- [ ] **Step 2: Add DPI normalization**

```python
# Before OCR/Saving
if img.info.get('dpi', (72, 72))[0] > 300:
    # Resize logic to target 300 DPI
    pass
```

- [ ] **Step 3: Commit**

```bash
git add python-sidecar/src/processor.py
git commit -m "feat: add high-quality JPEG compression and DPI normalization"
```

### Task 4: Task Queue UI (Frontend)

**Files:**
- Modify: `src/App.vue`
- Create: `src/components/TaskTable.vue`

- [ ] **Step 1: Create TaskTable component**

Show columns: Checkbox, Name, Category (Badge), Progress (Bar), Status.

- [ ] **Step 2: Integrate into App.vue**

Replace single file logic with an array `tasks`.
Add `scanFiles` function to call `/health` (or new `/scan`) and update task categories.

- [ ] **Step 3: Implement SSE listener in Frontend**

Use `new EventSource()` to listen to `/stream/{task_id}` and update the progress bar in the table.

- [ ] **Step 4: Commit**

```bash
git add src/App.vue src/components/TaskTable.vue
git commit -m "feat: implement batch task table and SSE progress listener"
```

### Task 5: Final Integration & E2E Test

- [ ] **Step 1: Run full application**
- [ ] **Step 2: Drag 3 files (1 Normal, 1 Image-only, 1 Decoy)**
- [ ] **Step 3: Verify categories are correct**
- [ ] **Step 4: Click 'Start' and verify progress bars and output quality**
- [ ] **Step 5: Commit final polish**

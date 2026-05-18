# PDF OCR Decoy Cleaner - Design Specification

## Overview
A desktop application designed to clear "OCR decoy layers" (hidden gibberish text used to prevent copying) from PDF files and rebuild them with correct OCR.

## Architecture
- **Frontend**: Tauri, Vue 3 (Composition API), TypeScript, TailwindCSS.
- **Backend (Sidecar)**: Python, FastAPI. Bundled as a standalone executable via PyInstaller.
- **AI/OCR Engine**: PaddleOCR (for high accuracy in Chinese/English).

## Data Flow & Processing Logic
1. **File Selection**: User selects a PDF file in the Vue frontend via Tauri's file dialog.
2. **Submission**: Frontend sends a request (with file path) to the Python FastAPI sidecar. For realtime feedback, the backend will implement a WebSocket endpoint or Server-Sent Events (SSE) to stream progress.
3. **Rasterization**: Python uses `pdf2image` (with Poppler) to render each PDF page into a high-resolution image, completely destroying any embedded text/decoy layers.
4. **OCR Extraction**: PaddleOCR processes each image to extract text and bounding boxes.
5. **Reconstruction**: `PyMuPDF` takes the rendered images as backgrounds and overlays the extracted text as a transparent, searchable layer on top.
6. **Delivery**: The newly generated "Searchable PDF" is saved to disk, and the path is returned to the frontend.

## User Interface & Experience
- **Main View**: A drag-and-drop zone and a "Select File" button.
- **Progress Feedback**: A progress bar showing the current page being processed (e.g., "Processing page 3 of 10...").
- **Error Handling**: 
  - If the PDF is encrypted, corrupted, or if there's an out-of-memory issue, the Python backend catches the exception and returns a readable error message.
  - The Vue frontend displays errors via toast notifications.
- **Completion**: Once finished, a "Success" message appears with a button to open the newly created file or its containing folder.

## Technical Constraints & Dependencies
- **Rust Toolchain**: Required for compiling the Tauri app.
- **Poppler**: Required by `pdf2image`. Since this is a desktop app, the Poppler binaries must be bundled alongside the executable.
- **Memory Footprint**: PaddleOCR can be memory-intensive. The choice of Tauri ensures the UI layer remains extremely lightweight, leaving maximum system resources for the Python OCR sidecar.

## Scope
- **Current Scope**: Single file processing, local execution.
- **Out of Scope for V1**: Batch processing of multiple files at once, cloud OCR fallback, advanced PDF editing capabilities.
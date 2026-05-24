# PDF OCR Decoy Cleaner - Feature Enhancement Design Spec

## Overview
This document outlines the design for major feature enhancements to the existing PDF OCR Decoy Cleaner. The goal is to evolve the tool from a single-file processor into a robust, intelligent batch-processing application that produces highly optimized output.

## 1. Core Enhancements
- **Batch Processing Workflow:** Support for queueing multiple PDF files.
- **Smart Classification (Pre-flight Check):** Automatically categorize PDFs to filter out files that don't need processing.
- **High-Quality Compression:** Implement TinyJPG-like zero-config compression to significantly reduce output file size while maintaining visual fidelity.
- **Real-time Progress Tracking:** Display granular progress for both overall batch status and page-level processing.

## 2. Architecture & Data Flow

### 2.1 UI / Frontend (Vue 3 + Tauri)
- **Task Table Component:** Replaces the single-file dropzone. Displays:
  - File Name, Size
  - **Category Badge** (e.g., "Decoy OCR", "Pure Image", "Valid PDF")
  - **Progress Indicator** (Dynamic progress bar replacing the badge during processing)
  - Status (Scanning, Pending, Processing, Skipped, Completed)
  - Selection Checkbox
- **Workflow:** 
  1. User drops files.
  2. Frontend sends files to backend for "Scanning".
  3. UI updates with categories and auto-selects specific types.
  4. User clicks "Start Processing".
  5. UI listens to SSE (Server-Sent Events) for real-time page-level progress updates.

### 2.2 Backend (Python FastAPI Sidecar)
- **Scanner Service:** A lightweight module that executes the Pre-flight Check on queued files.
- **Enhanced Processor:** The existing pipeline upgraded with the new compression logic.
- **SSE Endpoint:** A new streaming endpoint to emit processing progress to the frontend.

## 3. Intelligent Classification Logic (Smart ID)
The Scanner evaluates a sample page (e.g., Page 2) to categorize the PDF within 1-2 seconds without running a full OCR pipeline.

1. **Layer Check:** Extract text layer using `PyMuPDF`.
   - If char count < 10 -> **Type 4: Pure Image** (Auto-select for processing).
2. **Heuristic Analysis:** Check extracted text for gibberish.
   - Look for unprintable characters, chaotic unicode distributions, or stacked bounding boxes (transparent text overlay anomalies).
   - If true -> **Type 2: Decoy Format** (Auto-select for processing).
3. **OCR Sampling Match:** 
   - Crop a small central region (e.g., 500x500px).
   - Run PaddleOCR on this crop.
   - Compare OCR result with the text layer extracted from the exact same region using Levenshtein distance.
   - If similarity < 30% -> **Type 2: Decoy Format** (Auto-select).
   - If similarity > 85% -> **Type 1 / 3: Valid PDF / Existing correct OCR** (Do NOT auto-select).

## 4. Zero-Config High-Quality Compression
To achieve "TinyJPG" level compression (visually lossless, highly compressed) for the reconstructed PDFs:

- **Target DPI Normalization:** Force downsample excessively large inputs to **300 DPI**, the optimal threshold for both reading and OCR.
- **Quantization & Chroma Subsampling:** Utilize advanced JPEG encoding techniques (via Pillow/MozJPEG logic). Apply aggressive chroma subsampling while preserving luma (brightness) to maintain sharp text edges.
- **Encoding Parameters:** Force `Quality=85`, `Optimize=True`, and `Progressive=True`.
- **PDF Container Deflation:** Utilize PyMuPDF's maximum garbage collection (`garbage=4`) and stream compression (`deflate=True`) when saving the final document to eliminate redundant internal objects.

## 5. User Interaction & Edge Cases
- **Bypass / Force:** Even if a file is classified as Type 1 (Valid PDF) and unselected, the user can manually check the box to force the system to rasterize and rebuild it.
- **Memory Management:** The system will process files sequentially to prevent RAM exhaustion, though page extraction within a file can remain parallelized if memory allows.

# PDF OCR Decoy Cleaner

A desktop application to clear "OCR decoy layers" from PDFs and rebuild them with correct OCR using PaddleOCR.

## Features
- Completely removes hidden decoy text by rasterizing PDF pages.
- Reconstructs searchable text using high-accuracy PaddleOCR.
- Lightweight Tauri v2 + Vue 3 frontend.
- Python FastAPI sidecar for AI processing.

## Prerequisites

### 1. Rust Toolchain
Install from [rustup.rs](https://rustup.rs/). Required for building the Tauri app.

### 2. Python 3.10+
Required for the OCR sidecar.

### 3. Poppler
`pdf2image` depends on Poppler.
- **macOS**: `brew install poppler`
- **Windows**: Download from [poppler for Windows](https://github.com/oschwartz10612/poppler-windows/releases/) and add `bin` to PATH.
- **Linux**: `sudo apt install poppler-utils`

## Development

### Backend (Sidecar)
```bash
cd python-sidecar
python -m venv venv
source venv/bin/activate # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python src/main.py
```

### Frontend (Tauri)
```bash
npm install
npm run tauri dev
```

## Building for Production

To build a standalone executable:
1. Build the Python sidecar using PyInstaller and place it in `src-tauri/binaries/python-sidecar-<platform>`.
2. Run `npm run tauri build`.

## License
MIT

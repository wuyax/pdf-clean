# Python Sidecar Size Optimization Design Spec

## Background
The current `python-sidecar` packaged binary built with PyInstaller is approximately 130MB~138MB. This large size increases the download size of the final Tauri distribution package and contributes to a 3-5 seconds cold start delay because the single-file binary must self-extract its contents to a temporary directory on startup.

## Goal
Optimize the sidecar binary size by:
1. Removing unused packages (`pymupdf-fonts`).
2. Separating development dependencies (`pytest`) from production runtime dependencies.
3. Adding explicit exclusions of unused Python modules during PyInstaller compilation.

## Detailed Changes

### 1. Dependency Clean-up

#### Production Dependencies: `python-sidecar/requirements.txt`
We will shrink `requirements.txt` to only include the bare runtime necessities:
```text
rapidocr_onnxruntime
pymupdf>=1.24.0
numpy
```

#### Development Dependencies: `python-sidecar/requirements-dev.txt`
We will extract testing dependencies to a development-only configuration:
```text
pytest
```

### 2. PyInstaller Exclusions
We will update the PyInstaller compilation command in both the local build process and `.github/workflows/release.yml` to explicitly exclude unnecessary packages:
*   `tkinter`: GUI toolkit, not used by sidecar.
*   `unittest` / `test`: Standard library test frameworks, not used at runtime.
*   `email`: Email handling module.
*   `pydoc`: Documentation generator.
*   `html` / `http` (except what is transitively required): HTTP/HTML utilities.

The updated compile command format:
```bash
pyinstaller --clean -y --onefile --name "python-sidecar" \
  --collect-all rapidocr_onnxruntime \
  --collect-all onnxruntime \
  --collect-all pyfitz \
  --exclude-module tkinter \
  --exclude-module unittest \
  --exclude-module test \
  --exclude-module email \
  --exclude-module pydoc \
  src/main.py
```

## Verification Plan
1. **Tests Execution**: Run `pytest` locally to confirm all tests pass successfully without `pymupdf-fonts`.
2. **Binary Compiling & Measurement**: Compile the new sidecar binary locally using PyInstaller and measure the size reduction compared to the previous ~138MB version.
3. **Execution Verification**: Run the optimized sidecar binary against test PDFs (`test_unknow_type.pdf`) to verify OCR and classification function exactly as before.

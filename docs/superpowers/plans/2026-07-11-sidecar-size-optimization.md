# Sidecar Size Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shrink the packaged Python sidecar binary size to improve cold start latency and reduce the installation package size.

**Architecture:** Refactor dependencies by removing unused libraries (`pymupdf-fonts`) and separating development dependencies (`pytest`), then add explicit module exclusions to the PyInstaller compile commands.

**Tech Stack:** Python 3.12, PyInstaller, Pip

## Global Constraints
- Target platform: macOS (darwin), Windows (win32)
- Do not break existing unit/integration tests.
- Do not introduce external libraries not specified in requirements.

---

### Task 1: Dependency Separation

**Files:**
- Create: `python-sidecar/requirements-dev.txt`
- Modify: `python-sidecar/requirements.txt`

**Interfaces:**
- Consumes: None
- Produces: Cleaner `requirements.txt` environment for packaging.

- [ ] **Step 1: Write requirements-dev.txt**

Write to `python-sidecar/requirements-dev.txt`:
```text
pytest
```

- [ ] **Step 2: Modify requirements.txt**

Modify `python-sidecar/requirements.txt` to contain only:
```text
rapidocr_onnxruntime
pymupdf>=1.24.0
numpy
```

- [ ] **Step 3: Verify tests still pass in the new environment**

Run:
```bash
cd python-sidecar
./venv/bin/pip uninstall -y pymupdf-fonts pytest
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install -r requirements-dev.txt
./venv/bin/pytest
```
Expected: All 18 tests pass successfully.

- [ ] **Step 4: Commit changes**

Run:
```bash
git add python-sidecar/requirements.txt python-sidecar/requirements-dev.txt
git commit -m "chore(sidecar): separate dev and prod dependencies and remove unused fonts"
```

---

### Task 2: Update PyInstaller Exclusions in release.yml

**Files:**
- Modify: `.github/workflows/release.yml:71-84`

**Interfaces:**
- Consumes: Production dependencies from Task 1.
- Produces: Optimized PyInstaller release binaries on GitHub CI.

- [ ] **Step 1: Update release.yml build commands**

Modify the `Build Python Sidecar Binary` step in `.github/workflows/release.yml` around lines 71-84:

Target Content to Replace:
```yaml
      - name: Build Python Sidecar Binary
        run: |
          cd python-sidecar
          if [ "$RUNNER_OS" == "Windows" ]; then
            ./venv/Scripts/pyinstaller --clean -y --onefile --name "python-sidecar" --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pyfitz src/main.py
            mkdir -p ../src-tauri/binaries
            cp dist/python-sidecar.exe ../src-tauri/binaries/python-sidecar-x86_64-pc-windows-msvc.exe
          else
            ./venv/bin/pyinstaller --clean -y --onefile --name "python-sidecar" --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pyfitz src/main.py
            mkdir -p ../src-tauri/binaries
            cp dist/python-sidecar ../src-tauri/binaries/python-sidecar-${{ matrix.target }}
          fi
        shell: bash
```

Replacement Content:
```yaml
      - name: Build Python Sidecar Binary
        run: |
          cd python-sidecar
          if [ "$RUNNER_OS" == "Windows" ]; then
            ./venv/Scripts/pyinstaller --clean -y --onefile --name "python-sidecar" --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pyfitz --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module email --exclude-module pydoc src/main.py
            mkdir -p ../src-tauri/binaries
            cp dist/python-sidecar.exe ../src-tauri/binaries/python-sidecar-x86_64-pc-windows-msvc.exe
          else
            ./venv/bin/pyinstaller --clean -y --onefile --name "python-sidecar" --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pyfitz --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module email --exclude-module pydoc src/main.py
            mkdir -p ../src-tauri/binaries
            cp dist/python-sidecar ../src-tauri/binaries/python-sidecar-${{ matrix.target }}
          fi
        shell: bash
```

- [ ] **Step 2: Run PyInstaller compilation locally to verify file size reduction**

Run:
```bash
cd python-sidecar
./venv/bin/pyinstaller --clean -y --onefile --name "python-sidecar" --collect-all rapidocr_onnxruntime --collect-all onnxruntime --collect-all pyfitz --exclude-module tkinter --exclude-module unittest --exclude-module test --exclude-module email --exclude-module pydoc src/main.py
ls -la dist/python-sidecar
```
Expected: The binary builds successfully, and its size is smaller than the previous ~138MB version.

- [ ] **Step 3: Run sidecar binary against test file to verify logic**

Run:
```bash
cd python-sidecar
MODEL_DIR="./models" dist/python-sidecar scan ../test_unknow_type.pdf
```
Expected: Output contains `{"type": "scan_result", "results": {"../test_unknow_type.pdf": "TYPE_2"}}`.

- [ ] **Step 4: Cleanup temporary local build artifacts**

Run:
```bash
rm -rf build/ dist/ python-sidecar.spec
```

- [ ] **Step 5: Commit changes**

Run:
```bash
git add .github/workflows/release.yml
git commit -m "chore(ci): add pyinstaller exclusions for optimized release binaries"
```

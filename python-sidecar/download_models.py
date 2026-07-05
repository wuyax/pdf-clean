import os
import urllib.request

MODELS = {
    "det.onnx": "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv4/ch_PP-OCRv4_det_infer.onnx",
    "rec.onnx": "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv4/ch_PP-OCRv4_rec_infer.onnx",
    "cls.onnx": "https://huggingface.co/SWHL/RapidOCR/resolve/main/PP-OCRv1/ch_ppocr_mobile_v2.0_cls_infer.onnx"
}

def download_models():
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "models"))
    os.makedirs(target_dir, exist_ok=True)
    for name, url in MODELS.items():
        dest = os.path.join(target_dir, name)
        if not os.path.exists(dest):
            print(f"Downloading {name} from {url}...")
            urllib.request.urlretrieve(url, dest)
            print(f"Saved to {dest}")
        else:
            print(f"{name} already exists.")

if __name__ == "__main__":
    download_models()

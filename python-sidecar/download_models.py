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
        # Check if file exists and is not extremely small (e.g. less than 10KB, which indicates a corrupted/failed download)
        if not os.path.exists(dest) or os.path.getsize(dest) < 10240:
            print(f"Downloading {name} from {url}...")
            tmp_dest = dest + ".tmp"
            try:
                urllib.request.urlretrieve(url, tmp_dest)
                os.replace(tmp_dest, dest)
                print(f"Saved to {dest}")
            except BaseException as e:
                mirror_url = url.replace("huggingface.co", "hf-mirror.com")
                print(f"Primary download failed: {e}. Retrying with mirror: {mirror_url}...")
                try:
                    urllib.request.urlretrieve(mirror_url, tmp_dest)
                    os.replace(tmp_dest, dest)
                    print(f"Saved to {dest} via mirror")
                except BaseException as mirror_err:
                    if os.path.exists(tmp_dest):
                        try:
                            os.remove(tmp_dest)
                        except Exception:
                            pass
                    raise mirror_err
        else:
            print(f"{name} already exists.")

if __name__ == "__main__":
    download_models()

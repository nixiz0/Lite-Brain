import os
import torch
from pathlib import Path
from dotenv import load_dotenv

# Load .secret-env explicitly
load_dotenv(dotenv_path=".secret-env", override=False)

# =====================[ Paths / model cache ]====================
# Folder where this file is located
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", BASE_DIR.parents[1])) # Do like a 'cd ..'

# Common root for all models (embed, ocr, etc.)
MODELS_ROOT = Path(os.getenv("MODELS_ROOT", PROJECT_ROOT / "model"))
MODELS_ROOT.mkdir(parents=True, exist_ok=True)

# Dedicated subfolder for OCR
OCR_MODEL_DIR = Path(os.getenv("OCR_MODEL_DIR", MODELS_ROOT / "doctr"))
OCR_MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = os.getenv("OCR_MODEL_DIR", str(OCR_MODEL_DIR))

# We force docTR to use this folder as a template cache
os.environ.setdefault("DOCTR_CACHE_DIR", str(OCR_MODEL_DIR))

# =====================[ Auth / runtime ]=====================
HF_TOKEN = os.getenv("HF_TOKEN", "")

# Auth (empty => no auth)
API_KEY = os.getenv("API_KEY", "")

# DEVICE = "cpu" or "cuda:0" (or other)
DEVICE = os.getenv("DEVICE", "cpu")

# =====================[ docTR architectures ]====================
# Automatic arch selection based on the EFFECTIVE device (string + CUDA available)
_raw_device = DEVICE or "cpu"
has_cuda = _raw_device.startswith("cuda") and torch.cuda.is_available()

# OCR_DET_ARCH available : ["db_resnet50", "db_mobilenet_v3_large", "linknet_resnet18", "linknet_resnet34",
#                           "linknet_resnet50", "fast_tiny", "fast_small", "fast_base"]
# OCR_RECO_ARCH available : ["crnn_vgg16_bn", "crnn_mobilenet_v3_small", "crnn_mobilenet_v3_large", "sar_resnet31",
#                            "master", "vitstr_small", "vitstr_base", "parseq"]
# db_mobilenet_v3_large + crnn_mobilenet_v3_small = very good compromise between performance and quality on CPU.
# db_resnet50 + parseq = very good compromise between performance and quality on GPU.
if not has_cuda:
    default_det = "db_mobilenet_v3_large"
    default_reco = "crnn_mobilenet_v3_small"
else:
    default_det = "db_resnet50"
    default_reco = "parseq"

OCR_DET_ARCH  = os.getenv("OCR_DET_ARCH",  default_det)
OCR_RECO_ARCH = os.getenv("OCR_RECO_ARCH", default_reco)

# =====================[ Runtime knobs ]====================
# Worker competition: keep the guard down to avoid saturating the CPU.
# (You can go up to 2 if your machine breathes well)
OCR_CONCURRENCY_LIMIT = int(os.getenv("OCR_CONCURRENCY_LIMIT", "1"))

# Hard cap on the number of pages to maintain reasonable latency.
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "50"))

# We assume that the pages are generally straight (better performance).
OCR_ASSUME_STRAIGHT = os.getenv("OCR_ASSUME_STRAIGHT", "1") == "1"

# Threads Torch – adapt to your CPU (4 = good default for a recent i5).
TORCH_NUM_THREADS = int(os.getenv("TORCH_NUM_THREADS", "4"))
TORCH_NUM_INTEROP = int(os.getenv("TORCH_NUM_INTEROP", "1"))

# =====================[ PDF / batching / concurrency ]===========
# DPI: 150–200 is often sufficient; 170 is a good compromise between quality and performance.
OCR_PDF_DPI = int(os.getenv("OCR_PDF_DPI", "170"))

# Number of pages processed per batch.
OCR_BATCH_PAGES = int(os.getenv("OCR_BATCH_PAGES", "2"))

# Timeout to obtain a processing slot before returning 429.
SEM_TIMEOUT_S = int(os.getenv("SEM_TIMEOUT_S", "300"))

# =====================[ Upload guardrails ]======================
MAX_UPLOAD_MB     = int(os.getenv("MAX_UPLOAD_MB", "100"))  # Error 413 if exceeded
PPTX_MAX_SLIDES   = int(os.getenv("PPTX_MAX_SLIDES", "110"))

import requests, json
from pathlib import Path

# Base URL of the OCR API.
API_URL = "http://127.0.0.1:9005/ocr"
HEALTH_URL = "http://127.0.0.1:9005/ocr/healthz"

# Optional API key if the server is configured with authentication.
API_KEY = ""  # Fill if you enabled an API key in your environment

# HTTP headers required by the API.
# ⚠️ Do NOT force Content-Type here: `requests` will set the correct multipart
#     boundary for us when using `files=...`.
headers = {}

# Add API key only when configured.
if API_KEY:
    headers["x-api-key"] = API_KEY


# -------------- Health check --------------
print(f"Checking service health at {HEALTH_URL} ...")
try:
    health_resp = requests.get(HEALTH_URL, headers=headers, timeout=10)
    print(f"Health status code: {health_resp.status_code}")

    if health_resp.status_code == 200:
        print("✅ healthz OK:")
        try:
            print(json.dumps(health_resp.json(), indent=2))
        except Exception:
            print(health_resp.text)
    else:
        print(f"❌ healthz returned an error: {health_resp.text}")

except Exception as e:
    print(f"❌ Error while calling /healthz: {e}")


# -------------- Local test files --------------
BASE = Path(__file__).resolve().parent

FILES = {
    "test.png":  (BASE / "data_test" / "test.png",  "image/png"),
    "test.jpeg": (BASE / "data_test" / "test.jpeg", "image/jpeg"),
    "test.jpg":  (BASE / "data_test" / "test.jpg",  "image/jpeg"),
    "test.pdf":  (BASE / "data_test" / "test.pdf",  "application/pdf"),
    "test.pptx": (
        BASE / "data_test" / "test.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
}

print("\n-------------- OCR file tests --------------")

for name, (path, mime) in FILES.items():
    if not path.exists():
        print(f"⚠️  Skipping {name}: file not found at {path}")
        continue

    print(f"\n📄 Sending {name} → {API_URL}")
    with path.open("rb") as f:
        files = {
            "file": (path.name, f, mime),
        }
        try:
            response = requests.post(API_URL, headers=headers, files=files, timeout=60)
        except Exception as e:
            print(f"❌ Error while calling /ocr with {name}: {e}")
            continue

    # Handle response status.
    if response.status_code == 200:
        try:
            data = response.json()
        except Exception:
            print("✅ Raw response received (non-JSON):")
            print(response.text)
            continue

        # Show a short summary if the fields are present
        extracted = data.get("extracted_text", "")
        timings = data.get("timings_ms", {})

        print("✅ JSON response received:")
        print(f"- file: {name}")
        print(f"- extracted_text length: {len(extracted)} chars")
        print(f"- timings_ms: {timings}")
        print("- full JSON payload:")
        print(json.dumps(data, indent=2))
    else:
        print(f"❌ Error {response.status_code} for {name}: {response.text}")

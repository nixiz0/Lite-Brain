import requests, json

# Base URL of the embedding API.
API_URL = "http://127.0.0.1:9005/embed"
HEALTH_URL = "http://127.0.0.1:9005/embed/healthz"

# Optional API key if the server is configured with authentication.
API_KEY = ""  # Fill if you enabled an API key in your environment

# HTTP headers required by the API.
headers = {
    "Content-Type": "application/json",
}

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
        print(json.dumps(health_resp.json(), indent=2))
    else:
        print(f"❌ healthz returned an error: {health_resp.text}")

except Exception as e:
    print(f"❌ Error while calling /healthz: {e}")


# -------------- Embed request payload --------------
# Payload containing the text(s) to encode and encoding options.
payload = {
    "texts": ["Hello, this is a vectorization test with bge-m3."],
    "options": {
        "return_dense": True,
        "normalize_dense": True,
        "return_sparse": False,
        "return_colbert": False,
    },
}


# -------------- Send embed request --------------
# Send the embedding request.
print(f"Sending request to {API_URL} ...")
response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

# Handle response status.
if response.status_code == 200:
    data = response.json()
    print("✅ Response received:")
    print(json.dumps(data, indent=2), "...")
else:
    print(f"❌ Error {response.status_code}: {response.text}")

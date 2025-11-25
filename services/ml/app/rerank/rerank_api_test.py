import requests, json

# Base URLs for the rerank API.
API_URL = "http://127.0.0.1:9005/rerank"
HEALTH_URL = "http://127.0.0.1:9005/rerank/healthz"

# Optional API key if the rerank service is secured.
API_KEY = ""  # Fill this if you configured an API key in your environment.

# Prepare default HTTP headers.
headers = {
    "Content-Type": "application/json",
}

# Attach API key only when defined.
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


# -------------- Reranking request payload --------------
query = "What are the advantages of the BGE model for RAG?"

# Candidate passages with metadata preserved in output.
items = [
    {
        "text": (
            "The BGE-m3 model allows for dense embeddings,"
            "sparseness-aware and multi-vector, which is very useful "
            "for hybrid research."
        ),
        "metadata": {"id": 1, "source": "doc_bge_m3"},
    },
    {
        "text": (
            "Cats are very popular pets, "
            "known for their independence."
        ),
        "metadata": {"id": 2, "source": "doc_chat"},
    },
    {
        "text": (
            "For a high-performing RAG pipeline, one can combine a model "
            "embeddings like BGE-m3 with a cross-encoder type reranking model."
        ),
        "metadata": {"id": 3, "source": "doc_rag"},
    },
]

payload = {
    "query": query,
    "items": items,
    "top_k": 3,     # Returns all items but sorted by score.
    "return_scores": True,
}


# -------------- Send rerank request --------------
print(f"\nSending request to {API_URL} ...")
response = requests.post(API_URL, headers=headers, data=json.dumps(payload))

if response.status_code == 200:
    data = response.json()
    print("✅ Response received:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    print("\nSorted results (score + metadata + text):")
    for r in data.get("results", []):
        print(
            f"- score={r['score']:.4f} | "
            f"id={r.get('metadata', {}).get('id')} | "
            f"text={r['text'][:80]}..."
        )

else:
    print(f"❌ Error {response.status_code}: {response.text}")

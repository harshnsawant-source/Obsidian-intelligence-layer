import requests
import json


OLLAMA_URL = "http://localhost:11434/api/generate"

payload = {

    "model": "qwen3.5:4b",

    "prompt": "What is the capital of France?",

    "stream": False

}

response = requests.post(

    OLLAMA_URL,

    json=payload,

    timeout=600

)

print("STATUS:")
print(response.status_code)

print("\nFULL RESPONSE:")
print(
    json.dumps(
        response.json(),
        indent=2
    )
)
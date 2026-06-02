import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3.5:4b",
        "prompt": "Say hello",
        "stream": False
    }
)

print(response.status_code)
print(response.text)
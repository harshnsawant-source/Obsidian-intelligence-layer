import requests


OLLAMA_URL = "http://localhost:11434/api/generate"

MODEL_NAME = "qwen3.5:4b"


def query_llm(prompt):

    payload = {

        "model": MODEL_NAME,

        "prompt": prompt,

        "stream": False,

        "options": {

            "temperature": 0.2,

            "num_predict": 8000

        }

    }

    try:

        response = requests.post(

            OLLAMA_URL,

            json=payload,

            timeout=600

        )

        response.raise_for_status()

        data = response.json()

        print("\n=== DEBUG JSON ===\n")
        print(data)

        result = data.get(
            "response",
            ""
        ).strip()

        if result:

            return result

        thinking = data.get(
            "thinking",
            ""
        ).strip()

        if thinking:

            return (

                "[NO FINAL ANSWER GENERATED]\n\n"

                + thinking

            )

        return "No response generated."

    except Exception as error:

        return f"LLM ERROR: {error}"
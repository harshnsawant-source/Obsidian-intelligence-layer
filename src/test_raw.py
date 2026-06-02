from core.llm_engine import query_llm

result = query_llm(
    "What is the capital of France?"
)

print("RESULT:")
print(repr(result))
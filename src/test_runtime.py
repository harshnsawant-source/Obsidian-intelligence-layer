from capability.core.runtime_context import RuntimeContext


ctx = RuntimeContext()

path = ctx.memory.write(

    "working",

    "test_memory.md",

    "Runtime is operational."

)

print(path)

content = ctx.memory.read(

    "working",

    "test_memory.md"

)

print(content)

ctx.trace.log(

    "test-agent",

    "runtime validation",

    "success"

)

print("Trace written.")
from pathlib import Path

root = Path("knowledge/vault")

print("EXISTS:", root.exists())

for file in root.glob("*"):

    print(file)
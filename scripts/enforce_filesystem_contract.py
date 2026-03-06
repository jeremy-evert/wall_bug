import json
from pathlib import Path

CONTRACT_FILE = "automation/filesystem_contract.json"


def enforce_contract():

    contract = json.loads(Path(CONTRACT_FILE).read_text())

    created_dirs = []
    created_files = []

    for d in contract.get("directories", []):
        p = Path(d)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(p))

    for f in contract.get("files", []):
        p = Path(f)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch()
            created_files.append(str(p))

    print("Filesystem contract verified")

    if created_dirs:
        print("Created directories:")
        for d in created_dirs:
            print("  ", d)

    if created_files:
        print("Created files:")
        for f in created_files:
            print("  ", f)


if __name__ == "__main__":
    enforce_contract()

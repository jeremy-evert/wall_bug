import subprocess
from pathlib import Path


def enforce_contract():
    subprocess.run(
        ["python", "scripts/enforce_filesystem_contract.py"],
        check=True,
    )


def ensure_task_filesystem(task):

    for f in task.get("files", []):
        path = Path(f)
        path.parent.mkdir(parents=True, exist_ok=True)


def verify_task_files(task):

    missing = []

    for f in task.get("files", []):
        if not Path(f).exists():
            missing.append(f)

    if missing:
        raise RuntimeError(
            "Task expected files missing:\n" + "\n".join(missing)
        )

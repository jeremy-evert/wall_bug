#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

TASK_FILE = "automation/wall_bug_tasks.json"

MAX_WORKERS = 4
MAX_RETRIES = 5


# --------------------------------------------------------
# filesystem contract
# --------------------------------------------------------

def enforce_contract():
    subprocess.run(
        ["python", "scripts/enforce_filesystem_contract.py"],
        check=True,
    )


# --------------------------------------------------------
# task utilities
# --------------------------------------------------------

def load_tasks():
    with open(TASK_FILE) as f:
        tasks = json.load(f)

    for t in tasks:
        t.setdefault("status", "todo")

    return tasks


def save_tasks(tasks):
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def get_pending(tasks):
    return [t for t in tasks if t["status"] == "todo"]


# --------------------------------------------------------
# filesystem helpers
# --------------------------------------------------------

def ensure_task_filesystem(task):
    for f in task.get("files", []):
        Path(f).parent.mkdir(parents=True, exist_ok=True)


def verify_task_files(task):

    missing = []

    for f in task.get("files", []):
        if not Path(f).exists():
            missing.append(f)

    if missing:
        raise RuntimeError(
            "Expected files missing:\n" + "\n".join(missing)
        )


# --------------------------------------------------------
# git helpers
# --------------------------------------------------------

def git_has_changes():

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
    )

    return bool(result.stdout.strip())


def git_commit(task_id):

    if not git_has_changes():
        print("No changes detected, skipping commit.")
        return

    subprocess.run(["git", "add", "."])

    subprocess.run(
        ["git", "commit", "-m", f"Codex task {task_id}"],
        check=True,
    )


def get_last_diff():

    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True,
    )

    return result.stdout.strip()


# --------------------------------------------------------
# prompt builder
# --------------------------------------------------------

def build_prompt(task, previous_error=None, last_diff=None):

    files = "\n".join(task["files"])

    retry_section = ""
    if previous_error:
        retry_section = f"""
PREVIOUS FAILURE
----------------
{previous_error}
Fix the issue above.
"""

    diff_section = ""
    if last_diff:
        diff_section = f"""
LAST CHANGES MADE
-----------------
{last_diff}
"""

    return f"""
You are a senior Python engineer.

PROJECT
-------
Wall_Bug

A CLI tool that captures spoken ideas and converts them into
structured notes.

TASK
----
{task['description']}

FILES YOU MAY MODIFY
--------------------
{files}

RULES
-----
Modify ONLY these files.

OUTPUT FORMAT
-------------
FILE: path/to/file.py
<file contents>

{retry_section}
{diff_section}
"""


# --------------------------------------------------------
# codex execution
# --------------------------------------------------------

def run_codex(prompt):

    result = subprocess.run(
        ["codex", "exec", prompt],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result.stdout


# --------------------------------------------------------
# safe file application
# --------------------------------------------------------

def apply_changes(output):

    current_file = None
    buffer = []

    for line in output.splitlines():

        if line.startswith("FILE:"):

            if current_file:
                write_safe(current_file, "\n".join(buffer))
                buffer = []

            current_file = line.replace("FILE:", "").strip()

        else:
            buffer.append(line)

    if current_file:
        write_safe(current_file, "\n".join(buffer))


def write_safe(path, content):

    if content.strip() == "":
        raise RuntimeError("Codex returned empty file")

    with tempfile.TemporaryDirectory() as tmp:

        tmp_file = Path(tmp) / Path(path).name
        tmp_file.write_text(content)

        subprocess.run(
            ["python", "-m", "py_compile", str(tmp_file)],
            check=True
        )

        Path(path).write_text(content + "\n")


# --------------------------------------------------------
# testing
# --------------------------------------------------------

def run_tests():

    result = subprocess.run(["pytest"])

    if result.returncode != 0:
        raise RuntimeError("Tests failed")


# --------------------------------------------------------
# task executor
# --------------------------------------------------------

def execute_task(task):

    print("\n===================================")
    print("Running:", task["id"])
    print(task["description"])
    print("===================================\n")

    ensure_task_filesystem(task)

    retries = 0
    previous_error = None
    previous_diff = None

    while retries < MAX_RETRIES:

        try:

            last_diff = get_last_diff()

            prompt = build_prompt(task, previous_error, last_diff)

            output = run_codex(prompt)

            apply_changes(output)

            verify_task_files(task)

            run_tests()

            git_commit(task["id"])

            print("✅ Task completed\n")

            return True

        except Exception as e:

            previous_error = str(e)
            current_diff = get_last_diff()

            print("Codex error:", previous_error)

            if current_diff == previous_diff:
                print("Retry produced identical diff. Aborting.\n")
                return False

            previous_diff = current_diff
            retries += 1

    return False


# --------------------------------------------------------
# orchestrator
# --------------------------------------------------------

def main():

    print("\n==============================")
    print(" Wall_Bug Codex Orchestrator ")
    print("==============================\n")

    enforce_contract()

    tasks = load_tasks()

    pending = get_pending(tasks)

    if not pending:
        print("No tasks remaining.")
        return

    print(f"{len(pending)} tasks ready\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:

        futures = {pool.submit(execute_task, task): task for task in pending}

        for future in as_completed(futures):

            task = futures[future]

            try:
                success = future.result()
            except Exception as e:
                print("Worker crashed:", e)
                success = False

            if success:
                task["status"] = "done"
            else:
                task["status"] = "failed"

            save_tasks(tasks)

    print("\nRun complete\n")


if __name__ == "__main__":
    main()

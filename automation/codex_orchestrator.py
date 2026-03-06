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
# repo scanning
# --------------------------------------------------------

def build_repo_tree(root="src", max_depth=4):

    root = Path(root)

    if not root.exists():
        return ""

    lines = []

    for path in sorted(root.rglob("*")):

        depth = len(path.relative_to(root).parts)

        if depth > max_depth:
            continue

        indent = "  " * depth

        if path.is_dir():
            lines.append(f"{indent}{path.name}/")
        else:
            lines.append(f"{indent}{path.name}")

    return "\n".join(lines)


def load_file_context(files):

    context = []

    for f in files:

        path = Path(f)

        if not path.exists():
            continue

        try:
            text = path.read_text()[:4000]
        except Exception:
            continue

        context.append(
            f"\nFILE CONTENT ({f})\n-------------------\n{text}\n"
        )

    return "\n".join(context)


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
# incremental build
# --------------------------------------------------------

def task_is_up_to_date(task):

    inputs = task.get("inputs", [])
    outputs = task.get("outputs", [])

    if not outputs:
        return False

    for f in outputs:
        if not Path(f).exists():
            return False

    if not inputs:
        return True

    newest_input = max(
        Path(f).stat().st_mtime
        for f in inputs
        if Path(f).exists()
    )

    oldest_output = min(
        Path(f).stat().st_mtime
        for f in outputs
    )

    return oldest_output >= newest_input


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

def repo_diff():

    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True
    )

    return result.stdout.strip()


def git_has_changes():

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
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


# --------------------------------------------------------
# prompt builder
# --------------------------------------------------------

def build_prompt(task, previous_error=None, last_diff=None):

    repo_tree = build_repo_tree()

    files = "\n".join(task["files"])

    file_context = load_file_context(task["files"])

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

A CLI tool that captures spoken ideas and converts them
into structured notes.

PROJECT STRUCTURE
-----------------
{repo_tree}

TASK
----
{task['description']}

FILES YOU MAY MODIFY
--------------------
{files}

CURRENT FILE CONTENT
--------------------
{file_context}

RULES
-----
Modify ONLY the allowed files.
Do NOT invent modules.
Respect the existing project structure.

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
        text=True
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

            before_diff = repo_diff()

            prompt = build_prompt(task, previous_error, before_diff)

            output = run_codex(prompt)

            apply_changes(output)

            after_diff = repo_diff()

            if before_diff == after_diff:
                print("🟡 Codex produced no changes.\n")
                return True

            verify_task_files(task)

            run_tests()

            git_commit(task["id"])

            print("✅ Task completed\n")

            return True

        except Exception as e:

            previous_error = str(e)
            current_diff = repo_diff()

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

    runnable = []

    for t in tasks:

        if t["status"] != "todo":
            continue

        if task_is_up_to_date(t):

            print(f"⏩ Skipping {t['id']} (up-to-date)")

            t["status"] = "done"
            save_tasks(tasks)

            continue

        runnable.append(t)

    if not runnable:
        print("No tasks remaining.")
        return

    print(f"{len(runnable)} tasks ready\n")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:

        futures = {pool.submit(execute_task, t): t for t in runnable}

        for future in as_completed(futures):

            task = futures[future]

            try:
                success = future.result()
            except Exception as e:
                print("Worker crashed:", e)
                success = False

            task["status"] = "done" if success else "failed"

            save_tasks(tasks)

    print("\nRun complete\n")


if __name__ == "__main__":
    main()

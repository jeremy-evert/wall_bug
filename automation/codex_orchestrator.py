import json
import subprocess
from pathlib import Path

TASK_FILE = "automation/codex_tasks.json"

MAX_TASKS_PER_RUN = 4
MAX_RETRIES = 5


# --------------------------------------------------------
# enforce filesystem contract
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
        return json.load(f)


def save_tasks(tasks):
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def get_pending(tasks):
    pending = [t for t in tasks if t.get("status", "todo") == "todo"]
    return pending[:MAX_TASKS_PER_RUN]


# --------------------------------------------------------
# filesystem guard
# --------------------------------------------------------

def ensure_task_filesystem(task):
    for f in task.get("files", []):
        path = Path(f)
        path.parent.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------
# verify expected files exist
# --------------------------------------------------------

def verify_task_files(task):

    missing = []

    for f in task.get("files", []):
        if not Path(f).exists():
            missing.append(f)

    if missing:
        raise RuntimeError(
            "Task expected files missing:\n" + "\n".join(missing)
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

Fix the issue that caused this failure.
"""

    diff_section = ""
    if last_diff:
        diff_section = f"""

LAST CHANGES MADE
-----------------
{last_diff}
"""

    return f"""
You are a senior Python engineer working on a CLI tool.

PROJECT
-------
BRAT (Brainstorming Revision Assistance Tool)

PROJECT TYPE
------------
Python CLI application.

STRICT ARCHITECTURE RULES
-------------------------
This project MUST NOT include:

- web frontends
- backend servers
- databases
- REST APIs
- authentication systems

The project uses simple Python modules.

ALLOWED PROJECT AREAS
---------------------

src/brat/
scripts/
tests/
docs/

CURRENT TASK
------------

{task['description']}

FILES YOU MAY MODIFY
--------------------

{files}

RULES
-----

1. Modify ONLY the files listed above.
2. If a file does not exist, create it.
3. Write clean Python code.
4. Prefer small focused functions.
5. Add docstrings when appropriate.
6. Do NOT introduce unnecessary dependencies.
7. Do NOT redesign the system.

TESTING
-------

If tests exist, update them.

{retry_section}

{diff_section}

OUTPUT FORMAT
-------------

Return ONLY the files that changed.

Use this exact format:

FILE: path/to/file.py
<file contents>

Do not include markdown.
"""


# --------------------------------------------------------
# run codex
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
# apply codex output
# --------------------------------------------------------

def apply_changes(output):

    current_file = None
    buffer = []

    for line in output.splitlines():

        if line.startswith("FILE:"):

            if current_file:
                Path(current_file).write_text("\n".join(buffer) + "\n")
                buffer = []

            current_file = line.replace("FILE:", "").strip()

        else:
            buffer.append(line)

    if current_file:
        Path(current_file).write_text("\n".join(buffer) + "\n")


# --------------------------------------------------------
# run tests
# --------------------------------------------------------

def run_tests():

    result = subprocess.run(["pytest"])

    if result.returncode != 0:
        raise RuntimeError("Tests failed")


# --------------------------------------------------------
# execute task
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

            # loop protection
            if current_diff == previous_diff:
                print("Retry produced identical diff. Aborting retries.\n")
                return False

            previous_diff = current_diff

            retries += 1

            if retries < MAX_RETRIES:
                print("Retrying with error + diff feedback...\n")
            else:
                print("Max retries reached.\n")

    return False


# --------------------------------------------------------
# main loop
# --------------------------------------------------------

def main():

    print("\n==============================")
    print(" BRAT Codex Orchestrator ")
    print("==============================\n")

    enforce_contract()

    tasks = load_tasks()

    pending = get_pending(tasks)

    if not pending:
        print("No tasks remaining.")
        return

    print(f"{len(pending)} tasks scheduled\n")

    for task in pending:

        success = execute_task(task)

        if success:
            task["status"] = "done"
        else:
            task["status"] = "failed"

        save_tasks(tasks)

    print("\nRun complete\n")


if __name__ == "__main__":
    main()

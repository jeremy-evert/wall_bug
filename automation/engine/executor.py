import subprocess
import tempfile

from .filesystem_guard import ensure_task_filesystem, verify_task_files
from .git_tools import git_commit, get_last_diff
from .codex_runner import run_codex
from .prompt_builder import build_prompt
from .test_runner import run_tests
from pathlib import Path

from .repo_doctor import clean_markdown_blocks


MAX_RETRIES = 5


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
        
        content = "\n".join(buffer) + "\n"
        
        with tempfile.TemporaryDirectory() as tmp:

            tmp_file = Path(tmp) / Path(current_file).name
            tmp_file.write_text(content)

            # verify python syntax before touching repo
            subprocess.run(
                ["python", "-m", "py_compile", str(tmp_file)],
                check=True
            )

            Path(current_file).write_text(content)


        clean_markdown_blocks()


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
                print("Retry produced identical diff. Aborting retries.\n")
                return False

            previous_diff = current_diff

            retries += 1

            if retries < MAX_RETRIES:
                print("Retrying with error + diff feedback...\n")
            else:
                print("Max retries reached.\n")

    return False

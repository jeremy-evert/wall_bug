import subprocess


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

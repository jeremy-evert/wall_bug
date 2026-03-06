import json

TASK_FILE = "automation/codex_tasks.json"
MAX_TASKS_PER_RUN = 5


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

    pending = [t for t in tasks if t.get("status", "todo") == "todo"]

    return pending[:MAX_TASKS_PER_RUN]

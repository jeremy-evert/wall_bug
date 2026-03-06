from engine.task_manager import load_tasks, save_tasks, get_pending
from engine.executor import execute_task
from engine.filesystem_guard import enforce_contract
from ui.dashboard import print_dashboard

from engine.repo_doctor import repo_doctor

def sanitize_llm_code(code: str) -> str:
    lines = code.splitlines()

    cleaned = []
    for line in lines:
        if line.strip().startswith("```"):
            continue
        if line.startswith("I couldn"):
            continue
        cleaned.append(line)

    return "\n".join(cleaned)



def main():

    print("\n==============================")
    print(" BRAT Codex Orchestrator ")
    print("==============================\n")

    enforce_contract()

    tasks = load_tasks()

    print_dashboard(tasks)

    pending = get_pending(tasks)

    if not pending:
        print("No tasks remaining.")
        return

    print(f"{len(pending)} tasks scheduled\n")

    for task in pending:

        repo_doctor()

        success = execute_task(task)

        if success:
            task["status"] = "done"
        else:
            task["status"] = "failed"

        save_tasks(tasks)

        print_dashboard(tasks)

    print("\nRun complete\n")


if __name__ == "__main__":
    main()

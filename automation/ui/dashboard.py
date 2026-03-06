def print_dashboard(tasks):

    total = len(tasks)

    done = sum(1 for t in tasks if t.get("status", "todo") == "done")
    failed = sum(1 for t in tasks if t.get("status", "todo") == "failed")
    todo = sum(1 for t in tasks if t.get("status", "todo") == "todo")

    print("\nBRAT Progress")
    print("---------------------------")
    print(f"✔ completed : {done}")
    print(f"⚙ remaining : {todo}")
    print(f"✖ failed    : {failed}")
    print(f"📦 total    : {total}")
    print("---------------------------\n")

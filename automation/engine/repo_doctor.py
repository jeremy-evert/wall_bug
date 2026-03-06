from pathlib import Path


def clean_llm_artifacts(root="."):

    fixed = 0

    for file in Path(root).rglob("*.py"):

        try:
            text = file.read_text(encoding="utf-8")
        except Exception:
            continue

        lines = text.splitlines()

        cleaned = []
        changed = False

        for line in lines:

            # Remove markdown fences
            if line.strip().startswith("```"):
                changed = True
                continue

            # Remove assistant chatter
            if line.startswith("I couldn"):
                changed = True
                continue

            # Fix smart quotes
            if "’" in line:
                line = line.replace("’", "'")
                changed = True

            cleaned.append(line)

        if changed:
            file.write_text("\n".join(cleaned) + "\n", encoding="utf-8")
            fixed += 1

    return fixed


def fix_empty_modules(root="."):

    fixed = 0

    for file in Path(root).rglob("*.py"):

        try:
            text = file.read_text(encoding="utf-8").strip()
        except Exception:
            continue

        if text == "" or text == "# placeholder":

            file.write_text(
                '"""Auto-generated placeholder module."""\n',
                encoding="utf-8",
            )

            fixed += 1

    return fixed


def ensure_init_files(root="."):

    created = 0

    for path in Path(root).rglob("*"):

        if path.is_dir():

            init = path / "__init__.py"

            if not init.exists():

                try:
                    init.write_text("", encoding="utf-8")
                    created += 1
                except Exception:
                    pass

    return created


def remove_duplicate_tests():

    removed = 0

    seen = {}

    for file in Path("tests").rglob("test_*.py"):

        name = file.name

        if name in seen:

            try:
                file.unlink()
                removed += 1
            except Exception:
                pass

        else:
            seen[name] = file

    return removed


def repo_doctor():

    fixed = 0

    fixed += clean_llm_artifacts("src")
    fixed += clean_llm_artifacts("tests")

    fixed += fix_empty_modules("src")

    created = ensure_init_files("src")

    removed = remove_duplicate_tests()

    if fixed or created or removed:

        print(
            f"🩺 Repo Doctor repaired {fixed} files | "
            f"created {created} init files | "
            f"removed {removed} duplicate tests"
        )

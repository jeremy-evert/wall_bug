def build_prompt(task, previous_error=None, last_diff=None):

    files = "\n".join(task["files"])

    retry_section = ""
    if previous_error:
        retry_section = f"""

PREVIOUS FAILURE
----------------
{previous_error}
"""

    diff_section = ""
    if last_diff:
        diff_section = f"""

LAST CHANGES MADE
-----------------
{last_diff}
"""

    return f"""
You are a senior Python engineer working on BRAT.

TASK
----
{task['description']}

FILES
-----
{files}

RULES
-----
Modify only these files.

{retry_section}

{diff_section}

OUTPUT FORMAT

FILE: path/to/file.py
<file contents>
"""

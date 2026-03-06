import subprocess


def run_tests():

    result = subprocess.run(["pytest"])

    if result.returncode != 0:
        raise RuntimeError("Tests failed")

import time

from services import sandbox

TESTS = [{"args": [[2, 7, 11, 15], 9], "expected": [0, 1]}, {"args": [[3, 3], 6], "expected": [0, 1]}]
GOOD = "def two_sum(nums, target):\n    seen = {}\n    for i, x in enumerate(nums):\n        if target - x in seen:\n            return [seen[target - x], i]\n        seen[x] = i\n"


def test_correct_solution_passes():
    r = sandbox.run_tests(GOOD, "two_sum", TESTS)
    assert r["ok"] and all(x["passed"] for x in r["results"])


def test_wrong_solution_fails_without_crashing():
    r = sandbox.run_tests("def two_sum(a, b):\n    return [9, 9]", "two_sum", TESTS)
    assert r["ok"] and not r["results"][0]["passed"]


def test_infinite_loop_is_stopped():
    t = time.time()
    r = sandbox.run_tests("def two_sum(a, b):\n    while True:\n        pass", "two_sum", TESTS, timeout=5)
    assert time.time() - t < 8
    assert "Time limit" in r["results"][0]["error"]


def test_dangerous_imports_and_files_blocked():
    r = sandbox.run_tests("import os\ndef two_sum(a, b):\n    return os.listdir('/')", "two_sum", TESTS)
    assert "not allowed" in r["compile_error"]
    r = sandbox.run_tests("def two_sum(a, b):\n    return open('/etc/passwd').read()", "two_sum", TESTS)
    assert "open" in r["results"][0]["error"]
    r = sandbox.run_tests("def two_sum(a, b):\n    import subprocess", "two_sum", TESTS)
    assert "not allowed" in r["results"][0]["error"]


def test_memory_bomb_is_contained():
    r = sandbox.run_tests("def two_sum(a, b):\n    return [0] * (10 ** 10)", "two_sum", TESTS, memory_mb=128)
    assert r["results"][0]["error"] and not r["results"][0]["passed"]


def test_syntax_error_reported():
    r = sandbox.run_tests("def two_sum(:", "two_sum", TESTS)
    assert r["compile_error"]


def test_server_process_untouched():
    # candidate code must not be able to change the parent's state
    import os
    before = os.getcwd()
    sandbox.run_tests("def two_sum(a, b):\n    return [0, 1]", "two_sum", TESTS)
    assert os.getcwd() == before

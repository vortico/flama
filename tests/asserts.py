from time import sleep


def assert_recursive_contains(first, second):
    if isinstance(first, dict) and isinstance(second, dict):
        assert first.keys() <= second.keys()

        for k, v in first.items():
            assert_recursive_contains(v, second[k])
    elif isinstance(first, (list, set, tuple)) and isinstance(second, (list, set, tuple)):
        assert len(first) <= len(second)

        for i, _ in enumerate(first):
            assert_recursive_contains(first[i], second[i])
    else:
        assert first == second


def assert_read_from_file(file_path, value, max_sleep=10):
    read_value = None
    i = 0
    while not read_value and i < max_sleep:
        sleep(i)
        with open(file_path) as f:
            read_value = f.read()
        i += 0.1

    assert read_value == value

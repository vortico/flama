from time import sleep


def assert_recursive_contains(expected, value):
    if isinstance(expected, dict) and isinstance(value, dict):
        assert expected.keys() <= value.keys()

        for k, v in expected.items():
            assert_recursive_contains(v, value[k])
    elif isinstance(expected, (list, set, tuple)) and isinstance(value, (list, set, tuple)):
        assert len(expected) <= len(value)

        for i, _ in enumerate(expected):
            assert_recursive_contains(expected[i], value[i])
    else:
        assert expected == value


def assert_read_from_file(file_path, value, max_sleep=10):
    read_value = None
    i = 0
    while not read_value and i < max_sleep:
        sleep(i)
        with open(file_path) as f:
            read_value = f.read()
        i += 0.1

    assert read_value == value

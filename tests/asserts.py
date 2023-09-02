__all__ = ["assert_recursive_contains"]


def assert_recursive_contains(expected, value):
    if isinstance(expected, dict) and isinstance(value, dict):
        assert expected.keys() <= value.keys()

        if expected != value:
            for k, v in expected.items():
                assert_recursive_contains(v, value[k])
    elif isinstance(expected, (list, set, tuple)) and isinstance(value, (list, set, tuple)):
        assert len(expected) <= len(value)

        if expected != value:
            for i, _ in enumerate(expected):
                assert_recursive_contains(expected[i], value[i])
    else:
        assert expected == value

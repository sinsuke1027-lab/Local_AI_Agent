import pytest

def max_value(a, b):
    return a if a > b else b

def sum_one_to_ten():
    return sum(range(1, 11))

def test_max_value_normal():
    assert max_value(3, 5) == 5
    assert max_value(-2, -8) == -2
    assert max_value(0, 0) == 0

def test_max_value_abnormal():
    with pytest.raises(TypeError):
        max_value("a", 5)
    with pytest.raises(TypeError):
        max_value(3, "b")
    with pytest.raises(TypeError):
        max_value(None, 5)

def test_sum_one_to_ten():
    assert sum_one_to_ten() == 55
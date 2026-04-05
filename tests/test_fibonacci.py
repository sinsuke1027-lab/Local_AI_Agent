import pytest
from fibonacci import fibonacci

def test_fibonacci_zero():
    assert fibonacci(0) == []

def test_fibonacci_one():
    assert fibonacci(1) == [0]

def test_fibonacci_two():
    assert fibonacci(2) == [0, 1]

def test_fibonacci_five():
    assert fibonacci(5) == [0, 1, 1, 2, 3]

def test_fibonacci_ten():
    assert fibonacci(10) == [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

def test_fibonacci_negative():
    assert fibonacci(-5) == []

def test_fibonacci_non_integer():
    with pytest.raises(TypeError):
        fibonacci("string")
import pytest
from src.calc import Calculator

def test_add():
    calc = Calculator()
    assert calc.add(1, 2) == 3
    assert calc.add(-1, -1) == -2
    assert calc.add(-1, 1) == 0
    assert calc.add(0, 0) == 0

def test_subtract():
    calc = Calculator()
    assert calc.subtract(10, 5) == 5
    assert calc.subtract(-10, -5) == -5
    assert calc.subtract(-10, 5) == -15
    assert calc.subtract(10, -5) == 15

def test_multiply():
    calc = Calculator()
    assert calc.multiply(2, 3) == 6
    assert calc.multiply(-2, -3) == 6
    assert calc.multiply(-2, 3) == -6
    assert calc.multiply(0, 0) == 0

def test_divide():
    calc = Calculator()
    assert calc.divide(10, 2) == 5
    assert calc.divide(-10, -2) == 5
    assert calc.divide(-10, 2) == -5
    assert calc.divide(10, -2) == -5

    with pytest.raises(ValueError):
        calc.divide(10, 0)

import pytest

class TestCalculator:
    def setup_method(self):
        self.calc = Calculator()

    def test_add_normal(self):
        assert self.calc.add(1, 2) == 3
        assert self.calc.add(-1, -1) == -2
        assert self.calc.add(-1, 1) == 0

    def test_add_zero(self):
        assert self.calc.add(0, 0) == 0
        assert self.calc.add(0, 5) == 5
        assert self.calc.add(5, 0) == 5

    def test_subtract_normal(self):
        assert self.calc.subtract(5, 3) == 2
        assert self.calc.subtract(-1, -1) == 0
        assert self.calc.subtract(-1, 1) == -2

    def test_multiply_normal(self):
        assert self.calc.multiply(2, 3) == 6
        assert self.calc.multiply(-1, -1) == 1
        assert self.calc.multiply(-1, 1) == -1

    def test_multiply_zero(self):
        assert self.calc.multiply(0, 0) == 0
        assert self.calc.multiply(0, 5) == 0
        assert self.calc.multiply(5, 0) == 0

    def test_divide_normal(self):
        assert self.calc.divide(6, 2) == 3
        assert self.calc.divide(-1, -1) == 1
        assert self.calc.divide(-1, 1) == -1

    def test_divide_zero_dividend(self):
        assert self.calc.divide(0, 5) == 0

    def test_divide_by_zero(self):
        with pytest.raises(ValueError):
            self.calc.divide(5, 0)
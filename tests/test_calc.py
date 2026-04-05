# test_calc.py

import pytest
from src.calc import sum_one_to_ten

def test_sum_one_to_ten():
    assert sum_one_to_ten() == 55, "The sum of numbers from 1 to 10 should be 55."

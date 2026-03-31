import pytest
from calc import sum_list

def test_sum_list_integers():
    assert sum_list([1, 2, 3, 4]) == 10

def test_sum_list_floats():
    assert sum_list([1.5, 2.5, 3.5]) == 7.5

def test_sum_list_empty():
    assert sum_list([]) == 0

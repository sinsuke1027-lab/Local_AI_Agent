import pytest
from calc import sum_list_bonus

class TestCalc:
    def test_sum_list_bonus_normal_case(self):
        assert sum_list_bonus([1, 2, -3, 4]) == 7
        assert sum_list_bonus([-1, -2, -3]) == 0
        assert sum_list_bonus([]) == 0
        assert sum_list_bonus([0, 0, 0]) == 0

    def test_sum_list_bonus_with_negative_numbers(self):
        assert sum_list_bonus([1, -2, 3, -4, 5]) == 9

    def test_sum_list_bonus_with_all_positive_numbers(self):
        assert sum_list_bonus([1, 2, 3, 4, 5]) == 15

    def test_sum_list_bonus_with_mixed_types(self):
        with pytest.raises(TypeError):
            sum_list_bonus([1, 'a', 3])

    def test_sum_list_bonus_with_non_integer_elements(self):
        with pytest.raises(TypeError):
            sum_list_bonus([1.0, 2, 3])
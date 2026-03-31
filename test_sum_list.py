import pytest
from typing import List

@pytest.mark.parametrize("numbers, expected", [
    ([1, 2, -3, 4], 7),
    ([-1, -2, -3], 0),
    ([0, 0, 0], 0),
    ([5, 6, -2, -8], 9),
    ([], 0)
])
def test_sum_list_bonus(numbers: List[int], expected: int):
    assert sum_list_bonus(numbers) == expected

@pytest.mark.parametrize("invalid_input", [
    "string",
    [1, "two", 3],
    None
])
def test_invalid_inputs_bonus(invalid_input):
    with pytest.raises(TypeError):
        sum_list_bonus(invalid_input)

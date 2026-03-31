from typing import List

def sum_list_bonus(numbers: List[int]) -> int:
    """
    Calculate the sum of a list of integers, skipping any negative numbers.

    Args:
        numbers: A list of integers to be summed, ignoring negative numbers.

    Returns:
        The total sum of non-negative elements in the list.
        
    Example:
        >>> sum_list_bonus([1, 2, -3, 4])
        7
        >>> sum_list_bonus([-1, -2, -3])
        0
        >>> sum_list_bonus([])
        0
    """
    if not all(isinstance(x, int) for x in numbers):
        raise TypeError("All elements must be integers")
    return sum(filter(lambda x: x >= 0, numbers))

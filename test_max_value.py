import pytest

def test_max_of_two_normal_case():
    assert max_of_two(10, 20) == 20
    assert max_of_two(-1, -5) == -1
    assert max_of_two(0, 0) == 0

def test_max_of_two_edge_case():
    assert max_of_two(1.5, 1.5) == 1.5
    assert max_of_two(float('inf'), 0) == float('inf')
    assert max_of_two(-float('inf'), -float('inf')) == -float('inf')

def test_max_of_two_abnormal_case():
    with pytest.raises(TypeError):
        max_of_two("a", 1)
    with pytest.raises(TypeError):
        max_of_two(1, "b")
    with pytest.raises(TypeError):
        max_of_two([], {})
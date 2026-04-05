import pytest
from unittest.mock import patch

# 関数のモジュールパスを適切に設定してください
from decrement_function import decrement_from_ten

def test_decrement_from_ten_normal():
    with patch('builtins.print') as mock_print:
        decrement_from_ten()
        expected_calls = [pytest.call(i) for i in range(10, -1, -2)]
        mock_print.assert_has_calls(expected_calls, any_order=False)

def test_decrement_from_ten_abnormal():
    # この関数は異常系のテストケースがないため、何もしない
    pass
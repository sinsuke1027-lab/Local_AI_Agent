import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app import app, fibonacci

# テスト用のFastAPIインスタンスはapp.pyからインポート済み
client = TestClient(app)

def test_fibonacci_normal():
    assert fibonacci(0) == []
    assert fibonacci(1) == [0]
    assert fibonacci(2) == [0, 1]
    assert fibonacci(5) == [0, 1, 1, 2, 3]

def test_fibonacci_negative():
    assert fibonacci(-1) == []

def test_get_fibonacci_normal():
    response = client.get("/fibonacci/5")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"fibonacci_sequence": [0, 1, 1, 2, 3]}

def test_get_fibonacci_zero():
    response = client.get("/fibonacci/0")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"fibonacci_sequence": []}

def test_get_fibonacci_negative_input():
    response = client.get("/fibonacci/-1")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"error": "Input must be a non-negative integer"}
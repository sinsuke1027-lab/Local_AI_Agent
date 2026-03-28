#!/bin/bash

# pip のアップグレードと pytest のインストール
pip install --upgrade pip
pip install pytest pytest-cov

# 正しいディレクトリパスの指定
cd /Users/shinsukeimanaka/projects/langgraph-orchestrator
pytest test_calc.py

# pytest の正しくなった使用方法
pytest --cov=src
pytest --junitxml=results.xml

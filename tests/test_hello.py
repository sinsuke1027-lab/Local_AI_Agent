import pytest
from playwright.sync_api import sync_playwright

def test_h1_text():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("file:///Users/shinsukeimanaka/projects/langgraph-orchestrator/index.html")
        
        h1_text = page.inner_text('h1#greeting')
        assert h1_text == "Hello AI!"
        
        browser.close()

if __name__ == "__main__":
    pytest.main(['test_hello.py'])

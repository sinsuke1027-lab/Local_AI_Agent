# ~/projects/langgraph-orchestrator/test_example.py

import pytest
from playwright.sync_api import sync_playwright


def test_example_domain_title():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("https://example.com")
        title = page.title()
        assert title == "Example Domain", f"Expected 'Example Domain', but got '{title}'"
        browser.close()


if __name__ == "__main__":
    pytest.main([__file__])

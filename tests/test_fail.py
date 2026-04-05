# test_fail.py

import pytest
import asyncio
from playwright.async_api import async_playwright

@pytest.mark.anyio
async def test_example_com_title():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("https://example.com")
        
        # Get the title of the page
        actual_title = await page.title()
        expected_title = "Example Domain"
        
        # Assert that the title is as expected
        assert actual_title == expected_title, f"Expected '{expected_title}', but got '{actual_title}'"
        
        await browser.close()


def main():
    asyncio.run(test_example_com_title())


if __name__ == "__main__":
    main()

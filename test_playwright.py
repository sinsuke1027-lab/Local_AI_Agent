from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        # ヘッドレスモードでChromiumを起動
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://example.com')
        title = page.title()
        print(f"成功！ページのタイトル: {title}")
        browser.close()

if __name__ == '__main__':
    run()

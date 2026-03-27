# src/browser_client.py
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import concurrent.futures

class BrowserClient:
    """Playwrightを使用して動的なWebページを取得するクライアント"""

    def _fetch_sync(self, url: str) -> str:
        """実際のPlaywrightの同期処理（別スレッドで呼ばれる）"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # ページ移動（ネットワーク通信が落ち着くまで待機）
            page.goto(url, wait_until="networkidle", timeout=30000)
            
            # ページのHTMLを取得
            html_content = page.content()
            browser.close()

            # HTMLから不要なタグを除去してテキストのみを抽出
            soup = BeautifulSoup(html_content, "html.parser")
            for script_or_style in soup(["script", "style", "header", "footer", "nav"]):
                script_or_style.extract()
            
            text = soup.get_text(separator="\n")
            
            # 空白行の圧縮
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            cleaned_text = "\n".join(chunk for chunk in chunks if chunk)
            
            return cleaned_text[:5000]

    def get_page_content(self, url: str) -> str:
        """指定したURLにアクセスし、テキストを抽出する（スレッドプールで実行）"""
        try:
            # FastAPIのイベントループとの競合を避けるため、別スレッドで実行
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._fetch_sync, url)
                return future.result()
        except Exception as e:
            return f"ページ取得エラー: {str(e)}"

# 簡単なテスト用
if __name__ == "__main__":
    client = BrowserClient()
    print(client.get_page_content("https://example.com"))
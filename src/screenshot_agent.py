"""
screenshot_agent.py — M8-3: Playwright を使った実行中アプリのスクリーンショット撮影

browser_client.py と同じ sync_playwright + ThreadPoolExecutor パターンを採用。
FastAPI/Streamlit のイベントループとの競合を避けるため別スレッドで実行する。

M5-3（Claude Vision連携）との接続点:
  capture_screenshot() の戻り値 `path` を state.py の `screenshot_path` に格納し、
  vision_agent.py の入力として使う想定。
"""

import concurrent.futures
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

SCREENSHOTS_DIR = Path(__file__).parents[1] / "screenshots"
VIEWPORT        = {"width": 1280, "height": 800}
TIMEOUT_MS      = 10_000   # 10秒


def _build_save_path(project_name: str) -> Path:
    """スクリーンショットの保存先パスを生成する"""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    # project_name に使えない文字を除去
    safe_name = "".join(c for c in project_name if c.isalnum() or c in "-_")[:40] or "app"
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    return SCREENSHOTS_DIR / f"{safe_name}_{timestamp}.png"


def _capture_sync(url: str, save_path: str) -> dict:
    """Playwright 同期 API でスクリーンショットを撮影する（別スレッド内で呼ばれる）"""
    with sync_playwright() as p:
        # macOS launchd 環境では --no-sandbox / --disable-setuid-sandbox が必要。
        # これらがないと chromium_headless_shell が SIGKILL で即時終了する。
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page()
            page.set_viewport_size(VIEWPORT)

            page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            # Streamlit の描画完了を少し待つ
            try:
                page.wait_for_load_state("networkidle", timeout=TIMEOUT_MS)
            except Exception:
                # networkidle が来なくてもキャプチャは試みる
                pass

            page.screenshot(path=save_path, full_page=False)

        finally:
            browser.close()

    return {
        "success":     True,
        "path":        save_path,
        "url":         url,
        "captured_at": datetime.now().isoformat(),
        "error":       None,
    }


def capture_screenshot(
    url: str,
    project_name: str = "app",
    save_path: str | None = None,
) -> dict:
    """
    指定URLのスクリーンショットを撮影して保存する。

    Args:
        url:          撮影対象のURL
        project_name: ファイル名プレフィックスに使うプロジェクト名
        save_path:    保存先の絶対パス。None の場合は screenshots/ に自動命名

    Returns:
        {
            "success":     bool,
            "path":        str,   # 保存先の絶対パス
            "url":         str,
            "captured_at": str,   # ISO形式の撮影日時
            "error":       str | None
        }
    """
    if save_path is None:
        save_path = str(_build_save_path(project_name))

    logger.info("Screenshot: capturing %s → %s", url, save_path)

    try:
        # browser_client.py と同じパターン: 別スレッドで sync_playwright を実行
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future  = executor.submit(_capture_sync, url, save_path)
            result  = future.result(timeout=TIMEOUT_MS / 1000 + 5)

        logger.info("Screenshot: saved to %s", save_path)
        return result

    except concurrent.futures.TimeoutError:
        msg = f"タイムアウト ({TIMEOUT_MS // 1000}秒)"
        logger.warning("Screenshot: timeout for %s", url)
        return {"success": False, "path": None, "url": url, "captured_at": None, "error": msg}

    except Exception as e:
        msg = str(e)
        logger.error("Screenshot: failed for %s — %s", url, msg)
        return {"success": False, "path": None, "url": url, "captured_at": None, "error": msg}

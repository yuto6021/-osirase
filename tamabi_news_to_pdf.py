"""
tamabi_news_to_pdf.py

多摩美術大学（tamabi.ac.jp）のお知らせ記事を
1記事=1PDFとしてフルページスクショ保存するスクリプト。

使い方:
    python tamabi_news_to_pdf.py --limit 3          # 最初の3件を保存（動作確認用）
    python tamabi_news_to_pdf.py --headless          # ブラウザ画面なしで実行
    python tamabi_news_to_pdf.py --limit 0           # 全件保存（0=無制限）
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from PIL import Image

DEFAULT_LIST_URL = "https://www.tamabi.ac.jp/news/"

WINDOWS_FORBIDDEN = r'[\\/:*?"<>|]'


def safe_filename(s: str, max_len: int = 160) -> str:
    """Windowsで使えない文字を除去し、長さを制限したファイル名を返す。"""
    s = re.sub(WINDOWS_FORBIDDEN, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len] if len(s) > max_len else s


def normalize_date(text: str) -> str:
    """日付文字列を YYYY-MM-DD 形式に正規化する。"""
    t = text.strip()
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(20\d{2})[./-](\d{2})[./-](\d{2})", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return "unknown-date"


def png_to_pdf(png: Path, pdf: Path) -> None:
    """PNG画像をPDFファイルに変換する。"""
    img = Image.open(png).convert("RGB")
    img.save(pdf, "PDF", resolution=300.0)


def same_host(url: str, host: str) -> bool:
    """URLのホスト部分が指定ホストと一致するか確認する。"""
    try:
        return urlparse(url).netloc == host
    except Exception:
        return False


def collect_records(page, list_url: str, limit: int) -> list[tuple[str, str, str]]:
    """一覧ページから（日付, タイトル, URL）のリストを収集する。"""
    page.goto(list_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    base_host = urlparse(list_url).netloc
    anchors = page.query_selector_all("a[href]")

    records: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for a in anchors:
        href = a.get_attribute("href") or ""
        if not href:
            continue

        abs_url = page.evaluate(
            "([base, href]) => new URL(href, base).toString()",
            [page.url, href],
        )

        if not same_host(abs_url, base_host):
            continue
        if "/news/" not in abs_url:
            continue
        if abs_url.rstrip("/") == list_url.rstrip("/"):
            continue
        if abs_url in seen:
            continue

        # 親要素をさかのぼってテキストを取得（日付・タイトルの推定に使用）
        container = a
        for _ in range(4):
            parent = container.evaluate_handle("el => el.parentElement")
            if not parent:
                break
            container = parent

        text = (container.evaluate("el => el.innerText") or "").strip()
        link_text = (a.inner_text() or "").strip()

        m = re.search(r"(20\d{2}[./-]\d{2}[./-]\d{2})", text)
        date_s = normalize_date(m.group(1)) if m else "unknown-date"

        title = link_text
        if len(title) < 4:
            title = text
            title = re.sub(r"20\d{2}[./-]\d{2}[./-]\d{2}", "", title)
            title = re.sub(r"\s+", " ", title).strip()
        title = title if title else "untitled"

        records.append((date_s, title, abs_url))
        seen.add(abs_url)

        if limit and len(records) >= limit:
            break

    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="多摩美お知らせを1記事=1PDFで保存する")
    ap.add_argument("--list-url", default=DEFAULT_LIST_URL, help="お知らせ一覧ページのURL")
    ap.add_argument("--out", default="tamabi_news_pdfs", help="出力ディレクトリ")
    ap.add_argument("--limit", type=int, default=5, help="取得件数上限（0=全件）")
    ap.add_argument("--headless", action="store_true", help="ヘッドレスで実行")
    ap.add_argument("--keep-png", action="store_true", help="中間PNGファイルを残す")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        records = collect_records(page, args.list_url, args.limit)

        if not records:
            raise RuntimeError(
                "記事リンクを検出できませんでした。\n"
                "ヒント: --headless を外して画面を確認するか、"
                "collect_records() 内のセレクタ条件（'/news/' フィルタなど）を"
                "サイトのURL構造に合わせて調整してください。"
            )

        print(f"found: {len(records)} articles")

        for i, (date_s, title, url) in enumerate(records, start=1):
            base = safe_filename(f"{date_s}_{title}")
            png_path = out_dir / f"{base}.png"
            pdf_path = out_dir / f"{base}.pdf"

            print(f"[{i}/{len(records)}] open: {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(700)

            page.screenshot(path=str(png_path), full_page=True)
            png_to_pdf(png_path, pdf_path)

            if not args.keep_png:
                try:
                    png_path.unlink()
                except OSError:
                    pass

            print(f"  saved: {pdf_path}")

        browser.close()


if __name__ == "__main__":
    main()

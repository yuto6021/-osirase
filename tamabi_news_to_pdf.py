"""
tamabi_news_to_pdf.py
多摩美術大学のお知らせ一覧 (https://www.tamabi.ac.jp/news/) から
記事を取得し、1記事 = 1PDF（ページ全体スクリーンショット）で保存します。

ファイル名形式: YYYY-MM-DD_タイトル.pdf

使い方:
    python tamabi_news_to_pdf.py
    python tamabi_news_to_pdf.py --limit 5
    python tamabi_news_to_pdf.py --headless --out ./output
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError
from PIL import Image

# ─────────────────────────────────────────
# 定数
# ─────────────────────────────────────────
LIST_URL = "https://www.tamabi.ac.jp/news/"
BASE_HOST = "www.tamabi.ac.jp"
DEFAULT_OUT = "tamabi_news_pdfs"
# Windows 禁則文字パターン（\ / : * ? " < > |）
WINDOWS_FORBIDDEN = "[\\\\/:*?\"<>|]"

# ページが描画されるまでの最大待機時間（ミリ秒）
LOAD_WAIT_MS = 4000
# 記事ページを開いた後の追加待機（ミリ秒）
ARTICLE_WAIT_MS = 1000


# ─────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────
def safe_filename(s: str, max_len: int = 160) -> str:
    """Windows 禁則文字を除去し、長さを制限したファイル名文字列を返す。"""
    s = re.sub(WINDOWS_FORBIDDEN, "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


def normalize_date(text: str) -> str:
    """
    日付テキストを YYYY-MM-DD 形式に正規化する。
    対応フォーマット: YYYY.MM.DD / YYYY/MM/DD / YYYY-MM-DD / YYYY年MM月DD日
    """
    t = text.strip()
    for fmt in ("%Y.%m.%d", "%Y/%m/%d", "%Y-%m-%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    # テキスト中に埋まっている日付パターンを探す
    m = re.search(r"(20\d{2})[./-](\d{1,2})[./-](\d{1,2})", t)
    if m:
        y, mo, d = m.group(1), m.group(2).zfill(2), m.group(3).zfill(2)
        return f"{y}-{mo}-{d}"
    return "unknown-date"


def png_to_pdf(png_path: Path, pdf_path: Path) -> None:
    """PNG 画像を PDF に変換して保存する（Pillow）。"""
    img = Image.open(png_path).convert("RGB")
    img.save(pdf_path, "PDF", resolution=150.0)


def abs_url(base: str, href: str) -> str:
    """相対 URL を絶対 URL に変換する。"""
    return urljoin(base, href)


def is_article_url(url: str) -> bool:
    """
    ニュース記事 URL かどうかを判定する。
    - 同一ホスト
    - /news/ 以下のパスで、一覧ページ自身ではない
    """
    try:
        parsed = urlparse(url)
        if parsed.netloc != BASE_HOST:
            return False
        path = parsed.path.rstrip("/")
        # /news そのものや /news/ は除外、/news/xxxx は対象
        return re.match(r"^/news/.+", path) is not None
    except Exception:
        return False


# ─────────────────────────────────────────
# 記事リスト取得
# ─────────────────────────────────────────
def collect_records(page) -> list[tuple[str, str, str]]:
    """
    一覧ページから (日付, タイトル, URL) のリストを返す。

    多摩美サイトは Next.js 製の動的ページのため、DOMが生成される前に
    取得しようとすると空になる。wait_for_selector で描画完了を待つ。

    タイトルにリンクが付いていないレイアウトに対応するため、
    「同じカード/行の中にある <a href>」をリンク元とし、
    カード全体のテキストから日付・タイトルを抽出する。
    """
    # 記事カードが現れるまで待つ（タイムアウト 15 秒）
    try:
        page.wait_for_selector("a[href]", timeout=15000)
    except PWTimeoutError:
        pass

    page.wait_for_timeout(LOAD_WAIT_MS)

    # すべての <a> を取得し、記事 URL に絞る
    anchors = page.query_selector_all("a[href]")
    current_url = page.url

    records: list[tuple[str, str, str]] = []
    seen_urls: set[str] = set()

    for a in anchors:
        href = (a.get_attribute("href") or "").strip()
        if not href:
            continue

        url = abs_url(current_url, href)
        if not is_article_url(url):
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # ── タイトル・日付の取得 ──────────────────────────────────
        # 戦略: リンク要素から親方向に最大 5 段さかのぼり、
        # 日付テキストが見つかった時点でそのコンテナを使う。
        container = a
        date_s = "unknown-date"
        title = ""

        for depth in range(6):
            raw_text = (container.evaluate("el => el.innerText") or "").strip()

            # 日付パターン検索
            m = re.search(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", raw_text)
            if m:
                date_s = normalize_date(m.group(0))

                # タイトル: 日付・余分な空白を除いた残りのテキスト
                title_candidate = re.sub(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", "", raw_text)
                title_candidate = re.sub(r"\s+", " ", title_candidate).strip()

                # リンク文字が十分長ければ優先する
                link_text = (a.inner_text() or "").strip()
                link_text_clean = re.sub(r"20\d{2}[./-]\d{1,2}[./-]\d{1,2}", "", link_text).strip()

                if len(link_text_clean) >= 4:
                    title = link_text_clean
                elif title_candidate:
                    title = title_candidate
                else:
                    title = "untitled"

                break

            # さらに上の親へ
            parent_handle = container.evaluate_handle("el => el.parentElement")
            parent_el = parent_handle.as_element()
            if not parent_el:
                break
            container = parent_el

        # 日付が見つからなかった場合もリンク文字をタイトルとして採用
        if not title:
            title = (a.inner_text() or "untitled").strip() or "untitled"

        records.append((date_s, title, url))

    return records


# ─────────────────────────────────────────
# メイン処理
# ─────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser(
        description="多摩美術大学お知らせを 1記事1PDF でダウンロードします。"
    )
    ap.add_argument(
        "--list-url",
        default=LIST_URL,
        help=f"一覧ページ URL（デフォルト: {LIST_URL}）",
    )
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help=f"PDF 保存先ディレクトリ（デフォルト: {DEFAULT_OUT}）",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="取得する記事数の上限（0 = 無制限）",
    )
    ap.add_argument(
        "--headless",
        action="store_true",
        help="ブラウザ画面を表示しない（デフォルト: 表示あり）",
    )
    ap.add_argument(
        "--keep-png",
        action="store_true",
        help="中間 PNG ファイルを残す（デフォルト: 削除）",
    )
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        print(f"[INFO] 一覧ページを開いています: {args.list_url}")
        page.goto(args.list_url, wait_until="domcontentloaded")

        records = collect_records(page)

        if not records:
            print(
                "[ERROR] 記事リンクを検出できませんでした。\n"
                "        サイトの HTML 構造が変わっている可能性があります。"
            )
            browser.close()
            return

        if args.limit > 0:
            records = records[: args.limit]

        print(f"[INFO] {len(records)} 件の記事を取得しました。")

        for i, (date_s, title, url) in enumerate(records, start=1):
            base_name = safe_filename(f"{date_s}_{title}")
            png_path = out_dir / f"{base_name}.png"
            pdf_path = out_dir / f"{base_name}.pdf"

            print(f"[{i:>3}/{len(records)}] {url}")
            print(f"          日付: {date_s}  タイトル: {title}")

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
            except PWTimeoutError:
                # networkidle がタイムアウトしても描画は完了している場合が多い
                pass

            page.wait_for_timeout(ARTICLE_WAIT_MS)

            page.screenshot(path=str(png_path), full_page=True)
            png_to_pdf(png_path, pdf_path)

            if not args.keep_png:
                try:
                    png_path.unlink()
                except OSError:
                    pass

            print(f"          => 保存: {pdf_path}")

        browser.close()
        print(f"\n[INFO] 完了。PDF は {out_dir.resolve()} に保存されました。")


if __name__ == "__main__":
    main()

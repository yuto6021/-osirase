# -osirase（お知らせ PDF 保存ツール）

多摩美術大学（tamabi.ac.jp）のお知らせ記事を自動で収集し、1記事=1PDFとして保存するツールです。

## 機能

- お知らせ一覧ページから記事URLを自動収集
- 各記事ページをフルページスクショ（縦長ページも全体）
- `YYYY-MM-DD_タイトル.pdf` 形式でPDF保存
- Windowsで使えない文字を自動除去したファイル名生成

## 必要環境

- Python 3.9 以上
- Windows（他のOSでも動作しますが、Windows想定で設計しています）

## インストール

```powershell
pip install -r requirements.txt
python -m playwright install chromium
```

## 使い方

```powershell
# 最初の5件をブラウザ表示ありで保存（動作確認におすすめ）
python tamabi_news_to_pdf.py --limit 5

# ヘッドレス（画面なし）で全件保存
python tamabi_news_to_pdf.py --headless

# 件数・出力先・URLを変更する場合
python tamabi_news_to_pdf.py --limit 10 --out my_pdfs --list-url https://www.tamabi.ac.jp/news/

# 中間PNGファイルを残す場合
python tamabi_news_to_pdf.py --keep-png
```

## 出力

`tamabi_news_pdfs/` フォルダに PDF が保存されます。

例：
```
tamabi_news_pdfs/
  2026-04-01_タイトル例.pdf
  2026-03-28_別の記事タイトル.pdf
  ...
```

## トラブルシューティング

「found: 0 articles」と表示される場合、サイトのDOM構造が変わった可能性があります。
開発者ツールで記事一覧の1件を右クリック → Copy outerHTML をご確認ください。

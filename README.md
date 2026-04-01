# tamabi-news-to-pdf

多摩美術大学のお知らせ一覧（<https://www.tamabi.ac.jp/news/>）から、  
記事 1 件ごとにページ全体のスクリーンショットを取得し、  
**`YYYY-MM-DD_タイトル.pdf`** の形式で保存する Python スクリプトです。

## ファイル構成

```
tamabi_news_to_pdf.py   # メインスクリプト
requirements.txt        # 依存ライブラリ
README.md               # 本ファイル
```

## 動作環境

| 項目 | 内容 |
|------|------|
| OS | Windows 10 / 11（動作確認済み）|
| Python | 3.11 以上推奨 |
| ブラウザ | Playwright が自動管理する Chromium |

---

## インストール（初回のみ）

PowerShell を開き、以下を順に実行します。

```powershell
# 1. 依存ライブラリのインストール
pip install -r requirements.txt

# 2. Playwright 用 Chromium のインストール
python -m playwright install chromium
```

---

## 実行方法

### 基本（ブラウザ表示あり・先頭 5 件）

```powershell
python tamabi_news_to_pdf.py --limit 5
```

### ヘッドレスモード（ブラウザ画面なし）

```powershell
python tamabi_news_to_pdf.py --headless
```

### 全件取得・出力先を指定

```powershell
python tamabi_news_to_pdf.py --out C:\Users\YourName\Desktop\tamabi_pdfs
```

### オプション一覧

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `--list-url` | `https://www.tamabi.ac.jp/news/` | 一覧ページ URL |
| `--out` | `tamabi_news_pdfs` | PDF 保存先フォルダ |
| `--limit N` | 0（無制限） | 取得する記事数の上限 |
| `--headless` | 表示あり | ブラウザを非表示で実行 |
| `--keep-png` | 削除 | 中間 PNG ファイルを残す |

---

## 出力例

```
[INFO] 一覧ページを開いています: https://www.tamabi.ac.jp/news/
[INFO] 30 件の記事を取得しました。
[  1/30] https://www.tamabi.ac.jp/news/12345/
          日付: 2026-03-31  タイトル: 入学式のご案内
          => 保存: tamabi_news_pdfs\2026-03-31_入学式のご案内.pdf
[  2/30] https://www.tamabi.ac.jp/news/12344/
          日付: 2026-03-28  タイトル: 展覧会のお知らせ
          => 保存: tamabi_news_pdfs\2026-03-28_展覧会のお知らせ.pdf
...
[INFO] 完了。PDF は C:\work\tamabi_news_pdfs に保存されました。
```

---

## PDF ファイル名のルール

- 形式: `{YYYY-MM-DD}_{タイトル}.pdf`
- Windows で使用できない文字（`\ / : * ? " < > |`）は除去
- タイトルが 160 文字を超える場合は切り捨て
- 日付が取得できない場合は `unknown-date` になります

---

## トラブルシューティング

### `[ERROR] 記事リンクを検出できませんでした` が出る

サイト側の HTML 構造が変わっている可能性があります。  
Chrome の開発者ツールで一覧ページの記事 1 件の HTML（`Copy outerHTML`）を確認し、  
`collect_records()` 関数のセレクタを調整してください。

### スクリーンショットが真っ白になる

`LOAD_WAIT_MS` / `ARTICLE_WAIT_MS` の値を増やして試してください。

```python
LOAD_WAIT_MS = 6000   # 一覧の読み込み待機（ms）
ARTICLE_WAIT_MS = 2000  # 記事ページの読み込み待機（ms）
```

### Pillow のインストールエラー

```powershell
pip install --upgrade pip
pip install Pillow
```

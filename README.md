# pdf-toc-splitter

目次Markdownに基づきPDFファイルを章・節単位で分割するCLIツール。

Split PDF files into chapters based on a table-of-contents Markdown file.

## 概要

PDFの目次情報をMarkdownファイルとして与えると、指定した階層深さでPDFを分割します。
目次MarkdownはAI（Claude等）を使って目次ページから生成することも、手動で作成することも可能です。

## インストール

```bash
pip install -e .
```

または `uv` を使用する場合:

```bash
uv sync
```

## 使い方

### 基本コマンド

```bash
# python -m での実行
python -m pdf_toc_splitter <input.pdf> <toc.md>

# エントリーポイントでの実行
pdf-toc-splitter <input.pdf> <toc.md>
```

### 主要オプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `-o`, `--output-dir` | `./output` | 出力ディレクトリ |
| `-d`, `--depth` | `1` | 分割する階層の深さ（1〜3） |
| `--offset` | なし | ページオフセット値（Markdown内の設定より優先） |
| `--dry-run` | — | 分割を実行せずファイル一覧を表示する |
| `--prefix-digits` | `2` | 連番の桁数（全階層共通） |
| `--validate-only` | — | バリデーションのみ実行する |

### 使用例

```bash
# 最上位章のみ分割（デフォルト）
pdf-toc-splitter book.pdf toc.md -o ./chapters

# 節レベルまで分割
pdf-toc-splitter book.pdf toc.md --depth 2 -o ./chapters

# 分割内容を確認してから実行
pdf-toc-splitter book.pdf toc.md --dry-run

# 目次のバリデーションのみ
pdf-toc-splitter book.pdf toc.md --validate-only

# ページオフセットをCLIで指定
pdf-toc-splitter book.pdf toc.md --offset 4
```

### 使用フロー

```
1. PDFビューアで元PDFを開き、offset を算出する
   （本文1ページ目の物理ページ番号 − 1）
2. 目次ページをAI（Claude等）に読み込ませ、toc.md を生成する
   （prompts/toc_extraction_prompt.md のプロンプトを使用）
3. toc.md に offset ディレクティブを記入し、内容を確認・修正する
4. --dry-run で出力ファイル一覧を確認する
5. 実際に分割を実行する
```

## 目次Markdownのフォーマット

```markdown
# 書籍タイトル（任意）

<!-- offset: 4 -->

- 第1章 はじめに: 1-15
- 第2章 基本概念: 16-42
  - 2.1 定義: 16-25
  - 2.2 分類: 26-42
- 第3章 応用: 43-80
```

### 主なルール

- リストマーカーは `-`（ハイフン）
- インデントはスペース2個で1階層（最大3階層）
- 各行の形式: `- {タイトル}: {開始ページ}-{終了ページ}`
- ページ番号は目次に印刷されている番号（物理ページ番号ではない）
- `<!-- offset: N -->` でページオフセットを指定（省略時は0）
- `<!-- offset: TODO -->` はAIが算出できなかった場合の暫定値（実分割前に修正が必要）
- `0-0` はページ番号が判読不能だった場合の暫定値（実分割前に修正が必要）

詳細な仕様は [documentation/SPEC.md](documentation/SPEC.md) を参照してください。

## 出力ファイル名の形式

```
{階層連番}_{タイトル}_p{物理開始ページ}-{物理終了ページ}.pdf
```

例（offset=4、depth=1）:

```
01_第1章_はじめに_p5-19.pdf
02_第2章_基本概念_p20-46.pdf
03_第3章_応用_p47-84.pdf
```

## ライセンス

MIT License

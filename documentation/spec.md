# pdf-toc-splitter 仕様書

## リポジトリ情報

| 項目 | 内容 |
|------|------|
| リポジトリ名 | `pdf-toc-splitter` |
| Description | Split PDF files into chapters based on a table-of-contents Markdown file. |
| Visibility | Public |
| License | MIT |
| .gitignore | Python |

---

## 概要

目次（Table of Contents）の情報に基づき、PDFファイルを章・節単位で分割するCLIツール。
目次情報はMarkdownファイルとして外部から与える。目次Markdownの作成手段（人手・AI問わず）に依存しない汎用的な設計とする。

---

## スコープ

本プロジェクトに含めるもの：

1. **目次Markdownのフォーマット定義**
2. **目次PDF → 目次Markdown 生成を補助するプロンプトテンプレート**
3. **目次Markdownを入力としたPDF分割CLIスクリプト**

本プロジェクトに含めないもの：

- 分割後PDFのMarkdown化（別プロジェクトとする）
- PDF本体からの自動目次抽出（PDFブックマーク解析等）
- GUIの提供

---

## 1. 目次Markdownフォーマット定義

### 1.1 フォーマット仕様

ファイル名: `toc.md`（任意）

```markdown
# 書籍タイトルまたはPDFファイル名（任意。メタ情報として扱う）

- 第1章 はじめに: 1-15
- 第2章 基本概念: 16-42
  - 2.1 定義: 16-25
  - 2.2 分類: 26-42
- 第3章 応用: 43-80
  - 3.1 ケーススタディ: 43-60
    - 3.1.1 事例A: 43-50
    - 3.1.2 事例B: 51-60
  - 3.2 まとめ: 61-80
- 付録A 用語集: 81-90
```

### 1.2 構文ルール

| ルール | 説明 |
|--------|------|
| リスト記法 | `-`（ハイフン）によるMarkdownリストを使用する |
| インデント | スペース2個で1階層。ネストは3階層まで許容 |
| 各行の形式 | `- {タイトル}: {開始ページ}-{終了ページ}` |
| ページ番号 | PDFの物理ページ番号（1始まり）。印刷上のページ番号ではない |
| タイトル | 任意の文字列。ファイル名に使用するためOS非許容文字は含めないことを推奨 |
| 見出し行 | `# ...` で始まる行はメタ情報として無視する（任意） |
| 空行 | 無視する |
| コメント | `<!-- ... -->` 形式のHTMLコメントは無視する |

### 1.3 分割粒度の制御

分割は **最上位階層のみ** をデフォルトとする。
オプションにより任意の階層レベルまで分割可能とする。

例：上記の目次で `--depth 1`（デフォルト）の場合、出力は以下の4ファイル：

```
01_第1章_はじめに_p1-15.pdf
02_第2章_基本概念_p16-42.pdf
03_第3章_応用_p43-80.pdf
04_付録A_用語集_p81-90.pdf
```

`--depth 2` の場合、子階層も個別ファイルとして出力する：

```
01_第1章_はじめに_p1-15.pdf
02_第2章_基本概念_p16-42.pdf
02-01_2.1_定義_p16-25.pdf
02-02_2.2_分類_p26-42.pdf
03_第3章_応用_p43-80.pdf
03-01_3.1_ケーススタディ_p43-60.pdf
03-02_3.2_まとめ_p61-80.pdf
04_付録A_用語集_p81-90.pdf
```

### 1.4 バリデーション

目次Markdownの読み込み時に以下を検証する：

- 各行が所定のフォーマットに合致すること
- 開始ページ ≦ 終了ページ であること
- ページ範囲が元PDFの総ページ数を超えないこと
- 同一階層でページ範囲の重複がないこと（警告レベル）

---

## 2. プロンプトテンプレート

### 2.1 目的

目次ページのPDF（または画像）をAIに読み込ませ、上記フォーマットに準拠した `toc.md` を生成させるためのプロンプトテンプレートを提供する。

### 2.2 ファイル

`prompts/toc_extraction_prompt.md` として配置する。

### 2.3 プロンプト要件

プロンプトには以下を含める：

- 出力フォーマットの仕様（セクション1の内容を要約して埋め込む）
- ページ番号はPDFの物理ページ番号であることの指示
- 目次に載っていない前付け・後付けの扱い方の指示
- 出力例
- 「Markdownのコードブロックで出力せよ」等の出力制御指示

### 2.4 使用フロー

```
1. 人間が元PDFから目次ページ部分だけを切り出し、独立したPDFにする
2. そのPDFをAI（Claude等）に読み込ませる際にこのプロンプトを併用する
3. AIが出力した toc.md を必要に応じて人間が微修正する
4. toc.md をPDF分割スクリプトに渡す
```

---

## 3. PDF分割CLIスクリプト

### 3.1 技術スタック

| 項目 | 選定 |
|------|------|
| 言語 | Python 3.10+ |
| PDF操作 | pypdf |
| CLI | argparse（標準ライブラリ） |
| 依存管理 | requirements.txt |

### 3.2 コマンド仕様

```bash
python pdf_toc_splitter.py <input.pdf> <toc.md> [options]
```

#### 引数

| 引数 | 必須 | 説明 |
|------|------|------|
| `input.pdf` | 必須 | 分割対象のPDFファイルパス |
| `toc.md` | 必須 | 目次Markdownファイルパス |

#### オプション

| オプション | デフォルト | 説明 |
|-----------|----------|------|
| `-o`, `--output-dir` | `./output` | 出力ディレクトリ |
| `-d`, `--depth` | `1` | 分割する階層の深さ（1=最上位のみ） |
| `--dry-run` | `false` | 分割を実行せず、生成されるファイル一覧を表示する |
| `--prefix-digits` | `2` | 連番の桁数 |
| `--validate-only` | `false` | 目次Markdownのバリデーションのみ実行する |

### 3.3 出力ファイル名規則

```
{連番}_{タイトル}_p{開始ページ}-{終了ページ}.pdf
```

- 連番: 0埋め。桁数は `--prefix-digits` で制御
- タイトル: 空白は `_` に置換。OS非許容文字（`/\:*?"<>|`）は `_` に置換
- 例: `01_第1章_はじめに_p1-15.pdf`

### 3.4 ディレクトリ構成

```
pdf-toc-splitter/
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
├── pdf_toc_splitter.py        # メインスクリプト（エントリーポイント）
├── toc_parser.py              # 目次Markdownパーサー
├── prompts/
│   └── toc_extraction_prompt.md
├── examples/
│   └── example_toc.md         # 目次Markdownのサンプル
└── tests/
    ├── test_toc_parser.py
    └── test_splitter.py
```

### 3.5 モジュール構成

#### `toc_parser.py`

- `TocEntry` データクラス: タイトル、開始ページ、終了ページ、階層レベル、子エントリのリストを保持
- `parse_toc(filepath: str) -> list[TocEntry]`: 目次Markdownを解析しツリー構造で返す
- `validate_toc(entries: list[TocEntry], total_pages: int) -> list[str]`: バリデーションエラーのリストを返す
- `flatten_toc(entries: list[TocEntry], depth: int) -> list[TocEntry]`: 指定階層までフラット化する

#### `pdf_toc_splitter.py`

- `split_pdf(input_path: str, entries: list[TocEntry], output_dir: str, prefix_digits: int) -> list[str]`: PDFを分割し、出力ファイルパスのリストを返す
- `main()`: CLIエントリーポイント

### 3.6 エラーハンドリング

| エラー | 対処 |
|--------|------|
| 入力PDFが存在しない | エラーメッセージを表示し終了（exit code 1） |
| 目次Markdownが不正 | パースエラー箇所を行番号付きで表示し終了 |
| ページ範囲がPDF総ページ数を超過 | エラーメッセージに総ページ数を含めて表示し終了 |
| 出力ディレクトリが存在しない | 自動作成する |
| 出力ファイルが既に存在する | 上書きする（将来的に `--no-overwrite` オプション追加を検討） |

### 3.7 ログ出力

`print` による標準出力への進捗表示：

```
[INFO] Loaded TOC: 4 entries (depth=1)
[INFO] Input PDF: example.pdf (90 pages)
[INFO] Output directory: ./output
[INFO] Splitting...
[INFO]   1/4: 01_第1章_はじめに_p1-15.pdf (15 pages)
[INFO]   2/4: 02_第2章_基本概念_p16-42.pdf (27 pages)
[INFO]   3/4: 03_第3章_応用_p43-80.pdf (38 pages)
[INFO]   4/4: 04_付録A_用語集_p81-90.pdf (10 pages)
[INFO] Done. 4 files created in ./output
```

---

## 4. テスト方針

- `toc_parser.py` に対するユニットテストを `tests/test_toc_parser.py` に配置
  - 正常系: 単階層、複数階層、空行・コメント含みの目次
  - 異常系: フォーマット不正、ページ範囲逆転、ページ重複
- `pdf_toc_splitter.py` に対するユニットテストを `tests/test_splitter.py` に配置
  - 小さなテスト用PDFを `pypdf` で動的に生成してテストする
- テストフレームワーク: `pytest`

---

## 5. 将来の拡張候補（本バージョンではスコープ外）

- PDFブックマーク（しおり）からの自動目次抽出
- `--no-overwrite` オプション
- ページ範囲ギャップの検出と警告
- 分割後PDFへのブックマーク付与
- 設定ファイル（YAML/TOML）対応

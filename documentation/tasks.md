# pdf-toc-splitter 実装タスク

SPEC.md を参照して実装を進めてください。
各タスクは前のタスクが完了・確認された後に着手してください。

---

## タスク0: プロジェクト初期構成

SPEC.md のセクション3.1・3.3 に従い、プロジェクトの骨格を作成してください。

やること:

- pyproject.toml に以下を追加・設定
  - プロジェクトメタ情報（name, version, description, license, requires-python = ">=3.12"）
  - dependencies に pypdf を追加
  - [project.scripts] に pdf-toc-splitter エントリーポイントを定義
  - [tool.pytest.ini_options] の testpaths が src/tests であることを確認（既存設定があれば維持）
  - dev dependencies に pytest を追加
- src/pdf_toc_splitter/ ディレクトリに __init__.py, __main__.py, cli.py, toc_parser.py, splitter.py を空ファイルとして作成
- src/tests/ ディレクトリに test_toc_parser.py, test_splitter.py を空ファイルとして作成
- prompts/ ディレクトリを作成
- examples/ ディレクトリを作成

完了条件:

- `python -m pdf_toc_splitter` が（何も実装していないので即終了でよいが）インポートエラーにならないこと
- `pytest` が実行でき、テスト0件で正常終了すること

---

## タスク1: toc_parser.py — パーサー実装

SPEC.md のセクション1.1〜1.3 および 3.4 の toc_parser.py 部分に従い、目次Markdownのパース機能を実装してください。

やること:

- TocEntry データクラスの定義（タイトル、開始ページ、終了ページ、階層レベル、子エントリリスト、元ファイル行番号）
  - 開始・終了ページが 0 の場合は暫定値（判読不能）
- parse_toc(filepath: str) -> tuple[list[TocEntry], int | None] の実装
  - Markdownリスト行のパース（インデントによる階層判定）
  - `<!-- offset: N -->` ディレクティブの読み取り（整数 → int, TODO → None, 未指定 → 0）
  - `# ...` 見出し行、空行、通常HTMLコメントのスキップ
- flatten_toc(entries: list[TocEntry], depth: int) -> list[TocEntry] の実装
  - 深さ優先・出現順でフラット化

実装しないこと:

- validate_toc（タスク2で実装）
- CLI関連（タスク4で実装）

完了条件:

- 以下の目次Markdownを正しくパースできること

```markdown
# テスト文書

<!-- offset: 4 -->

- 第1章 はじめに: 1-15
- 第2章 基本概念: 16-42
  - 2.1 定義: 16-25
  - 2.2 分類: 26-42
- 第3章 応用: 43-80
  - 3.1 ケーススタディ: 43-60
    - 3.1.1 事例A: 43-50
    - 3.1.2 事例B: 51-60
  - 3.2 まとめ: 61-80
```

---

## タスク2: toc_parser.py — バリデーション実装 + パーサーテスト

SPEC.md のセクション1.6 および 4.1 に従い、バリデーション機能を実装し、パーサー全体のテストを書いてください。

やること:

- validate_toc(entries, total_pages, offset, strict=True) -> tuple[list[str], list[str]] の実装
  - セクション1.6 のエラー項目すべて（フォーマット合致、タイトル非空、ページ番号正値、ページ範囲整合、総ページ数以内、子範囲が親範囲内、インデント連続性、深さ上限、ページ範囲非重複、暫定値残留）
  - 0-0 エントリに対するチェックスキップ（ページ範囲整合・総ページ数・子範囲・重複）
  - strict=True 時: 0-0 および offset=None をエラー
  - strict=False 時: 0-0 および offset=None を警告
  - 警告項目（ページ範囲ギャップ）
- src/tests/test_toc_parser.py の実装
  - SPEC.md セクション4.1 に記載の全テスト観点

完了条件:

- pytest が全件パスすること
- 正常系・異常系・暫定値・警告系すべてのテストケースが存在すること

---

## タスク3: splitter.py — 分割ロジック実装 + テスト

SPEC.md のセクション1.5、3.4 の splitter.py 部分、および 4.2 に従い、PDF分割機能を実装してください。

やること:

- generate_filename の実装
  - タイトルサニタイズ（半角/全角スペース→_, OS非許容文字→_, 先頭末尾トリム, 連続_圧縮）
  - 物理ページ番号（offset適用後）をファイル名に使用
- build_output_plan の実装
  - 階層連番の生成（深さ優先・出現順、各階層独立採番、全階層共通prefix-digits）
  - 桁あふれ時の自動拡張と警告
- validate_output_plan の実装
  - ファイル名重複検出
- split_pdf の実装
  - pypdf を使用したページ抽出と個別PDF出力
- src/tests/test_splitter.py の実装
  - SPEC.md セクション4.2 に記載のテスト観点（分割機能、ファイル名生成、出力計画検証）
  - テスト用PDFは pypdf で動的に生成する

完了条件:

- pytest が全件パスすること（タスク2のテストも含む）
- 10ページのテスト用PDFを3エントリに分割し、各出力PDFのページ数が正しいこと

---

## タスク4: cli.py — CLI実装 + CLIテスト

SPEC.md のセクション3.2、3.4 の cli.py 部分、3.5〜3.7、および 4.2 のCLIオプション・終了コード・エッジケースに従い、CLI層を実装してください。

やること:

- __main__.py から cli.main() を呼ぶ構成
- argparse による引数・オプション定義
- 制御フロー: 引数解析 → パース → offset解決（--offset 指定時は上書き）→ validate_toc → flatten_toc → build_output_plan → validate_output_plan → split_pdf
- --dry-run: ファイル一覧を表示して終了
- --validate-only: バリデーション結果を表示して終了（strict=False で実行）
- 終了コード（0, 1, 2）の制御
- ログ出力（SPEC.md セクション3.7 の形式）
- src/tests/test_splitter.py に CLIテストを追加
  - SPEC.md セクション4.2 のCLIオプション・終了コード・エッジケースの全観点
  - subprocess または monkeypatch で CLI 実行をテスト

完了条件:

- pytest が全件パスすること（タスク2, 3のテストも含む）
- 実際のPDFファイルに対して `python -m pdf_toc_splitter sample.pdf toc.md --dry-run` が正しいファイル一覧を出力すること

---

## タスク5: プロンプトテンプレート + サンプル + README

SPEC.md のセクション2 および examples/ に従い、残りの成果物を作成してください。

やること:

- prompts/toc_extraction_prompt.md の作成
  - セクション2.3 のプロンプト要件すべてを含む
  - セクション2.4 のあいまいケース対照表を含む
  - セクション2.5 の暫定記法の説明を含む
  - offset算出手順を含む
  - 完全な出力例（offset付き）を含む
- examples/example_toc.md の作成
  - SPEC.md セクション1.1 のフォーマット例をベースに、offset ディレクティブ付きの実用的なサンプル
- README.md の作成
  - プロジェクト概要
  - インストール手順（pip install -e .）
  - 使い方（基本コマンド、主要オプション、使用フロー）
  - 目次Markdownのフォーマット仕様（簡潔にまとめてSPEC.mdへのリンクを添える）
  - ライセンス

完了条件:

- プロンプトテンプレートにあいまいケース・offset算出手順・出力例がすべて含まれていること
- README の手順通りにインストール・実行できること
- pytest が全件パスすること（全タスクの回帰確認）

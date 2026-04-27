"""CLIエントリーポイント。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pypdf import PdfReader

from pdf_toc_splitter.splitter import build_output_plan, split_pdf, validate_output_plan
from pdf_toc_splitter.toc_parser import TocEntry, flatten_toc, parse_toc, validate_toc


def main() -> None:
    """CLIのメイン関数。"""
    parser = argparse.ArgumentParser(
        prog='pdf-toc-splitter',
        description='目次Markdownに基づきPDFファイルを章・節単位で分割する。',
    )
    parser.add_argument('input_pdf', help='分割対象のPDFファイルパス')
    parser.add_argument('toc', help='目次Markdownファイルパス')
    parser.add_argument('-o', '--output-dir', default='./output', help='出力ディレクトリ (デフォルト: ./output)')
    parser.add_argument('-d', '--depth', type=int, default=1, choices=[1, 2, 3], help='分割階層深さ 1〜3 (デフォルト: 1)')
    parser.add_argument('--offset', type=int, default=None, help='ページオフセット (Markdown内のoffsetより優先)')
    parser.add_argument('--dry-run', action='store_true', help='分割を実行せずファイル一覧を表示する')
    parser.add_argument('--prefix-digits', type=int, default=2, help='連番の桁数 (デフォルト: 2)')
    parser.add_argument('--validate-only', action='store_true', help='バリデーションのみ実行する')

    args = parser.parse_args()

    # 入力ファイルの存在確認
    if not Path(args.input_pdf).exists():
        print(f'[ERROR] 入力PDFが見つかりません: {args.input_pdf}')
        sys.exit(1)
    if not Path(args.toc).exists():
        print(f'[ERROR] 目次ファイルが見つかりません: {args.toc}')
        sys.exit(1)

    # 目次Markdownのパース
    try:
        entries, toc_offset = parse_toc(args.toc)
    except Exception as e:
        print(f'[ERROR] 目次ファイルの読み込みに失敗しました: {e}')
        sys.exit(1)

    # PDFの読み込み（総ページ数取得）
    try:
        reader = PdfReader(args.input_pdf)
        total_pages = len(reader.pages)
    except Exception as e:
        print(f'[ERROR] PDFの読み込みに失敗しました: {e}')
        sys.exit(1)

    # offset解決: CLI --offset 指定時はMarkdownのディレクティブより優先
    effective_offset: int | None = args.offset if args.offset is not None else toc_offset

    # バリデーション（--validate-only 時は strict=False で実行）
    strict = not args.validate_only
    errors, warnings = validate_toc(entries, total_pages, effective_offset, strict=strict)

    for w in warnings:
        print(f'[WARN] {w}')

    if errors:
        for err in errors:
            print(f'[ERROR] {err}')
        sys.exit(2)

    if args.validate_only:
        print('[INFO] バリデーション完了。エラーなし。')
        sys.exit(0)

    # 実分割用 offset（None の場合は 0 として扱う）
    offset: int = effective_offset if effective_offset is not None else 0

    # エントリのフラット化と出力計画の生成
    flat_entries = flatten_toc(entries, args.depth)
    plan = build_output_plan(flat_entries, offset, args.prefix_digits)

    # 出力ファイル名の重複検証
    plan_errors = validate_output_plan(plan)
    if plan_errors:
        for err in plan_errors:
            print(f'[ERROR] {err}')
        sys.exit(2)

    # ログ出力
    print(f'[INFO] Loaded TOC: {len(flat_entries)} entries (depth={args.depth}), offset={offset}')
    print(f'[INFO] Input PDF: {args.input_pdf} ({total_pages} pages)')
    print(f'[INFO] Output directory: {args.output_dir}')

    # --dry-run: ファイル一覧を表示して終了
    if args.dry_run:
        for _entry, filename in plan:
            print(f'  {filename}')
        sys.exit(0)

    # PDF分割
    total = len(plan)

    def _on_progress(current: int, total_count: int, entry: TocEntry, filename: str) -> None:
        page_count = entry.end_page - entry.start_page + 1
        print(f'[INFO]   {current}/{total_count}: {filename} ({page_count} pages)')

    print('[INFO] Splitting...')
    split_pdf(args.input_pdf, plan, args.output_dir, offset, on_progress=_on_progress)

    print(f'[INFO] Done. {total} files created in {args.output_dir}')
    sys.exit(0)

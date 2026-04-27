"""PDF分割ロジック。"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdf_toc_splitter.toc_parser import TocEntry

_OS_DISALLOWED_RE = re.compile(r'[/\\:*?"<>|]')
_MULTI_UNDERSCORE_RE = re.compile(r'_+')


def _sanitize_title(title: str) -> str:
    result = title.replace(' ', '_').replace('　', '_')
    result = _OS_DISALLOWED_RE.sub('_', result)
    result = _MULTI_UNDERSCORE_RE.sub('_', result)
    return result.strip('_')


def generate_filename(entry: TocEntry, index_label: str, offset: int, prefix_digits: int) -> str:
    """エントリからサニタイズ済みファイル名を生成する。

    Args:
        entry: 目次エントリ
        index_label: 階層連番ラベル（例: "02-01"）
        offset: ページオフセット
        prefix_digits: 連番の桁数（呼び出し元で index_label 生成時に適用済み）

    Returns:
        ファイル名（例: "02-01_2.1_定義_p20-29.pdf"）
    """
    phys_start = entry.start_page + offset
    phys_end = entry.end_page + offset
    sanitized = _sanitize_title(entry.title)
    return f'{index_label}_{sanitized}_p{phys_start}-{phys_end}.pdf'


def build_output_plan(entries: list[TocEntry], offset: int, prefix_digits: int) -> list[tuple[TocEntry, str]]:
    """フラット化済みエントリ一覧からファイル名を生成し、(エントリ, ファイル名) のリストを返す。

    階層連番は深さ優先・出現順で付与する。各階層の連番はそれぞれ独立して1から採番し、
    全階層共通の prefix_digits で0埋めする。子エントリ数が 10^prefix_digits を超える場合は
    桁数を自動拡張し、警告を出力する。

    Args:
        entries: flatten_toc が返したフラットなエントリリスト
        offset: ページオフセット
        prefix_digits: 連番の桁数（全階層共通）

    Returns:
        (エントリ, ファイル名) のタプルのリスト
    """
    counters: dict[int, int] = {}
    overflow_warned: set[int] = set()
    threshold = 10**prefix_digits
    plan: list[tuple[TocEntry, str]] = []

    for entry in entries:
        level = entry.level
        counters[level] = counters.get(level, 0) + 1

        for lv in range(level + 1, 4):
            counters.pop(lv, None)

        count = counters[level]
        if count >= threshold and level not in overflow_warned:
            overflow_warned.add(level)
            print(f'[WARN] level {level} の連番が {prefix_digits} 桁を超えました (count={count})')

        parts = [format(counters.get(lv, 1), f'0{prefix_digits}d') for lv in range(1, level + 1)]
        index_label = '-'.join(parts)
        filename = generate_filename(entry, index_label, offset, prefix_digits)
        plan.append((entry, filename))

    return plan


def validate_output_plan(plan: list[tuple[TocEntry, str]]) -> list[str]:
    """出力計画のファイル名重複を検証し、エラーメッセージのリストを返す。

    Args:
        plan: build_output_plan が返した (エントリ, ファイル名) のリスト

    Returns:
        エラーメッセージのリスト。重複がない場合は空リスト
    """
    errors: list[str] = []
    seen: dict[str, int] = {}

    for entry, filename in plan:
        if filename in seen:
            errors.append(f'行 {seen[filename]} と行 {entry.line_no}: ファイル名が重複しています ({filename!r})')
        else:
            seen[filename] = entry.line_no

    return errors


def split_pdf(input_path: str, plan: list[tuple[TocEntry, str]], output_dir: str, offset: int) -> list[str]:
    """出力計画に基づきPDFを分割し、出力ファイルパスのリストを返す。

    出力ディレクトリが存在しない場合は自動作成する。既存ファイルは上書きする。

    Args:
        input_path: 入力PDFファイルパス
        plan: build_output_plan が返した (エントリ, ファイル名) のリスト
        output_dir: 出力ディレクトリ
        offset: ページオフセット

    Returns:
        出力ファイルパスのリスト
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(input_path)
    output_files: list[str] = []

    for entry, filename in plan:
        writer = PdfWriter()
        phys_start = entry.start_page + offset
        phys_end = entry.end_page + offset

        for page_idx in range(phys_start - 1, phys_end):
            writer.add_page(reader.pages[page_idx])

        file_path = out_dir / filename
        with file_path.open('wb') as f:
            writer.write(f)

        output_files.append(str(file_path))

    return output_files

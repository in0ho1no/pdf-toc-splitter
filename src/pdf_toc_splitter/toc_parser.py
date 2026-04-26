"""目次Markdownパーサー。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TocEntry:
    """目次の1エントリを表すデータクラス。

    Attributes:
        title: セクションのタイトル
        start_page: 印刷上の開始ページ番号。0 は暫定値（判読不能）を意味する
        end_page: 印刷上の終了ページ番号。0 は暫定値（判読不能）を意味する
        level: 階層レベル（1〜3）
        children: 子エントリのリスト
        line_no: 元ファイルの行番号（1始まり）
    """

    title: str
    start_page: int
    end_page: int
    level: int
    children: list[TocEntry] = field(default_factory=list)
    line_no: int = 0


_OFFSET_RE = re.compile(r'<!--\s*offset:\s*(\S+)\s*-->')
_LIST_ITEM_RE = re.compile(r'^( *)- (.+)$')
_PAGE_RANGE_RE = re.compile(r'^(.+):\s*(\d+)-(\d+)\s*$')


def parse_toc(filepath: str) -> tuple[list[TocEntry], int | None]:
    """目次Markdownを解析し、ツリー構造のエントリリストとoffset値のタプルを返す。

    Args:
        filepath: 目次Markdownファイルのパス

    Returns:
        (エントリリスト, offset値) のタプル。
        offset値は整数ディレクティブがあれば int、
        ``<!-- offset: TODO -->`` の場合は None、ディレクティブ自体がない場合は 0。
    """
    text = Path(filepath).read_text(encoding='utf-8')
    lines = text.splitlines()

    offset: int | None = 0
    root_entries: list[TocEntry] = []
    level_stack: dict[int, TocEntry] = {}

    for line_no, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith('#'):
            continue

        # offset ディレクティブをその他のHTMLコメントより先に確認する
        offset_match = _OFFSET_RE.search(stripped)
        if offset_match:
            raw = offset_match.group(1)
            offset = None if raw == 'TODO' else int(raw)
            continue

        if stripped.startswith('<!--'):
            continue

        list_match = _LIST_ITEM_RE.match(line)
        if not list_match:
            continue

        indent = len(list_match.group(1))
        rest = list_match.group(2)
        level = indent // 2 + 1

        page_match = _PAGE_RANGE_RE.match(rest)
        if page_match:
            title = page_match.group(1).strip()
            start_page = int(page_match.group(2))
            end_page = int(page_match.group(3))
        else:
            # フォーマット不正: -1 を番兵値として格納し、validate_toc で検出する
            title = rest.strip()
            start_page = -1
            end_page = -1

        entry = TocEntry(
            title=title,
            start_page=start_page,
            end_page=end_page,
            level=level,
            line_no=line_no,
        )

        if level == 1:
            root_entries.append(entry)
        elif level - 1 in level_stack:
            level_stack[level - 1].children.append(entry)
        else:
            # インデント飛び級: 親がないためルートへ追加し、validate_toc で検出する
            root_entries.append(entry)

        level_stack[level] = entry
        for lv in range(level + 1, 4):
            level_stack.pop(lv, None)

    return root_entries, offset


def flatten_toc(entries: list[TocEntry], depth: int) -> list[TocEntry]:
    """指定階層までフラット化する（深さ優先・出現順）。

    Args:
        entries: ルートエントリのリスト
        depth: フラット化する最大階層（1=最上位のみ）

    Returns:
        フラット化されたエントリのリスト
    """
    result: list[TocEntry] = []

    def _traverse(entry: TocEntry) -> None:
        result.append(entry)
        if entry.level < depth:
            for child in entry.children:
                _traverse(child)

    for entry in entries:
        _traverse(entry)

    return result

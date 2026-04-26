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


def validate_toc(
    entries: list[TocEntry],
    total_pages: int,
    offset: int | None,
    strict: bool = True,
) -> tuple[list[str], list[str]]:
    """目次エントリのバリデーションを行い、エラーと警告のリストを返す。

    Args:
        entries: parse_toc が返したルートエントリのリスト
        total_pages: 対象PDFの総ページ数
        offset: ページオフセット（None は ``<!-- offset: TODO -->`` の暫定値）
        strict: True のとき 0-0 エントリと offset=None をエラーとし、
            False のとき警告とする

    Returns:
        (errors, warnings) のタプル。errors はエラーメッセージのリスト、
        warnings は警告メッセージのリスト。
    """
    errors: list[str] = []
    warnings: list[str] = []

    # offset=None (TODO) の暫定値残留チェック
    if offset is None:
        msg = 'offset が未設定です (<!-- offset: TODO -->)'
        (errors if strict else warnings).append(msg)

    eff_offset: int = offset if offset is not None else 0

    def _is_provisional(entry: TocEntry) -> bool:
        return entry.start_page == 0 and entry.end_page == 0

    def _check_siblings(siblings: list[TocEntry]) -> None:
        checkable = [e for e in siblings if not _is_provisional(e) and e.start_page != -1]

        # ページ範囲非重複チェック
        for i, e1 in enumerate(checkable):
            for e2 in checkable[i + 1 :]:
                if e1.start_page <= e2.end_page and e2.start_page <= e1.end_page:
                    errors.append(
                        f'行 {e1.line_no} と行 {e2.line_no}: 同一階層内でページ範囲が重複しています'
                        f' ({e1.start_page}-{e1.end_page} と {e2.start_page}-{e2.end_page})'
                    )

        # ページ範囲ギャップ警告（開始ページ順にソートして確認）
        sorted_s = sorted(checkable, key=lambda e: e.start_page)
        for i in range(len(sorted_s) - 1):
            e1, e2 = sorted_s[i], sorted_s[i + 1]
            if e2.start_page > e1.end_page + 1:
                warnings.append(
                    f'行 {e1.line_no} と行 {e2.line_no}: ページ {e1.end_page + 1}〜{e2.start_page - 1} がカバーされていません'
                )

    def _validate_entry(entry: TocEntry, parent: TocEntry | None) -> None:
        # フォーマット合致（番兵値 -1 はフォーマット不正）
        if entry.start_page == -1:
            errors.append(f'行 {entry.line_no}: フォーマット不正です ({entry.title!r})')
            return

        # タイトル非空
        if not entry.title:
            errors.append(f'行 {entry.line_no}: タイトルが空文字です')

        # 深さ上限
        if entry.level > 3:
            errors.append(f'行 {entry.line_no}: ネストが3階層を超えています (level={entry.level})')

        # インデント連続性
        expected_level = 1 if parent is None else parent.level + 1
        if entry.level != expected_level:
            errors.append(
                f'行 {entry.line_no}: インデントの飛び級があります'
                f' (期待 level={expected_level}, 実際 level={entry.level})'
            )

        provisional = _is_provisional(entry)
        if provisional:
            # 暫定値残留 (0-0)
            msg = f'行 {entry.line_no}: ページ番号が暫定値 (0-0) のままです'
            (errors if strict else warnings).append(msg)
        else:
            # ページ番号正値
            if entry.start_page < 1:
                errors.append(f'行 {entry.line_no}: 開始ページが 1 未満です ({entry.start_page})')
            if entry.end_page < 1:
                errors.append(f'行 {entry.line_no}: 終了ページが 1 未満です ({entry.end_page})')

            # ページ範囲整合
            if entry.start_page > entry.end_page:
                errors.append(
                    f'行 {entry.line_no}: 開始ページ ({entry.start_page}) が終了ページ ({entry.end_page}) より大きいです'
                )

            # 総ページ数以内
            phys_end = entry.end_page + eff_offset
            if phys_end > total_pages:
                errors.append(
                    f'行 {entry.line_no}: offset 適用後の終了ページ ({phys_end}) が'
                    f' 総ページ数 ({total_pages}) を超えています'
                )

            # 子範囲が親範囲内（親が 0-0 の場合はスキップ）
            if (
                parent is not None
                and not _is_provisional(parent)
                and (entry.start_page < parent.start_page or entry.end_page > parent.end_page)
            ):
                errors.append(
                    f'行 {entry.line_no}: 子エントリのページ範囲 ({entry.start_page}-{entry.end_page}) が'
                    f' 親の範囲 ({parent.start_page}-{parent.end_page}) を超えています'
                )

        # 子エントリを再帰チェック
        if entry.children:
            for child in entry.children:
                _validate_entry(child, entry)
            _check_siblings(entry.children)

    for entry in entries:
        _validate_entry(entry, None)
    _check_siblings(entries)

    return errors, warnings


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

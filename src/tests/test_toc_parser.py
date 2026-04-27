"""toc_parser モジュールのテスト。"""

from pathlib import Path

import pytest

from pdf_toc_splitter.toc_parser import TocEntry, flatten_toc, parse_toc, validate_toc

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def write_toc(tmp_path: Path, content: str) -> str:
    """テスト用 toc.md を tmp_path に書き込みパスを返す。"""
    p = tmp_path / 'toc.md'
    p.write_text(content, encoding='utf-8')
    return str(p)


# ---------------------------------------------------------------------------
# 正常系: parse_toc
# ---------------------------------------------------------------------------


class TestParseTocNormal:
    def test_single_level(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '- Ch1: 1-10\n- Ch2: 11-20\n- Ch3: 21-30\n',
        )
        entries, offset = parse_toc(path)
        assert offset == 0
        assert len(entries) == 3
        assert entries[0].title == 'Ch1'
        assert entries[0].start_page == 1
        assert entries[0].end_page == 10
        assert entries[0].level == 1
        assert entries[1].title == 'Ch2'
        assert entries[2].title == 'Ch3'

    def test_multiple_levels_depth2(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '- Ch1: 1-20\n  - S1.1: 1-10\n  - S1.2: 11-20\n- Ch2: 21-40\n',
        )
        entries, _ = parse_toc(path)
        assert len(entries) == 2
        assert len(entries[0].children) == 2
        assert entries[0].children[0].title == 'S1.1'
        assert entries[0].children[0].level == 2
        assert entries[0].children[1].title == 'S1.2'
        assert len(entries[1].children) == 0

    def test_multiple_levels_depth3(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '- Ch1: 1-30\n  - S1.1: 1-15\n    - S1.1.1: 1-7\n    - S1.1.2: 8-15\n  - S1.2: 16-30\n',
        )
        entries, _ = parse_toc(path)
        assert len(entries) == 1
        assert len(entries[0].children) == 2
        s11 = entries[0].children[0]
        assert len(s11.children) == 2
        assert s11.children[0].title == 'S1.1.1'
        assert s11.children[0].level == 3
        assert s11.children[1].title == 'S1.1.2'

    def test_skip_blank_lines_and_heading(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '# 書籍タイトル\n\n<!-- offset: 2 -->\n\n- Ch1: 1-10\n\n- Ch2: 11-20\n',
        )
        entries, offset = parse_toc(path)
        assert offset == 2
        assert len(entries) == 2

    def test_skip_html_comment(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '<!-- NOTE: これはコメント -->\n- Ch1: 1-10\n',
        )
        entries, offset = parse_toc(path)
        assert offset == 0
        assert len(entries) == 1

    def test_offset_integer(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '<!-- offset: 4 -->\n- Ch1: 1-10\n')
        _, offset = parse_toc(path)
        assert offset == 4

    def test_offset_missing_returns_zero(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '- Ch1: 1-10\n')
        _, offset = parse_toc(path)
        assert offset == 0

    def test_offset_zero(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '<!-- offset: 0 -->\n- Ch1: 1-10\n')
        _, offset = parse_toc(path)
        assert offset == 0

    def test_offset_todo_returns_none(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '<!-- offset: TODO -->\n- Ch1: 1-10\n')
        _, offset = parse_toc(path)
        assert offset is None

    def test_single_page_entry(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '- 序文: 5-5\n')
        entries, _ = parse_toc(path)
        assert entries[0].start_page == 5
        assert entries[0].end_page == 5

    def test_provisional_zero_zero(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '- 不明章: 0-0\n- Ch2: 5-10\n')
        entries, _ = parse_toc(path)
        assert entries[0].start_page == 0
        assert entries[0].end_page == 0
        assert entries[1].start_page == 5

    def test_line_numbers_recorded(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '# title\n\n- Ch1: 1-10\n  - S1.1: 1-5\n',
        )
        entries, _ = parse_toc(path)
        assert entries[0].line_no == 3
        assert entries[0].children[0].line_no == 4


# ---------------------------------------------------------------------------
# 正常系: flatten_toc
# ---------------------------------------------------------------------------


class TestFlattenToc:
    @pytest.fixture
    def tree(self) -> list[TocEntry]:
        s11 = TocEntry('S1.1', 1, 7, 3)
        s12 = TocEntry('S1.2', 8, 15, 3)
        sec1 = TocEntry('S1', 1, 15, 2, children=[s11, s12])
        sec2 = TocEntry('S2', 16, 30, 2)
        ch1 = TocEntry('Ch1', 1, 30, 1, children=[sec1, sec2])
        ch2 = TocEntry('Ch2', 31, 50, 1)
        return [ch1, ch2]

    def test_depth1(self, tree: list[TocEntry]) -> None:
        flat = flatten_toc(tree, depth=1)
        assert [e.title for e in flat] == ['Ch1', 'Ch2']

    def test_depth2(self, tree: list[TocEntry]) -> None:
        flat = flatten_toc(tree, depth=2)
        assert [e.title for e in flat] == ['Ch1', 'S1', 'S2', 'Ch2']

    def test_depth3(self, tree: list[TocEntry]) -> None:
        flat = flatten_toc(tree, depth=3)
        assert [e.title for e in flat] == ['Ch1', 'S1', 'S1.1', 'S1.2', 'S2', 'Ch2']

    def test_empty(self) -> None:
        assert flatten_toc([], depth=1) == []


# ---------------------------------------------------------------------------
# 異常系: validate_toc — エラー項目
# ---------------------------------------------------------------------------


class TestValidateTocErrors:
    def test_format_error_no_colon(self, tmp_path: Path) -> None:
        path = write_toc(tmp_path, '- タイトルのみ\n')
        entries, offset = parse_toc(path)
        errors, _ = validate_toc(entries, total_pages=100, offset=offset)
        assert any('フォーマット不正' in e for e in errors)

    def test_empty_title(self) -> None:
        entry = TocEntry(title='', start_page=1, end_page=10, level=1, line_no=1)
        errors, _ = validate_toc([entry], total_pages=100, offset=0)
        assert any('空文字' in e for e in errors)

    def test_start_page_zero_not_provisional(self) -> None:
        # 0-10 は 0-0 ではないので暫定値扱いにならず、ページ番号正値エラー
        entry = TocEntry(title='Ch', start_page=0, end_page=10, level=1, line_no=1)
        errors, _ = validate_toc([entry], total_pages=100, offset=0)
        assert any('1 未満' in e for e in errors)

    def test_end_page_zero_not_provisional(self) -> None:
        entry = TocEntry(title='Ch', start_page=5, end_page=0, level=1, line_no=1)
        errors, _ = validate_toc([entry], total_pages=100, offset=0)
        assert any('1 未満' in e for e in errors)

    def test_start_greater_than_end(self) -> None:
        entry = TocEntry(title='Ch', start_page=20, end_page=10, level=1, line_no=1)
        errors, _ = validate_toc([entry], total_pages=100, offset=0)
        assert any('終了ページ' in e and '大きい' in e for e in errors)

    def test_exceed_total_pages(self) -> None:
        entry = TocEntry(title='Ch', start_page=1, end_page=60, level=1, line_no=1)
        errors, _ = validate_toc([entry], total_pages=50, offset=0)
        assert any('総ページ数' in e for e in errors)

    def test_exceed_total_pages_with_offset(self) -> None:
        entry = TocEntry(title='Ch', start_page=1, end_page=47, level=1, line_no=1)
        # offset=4 → physical_end=51 > 50
        errors, _ = validate_toc([entry], total_pages=50, offset=4)
        assert any('総ページ数' in e for e in errors)

    def test_child_exceeds_parent(self) -> None:
        child = TocEntry(title='S1', start_page=5, end_page=15, level=2, line_no=2)
        parent = TocEntry(title='Ch1', start_page=1, end_page=10, level=1, children=[child], line_no=1)
        errors, _ = validate_toc([parent], total_pages=100, offset=0)
        assert any('親の範囲' in e for e in errors)

    def test_indent_jump_level1_to_level3(self, tmp_path: Path) -> None:
        # インデント飛び級: レベル1の次にレベル3
        path = write_toc(tmp_path, '- Ch1: 1-20\n    - S1.1.1: 2-5\n')
        entries, offset = parse_toc(path)
        errors, _ = validate_toc(entries, total_pages=100, offset=offset)
        assert any('飛び級' in e for e in errors)

    def test_max_depth_exceeded(self) -> None:
        # level 4 エントリ
        deep = TocEntry(title='Deep', start_page=1, end_page=5, level=4, line_no=4)
        sub = TocEntry(title='Sub', start_page=1, end_page=10, level=3, children=[deep], line_no=3)
        sec = TocEntry(title='Sec', start_page=1, end_page=20, level=2, children=[sub], line_no=2)
        ch = TocEntry(title='Ch', start_page=1, end_page=30, level=1, children=[sec], line_no=1)
        errors, _ = validate_toc([ch], total_pages=100, offset=0)
        assert any('3階層' in e for e in errors)

    def test_page_range_overlap(self) -> None:
        e1 = TocEntry(title='Ch1', start_page=1, end_page=10, level=1, line_no=1)
        e2 = TocEntry(title='Ch2', start_page=8, end_page=20, level=1, line_no=2)
        errors, warnings = validate_toc([e1, e2], total_pages=100, offset=0)
        assert not any('重複' in e for e in errors)
        assert any('重複' in w for w in warnings)

    def test_page_range_overlap_at_boundary(self) -> None:
        # 終端と先頭が一致するケース [1,10] と [10,20] は重複
        e1 = TocEntry(title='Ch1', start_page=1, end_page=10, level=1, line_no=1)
        e2 = TocEntry(title='Ch2', start_page=10, end_page=20, level=1, line_no=2)
        errors, warnings = validate_toc([e1, e2], total_pages=100, offset=0)
        assert not any('重複' in e for e in errors)
        assert any('重複' in w for w in warnings)

    def test_no_errors_valid_toc(self, tmp_path: Path) -> None:
        path = write_toc(
            tmp_path,
            '<!-- offset: 4 -->\n- Ch1: 1-15\n- Ch2: 16-42\n  - S2.1: 16-25\n  - S2.2: 26-42\n',
        )
        entries, offset = parse_toc(path)
        errors, _ = validate_toc(entries, total_pages=100, offset=offset)
        assert errors == []


# ---------------------------------------------------------------------------
# 暫定値の扱い
# ---------------------------------------------------------------------------


class TestValidateTocProvisional:
    def test_strict_zero_zero_is_error(self) -> None:
        entry = TocEntry(title='未設定', start_page=0, end_page=0, level=1, line_no=1)
        errors, warnings = validate_toc([entry], total_pages=100, offset=0, strict=True)
        assert any('暫定値' in e for e in errors)
        assert not any('暫定値' in w for w in warnings)

    def test_strict_todo_offset_is_error(self) -> None:
        entry = TocEntry(title='Ch', start_page=1, end_page=10, level=1, line_no=1)
        errors, warnings = validate_toc([entry], total_pages=100, offset=None, strict=True)
        assert any('offset' in e for e in errors)
        assert not any('offset' in w for w in warnings)

    def test_nonstrict_zero_zero_is_warning(self) -> None:
        entry = TocEntry(title='未設定', start_page=0, end_page=0, level=1, line_no=1)
        errors, warnings = validate_toc([entry], total_pages=100, offset=0, strict=False)
        assert not any('暫定値' in e for e in errors)
        assert any('暫定値' in w for w in warnings)

    def test_nonstrict_todo_offset_is_warning(self) -> None:
        entry = TocEntry(title='Ch', start_page=1, end_page=10, level=1, line_no=1)
        errors, warnings = validate_toc([entry], total_pages=100, offset=None, strict=False)
        assert not any('offset' in e for e in errors)
        assert any('offset' in w for w in warnings)

    def test_zero_zero_skips_range_check(self) -> None:
        # 0-0 エントリは ページ範囲整合・総ページ数・重複チェックをスキップ
        e1 = TocEntry(title='不明', start_page=0, end_page=0, level=1, line_no=1)
        e2 = TocEntry(title='Ch2', start_page=1, end_page=10, level=1, line_no=2)
        errors, _ = validate_toc([e1, e2], total_pages=5, offset=0, strict=False)
        # 0-0 に起因するエラーは出ない（strict=False なので暫定値は警告のみ）
        non_provisional_errors = [e for e in errors if '暫定値' not in e and 'offset' not in e]
        assert non_provisional_errors == []

    def test_zero_zero_skips_child_range_check(self) -> None:
        # 親が 0-0 → 子範囲チェックをスキップ
        child = TocEntry(title='S1', start_page=1, end_page=100, level=2, line_no=2)
        parent = TocEntry(title='Ch', start_page=0, end_page=0, level=1, children=[child], line_no=1)
        errors, _ = validate_toc([parent], total_pages=200, offset=0, strict=False)
        assert not any('親の範囲' in e for e in errors)

    def test_zero_zero_skips_overlap_check(self) -> None:
        # 0-0 同士は重複チェック対象外
        e1 = TocEntry(title='不明1', start_page=0, end_page=0, level=1, line_no=1)
        e2 = TocEntry(title='不明2', start_page=0, end_page=0, level=1, line_no=2)
        errors, warnings = validate_toc([e1, e2], total_pages=100, offset=0, strict=False)
        assert not any('重複' in e for e in errors)
        assert not any('重複' in w for w in warnings)


# ---------------------------------------------------------------------------
# 警告系
# ---------------------------------------------------------------------------


class TestValidateTocWarnings:
    def test_page_gap_warning(self) -> None:
        e1 = TocEntry(title='Ch1', start_page=1, end_page=10, level=1, line_no=1)
        e2 = TocEntry(title='Ch2', start_page=15, end_page=30, level=1, line_no=2)
        _, warnings = validate_toc([e1, e2], total_pages=100, offset=0)
        assert any('カバーされていません' in w for w in warnings)

    def test_no_gap_warning_when_consecutive(self) -> None:
        e1 = TocEntry(title='Ch1', start_page=1, end_page=10, level=1, line_no=1)
        e2 = TocEntry(title='Ch2', start_page=11, end_page=20, level=1, line_no=2)
        _, warnings = validate_toc([e1, e2], total_pages=100, offset=0)
        assert not any('カバーされていません' in w for w in warnings)

    def test_gap_warning_children(self) -> None:
        c1 = TocEntry(title='S1', start_page=1, end_page=5, level=2, line_no=2)
        c2 = TocEntry(title='S2', start_page=10, end_page=20, level=2, line_no=3)
        parent = TocEntry(title='Ch', start_page=1, end_page=20, level=1, children=[c1, c2], line_no=1)
        _, warnings = validate_toc([parent], total_pages=100, offset=0)
        assert any('カバーされていません' in w for w in warnings)

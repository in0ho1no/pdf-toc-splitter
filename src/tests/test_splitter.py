"""splitter モジュールのテスト。"""

from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from pdf_toc_splitter.splitter import build_output_plan, generate_filename, split_pdf, validate_output_plan
from pdf_toc_splitter.toc_parser import TocEntry


def _make_entry(title: str, start_page: int, end_page: int, level: int = 1, line_no: int = 1) -> TocEntry:
    return TocEntry(title=title, start_page=start_page, end_page=end_page, level=level, line_no=line_no)


def _create_pdf(path: Path, num_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=612, height=792)
    with path.open('wb') as f:
        writer.write(f)


class TestGenerateFilename:
    def test_basic(self) -> None:
        entry = _make_entry('第1章 はじめに', 1, 15)
        result = generate_filename(entry, '01', offset=4, prefix_digits=2)
        assert result == '01_第1章_はじめに_p5-19.pdf'

    def test_sanitize_os_disallowed_chars(self) -> None:
        entry = _make_entry('A/B:C*D?E"F<G>H|I', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result == '01_A_B_C_D_E_F_G_H_I_p1-5.pdf'

    def test_sanitize_halfwidth_space(self) -> None:
        entry = _make_entry('Hello World', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result == '01_Hello_World_p1-5.pdf'

    def test_sanitize_fullwidth_space(self) -> None:
        entry = _make_entry('Hello　World', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result == '01_Hello_World_p1-5.pdf'

    def test_sanitize_consecutive_spaces(self) -> None:
        entry = _make_entry('A  B', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result == '01_A_B_p1-5.pdf'

    def test_trim_leading_trailing_underscore(self) -> None:
        entry = _make_entry(' Leading', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result == '01_Leading_p1-5.pdf'

    def test_prefix_digits_2(self) -> None:
        entry = _make_entry('Ch1', 1, 5)
        result = generate_filename(entry, '01', offset=0, prefix_digits=2)
        assert result.startswith('01_')

    def test_prefix_digits_3(self) -> None:
        entry = _make_entry('Ch1', 1, 5)
        result = generate_filename(entry, '001', offset=0, prefix_digits=3)
        assert result.startswith('001_')


class TestBuildOutputPlan:
    def test_depth1_flat(self) -> None:
        entries = [
            _make_entry('Ch1', 1, 15, level=1, line_no=1),
            _make_entry('Ch2', 16, 30, level=1, line_no=2),
            _make_entry('Ch3', 31, 50, level=1, line_no=3),
        ]
        plan = build_output_plan(entries, offset=0, prefix_digits=2)
        filenames = [fn for _, fn in plan]
        assert filenames[0] == '01_Ch1_p1-15.pdf'
        assert filenames[1] == '02_Ch2_p16-30.pdf'
        assert filenames[2] == '03_Ch3_p31-50.pdf'

    def test_depth2_hierarchical(self) -> None:
        entries = [
            _make_entry('Ch1', 1, 15, level=1, line_no=1),
            _make_entry('1.1', 1, 8, level=2, line_no=2),
            _make_entry('1.2', 9, 15, level=2, line_no=3),
            _make_entry('Ch2', 16, 30, level=1, line_no=4),
            _make_entry('2.1', 16, 22, level=2, line_no=5),
        ]
        plan = build_output_plan(entries, offset=0, prefix_digits=2)
        filenames = [fn for _, fn in plan]
        assert filenames[0] == '01_Ch1_p1-15.pdf'
        assert filenames[1] == '01-01_1.1_p1-8.pdf'
        assert filenames[2] == '01-02_1.2_p9-15.pdf'
        assert filenames[3] == '02_Ch2_p16-30.pdf'
        assert filenames[4] == '02-01_2.1_p16-22.pdf'

    def test_depth3_hierarchical(self) -> None:
        entries = [
            _make_entry('Ch1', 1, 20, level=1, line_no=1),
            _make_entry('1.1', 1, 10, level=2, line_no=2),
            _make_entry('1.1.1', 1, 5, level=3, line_no=3),
            _make_entry('1.1.2', 6, 10, level=3, line_no=4),
            _make_entry('1.2', 11, 20, level=2, line_no=5),
        ]
        plan = build_output_plan(entries, offset=0, prefix_digits=2)
        filenames = [fn for _, fn in plan]
        assert filenames[2] == '01-01-01_1.1.1_p1-5.pdf'
        assert filenames[3] == '01-01-02_1.1.2_p6-10.pdf'
        assert filenames[4] == '01-02_1.2_p11-20.pdf'

    def test_offset_applied(self) -> None:
        entries = [_make_entry('Ch1', 1, 15, level=1)]
        plan = build_output_plan(entries, offset=4, prefix_digits=2)
        assert '_p5-19.pdf' in plan[0][1]

    def test_digit_overflow_auto_expand_and_warn(self, capsys: pytest.CaptureFixture[str]) -> None:
        entries = [
            _make_entry(f'Ch{i}', i, i, level=1, line_no=i)
            for i in range(1, 12)
        ]
        plan = build_output_plan(entries, offset=0, prefix_digits=1)
        assert plan[9][1].startswith('10_')
        captured = capsys.readouterr()
        assert '[WARN]' in captured.out


class TestValidateOutputPlan:
    def test_unique_filenames(self) -> None:
        plan = [
            (_make_entry('Ch1', 1, 5, line_no=1), '01_Ch1_p1-5.pdf'),
            (_make_entry('Ch2', 6, 10, line_no=2), '02_Ch2_p6-10.pdf'),
        ]
        errors = validate_output_plan(plan)
        assert errors == []

    def test_duplicate_filenames_detected(self) -> None:
        plan = [
            (_make_entry('Hello World', 1, 5, line_no=1), '01_Hello_World_p1-5.pdf'),
            (_make_entry('Hello_World', 1, 5, line_no=2), '01_Hello_World_p1-5.pdf'),
        ]
        errors = validate_output_plan(plan)
        assert len(errors) == 1
        assert '01_Hello_World_p1-5.pdf' in errors[0]


class TestSplitPdf:
    def test_depth1_file_count(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 10)
        plan = [
            (_make_entry('Ch1', 1, 4, line_no=1), '01_Ch1_p1-4.pdf'),
            (_make_entry('Ch2', 5, 7, line_no=2), '02_Ch2_p5-7.pdf'),
            (_make_entry('Ch3', 8, 10, line_no=3), '03_Ch3_p8-10.pdf'),
        ]
        output_files = split_pdf(str(pdf_path), plan, str(tmp_path / 'output'), offset=0)
        assert len(output_files) == 3

    def test_depth1_page_count(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 10)
        plan = [
            (_make_entry('Ch1', 1, 4, line_no=1), '01_Ch1_p1-4.pdf'),
            (_make_entry('Ch2', 5, 7, line_no=2), '02_Ch2_p5-7.pdf'),
            (_make_entry('Ch3', 8, 10, line_no=3), '03_Ch3_p8-10.pdf'),
        ]
        output_files = split_pdf(str(pdf_path), plan, str(tmp_path / 'output'), offset=0)
        page_counts = [len(PdfReader(f).pages) for f in output_files]
        assert page_counts == [4, 3, 3]

    def test_offset_applied(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 10)
        plan = [(_make_entry('Ch1', 1, 3, line_no=1), '01_Ch1_p5-7.pdf')]
        output_files = split_pdf(str(pdf_path), plan, str(tmp_path / 'output'), offset=4)
        assert len(PdfReader(output_files[0]).pages) == 3

    def test_output_dir_auto_created(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 5)
        out_dir = tmp_path / 'nested' / 'output'
        plan = [(_make_entry('Ch1', 1, 5, line_no=1), '01_Ch1_p1-5.pdf')]
        split_pdf(str(pdf_path), plan, str(out_dir), offset=0)
        assert out_dir.exists()

    def test_overwrite_existing_file(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 5)
        out_dir = tmp_path / 'output'
        out_dir.mkdir()
        existing = out_dir / '01_Ch1_p1-5.pdf'
        existing.write_bytes(b'old content')
        plan = [(_make_entry('Ch1', 1, 5, line_no=1), '01_Ch1_p1-5.pdf')]
        split_pdf(str(pdf_path), plan, str(out_dir), offset=0)
        assert len(PdfReader(str(existing)).pages) == 5

    def test_depth2_output_order(self, tmp_path: Path) -> None:
        pdf_path = tmp_path / 'input.pdf'
        _create_pdf(pdf_path, 6)
        plan = [
            (_make_entry('Ch1', 1, 3, level=1, line_no=1), '01_Ch1_p1-3.pdf'),
            (_make_entry('1.1', 1, 2, level=2, line_no=2), '01-01_1.1_p1-2.pdf'),
            (_make_entry('Ch2', 4, 6, level=1, line_no=3), '02_Ch2_p4-6.pdf'),
        ]
        output_files = split_pdf(str(pdf_path), plan, str(tmp_path / 'output'), offset=0)
        filenames = [Path(f).name for f in output_files]
        assert filenames == ['01_Ch1_p1-3.pdf', '01-01_1.1_p1-2.pdf', '02_Ch2_p4-6.pdf']

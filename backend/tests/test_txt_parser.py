"""Pure, synthetic TXT v1/v2 compatibility and error reporting."""

from apps.imports.txt_parser import parse_txt


def test_v1_metadata_chapter_and_mcq():
    source = """\ufeff#TITLE: Bộ đề tự biên soạn
#SUBTITLE: Mẫu
#TRUONG: Trường A, Trường B
#NGANH: Toán, Tin học
[C1] Số học
Hai cộng hai bằng mấy?
A. Ba
B. Bốn
C. Năm
D. Sáu
=>B
"""
    outcome = parse_txt(source)
    assert outcome.valid == 1 and outcome.skipped == 0
    assert not outcome.issues
    assert outcome.draft.metadata.title == "Bộ đề tự biên soạn"
    assert outcome.draft.metadata.schools == ["Trường A", "Trường B"]
    assert outcome.draft.chapters[0].code == "C1"
    question = outcome.draft.sections[0].questions[0]
    assert question.kind == "MCQ"
    assert question.choices[1].is_correct
    assert question.provenance.line == 6


def test_v2_multi_true_false_short_and_code_fence():
    source = """#TITLE: Mẫu v2
#SUBJECT: toan
#LEVEL: THPT
#GRADE: 12
#TYPE: ON_TAP
#YEAR: 2026
#DURATION: 30
[C1] Lập trình
Chọn hai đáp án:
A. Một
B. Hai
C. Ba
=>A,C
#EXPLAIN: Hai phương án đúng.
Mệnh đề này đúng?
=>T
Giá trị của 7/2 là bao nhiêu?
=>#3.5
Đoạn mã cho kết quả gì?
```
print('A. ví dụ')
```
A. Có
B. Không
=>A
"""
    outcome = parse_txt(source)
    assert outcome.valid == 4 and outcome.skipped == 0
    assert [q.kind for q in outcome.draft.sections[0].questions] == [
        "MCQ_MULTI",
        "TRUE_FALSE",
        "SHORT",
        "MCQ",
    ]
    assert outcome.draft.sections[0].questions[0].explanation == "Hai phương án đúng."
    assert outcome.draft.sections[0].questions[2].short_answer == "3.5"
    assert "print('A. ví dụ')" in outcome.draft.sections[0].questions[3].text


def test_malformed_questions_are_reported_with_line_numbers_without_silent_drop():
    source = """Câu lạc chương?
A. Một
B. Hai
=>A
[C1] Số học
Thiếu đáp án?
A. Một
B. Hai
Câu hợp lệ?
A. Một
B. Hai
=>B
Câu hợp lệ?
A. Một
B. Hai
=>B
#UNKNOWN: x
"""
    outcome = parse_txt(source)
    assert outcome.valid == 2 and outcome.skipped == 2
    assert [(item.line, item.code) for item in outcome.issues] == [
        (1, "T_NO_CHAPTER"),
        (6, "T_NO_ANSWER"),
        (13, "W_DUP_QUESTION"),
        (17, "T_UNKNOWN_LINE"),
    ]


def test_limits_and_bad_answers_are_explicit():
    too_large = parse_txt("x" * (2 * 1024 * 1024 + 1))
    assert too_large.issues[0].code == "T_TOO_LARGE"
    too_many_lines = parse_txt("\n" * 20_000)
    assert too_many_lines.issues[0].code == "T_TOO_MANY_LINES"
    invalid = parse_txt("[C1] Số học\nCâu hỏi?\nA. Một\nB. Hai\n=>C")
    assert invalid.valid == 0 and invalid.skipped == 1
    assert invalid.issues[0].code == "T_ANSWER_OUT_OF_RANGE"


def test_invalid_question_does_not_erase_valid_neighbors():
    source = (
        "[C1] Số học\nCâu lỗi?\nA. <script>x</script>\nB. Bốn\n=>B\n"
        "Câu hợp lệ?\nA. Ba\nB. Bốn\n=>B\n"
    )
    outcome = parse_txt(source)
    assert outcome.valid == 1 and outcome.skipped == 1
    assert [(issue.line, issue.code) for issue in outcome.issues] == [(2, "T_QUESTION_INVALID")]
    assert outcome.draft.sections[0].questions[0].text == "Câu hợp lệ?"

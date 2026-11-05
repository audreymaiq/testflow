"""Check legacy source; optionally export licensed questions as deterministic TXT."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from apps.imports.txt_parser import parse_txt


def main() -> int:
    if len(sys.argv) not in (2, 4) or (len(sys.argv) == 4 and sys.argv[2] != "--output"):
        print("Usage: python scripts/check_quiz_rush_parser.py PATH_TO_DATA_JS [--output PATH_TO_TXT]")
        return 2
    legacy = Path(sys.argv[1]).resolve(strict=True)
    script = (
        "const fs=require('fs');const vm=require('vm');"
        "const source=fs.readFileSync(process.argv[1],'utf8');"
        "const result=vm.runInNewContext(source+';JSON.stringify({raw:RAW,chapters:chapMeta})');"
        "process.stdout.write(result);"
    )
    result = subprocess.run(
        ["node", "-e", script, str(legacy)], capture_output=True, text=True,
        encoding="utf-8",
        check=True, timeout=20,
    )
    source = json.loads(result.stdout)
    raw = source["raw"]
    chapters = source["chapters"]
    lines = ["#TITLE: Thị Giác Máy Tính"]
    for code, chapter in chapters.items():
        lines.append(f"[{code}] {chapter['name']}")
        for question, choices, answer_index, question_code in raw:
            if question_code != code:
                continue
            lines.append(question)
            lines.extend(f"{label}. {choice}" for label, choice in zip("ABCDEF", choices, strict=False))
            lines.append(f"=>{'ABCDEF'[answer_index]}")
    outcome = parse_txt("\n".join(lines))
    parsed = [question for section in outcome.draft.sections for question in section.questions]
    expected = [item for code in chapters for item in raw if item[3] == code]
    correct = len(parsed) == len(expected) and all(
        question.text == source_question
        and [choice.text for choice in question.choices] == choices
        and next(index for index, choice in enumerate(question.choices) if choice.is_correct) == answer_index
        and question.chapter == code
        for question, (source_question, choices, answer_index, code) in zip(parsed, expected, strict=False)
    )
    valid = (
        correct and len(raw) == 300 and len(outcome.draft.chapters) == 4
        and outcome.skipped == 0 and len(outcome.issues) == 0
    )
    if valid and len(sys.argv) == 4:
        output = Path(sys.argv[3])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "source_questions": len(raw), "parsed_questions": len(parsed),
        "chapters": len(outcome.draft.chapters), "skipped": outcome.skipped,
        "issues": len(outcome.issues), "answers_and_text_match": correct,
    }))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())

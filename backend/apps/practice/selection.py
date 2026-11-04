"""Pure, reproducible question and option selection."""

import random

from .schemas import SessionConfig


def build_question_set(
    section_questions: dict[str, list[tuple[str, str | None, tuple[str, ...]]]],
    config: SessionConfig,
    wrong_ids: set[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]] | None]:
    """Map section to fixed question IDs and optional fixed choice-label orders."""
    rng = random.Random(config.seed)
    chapter_ids = set(config.chapter_ids)
    selected: dict[str, list[str]] = {}
    options: dict[str, list[str]] = {}
    for section_id, questions in section_questions.items():
        included = []
        for question_id, chapter_id, labels in questions:
            chosen = (
                question_id in wrong_ids
                if config.only_wrong_bank
                else (not chapter_ids or chapter_id in chapter_ids)
            )
            if config.include_wrong_bank and question_id in wrong_ids:
                chosen = True
            if not chosen:
                continue
            included.append(question_id)
            if config.shuffle_options and labels:
                shuffled = list(labels)
                rng.shuffle(shuffled)
                options[question_id] = shuffled
        if config.shuffle_questions:
            rng.shuffle(included)
        if included:
            selected[section_id] = included
    return selected, options if config.shuffle_options else None

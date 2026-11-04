"""Validated session configuration stored in Session.config."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_ids: list[str] = Field(default_factory=list)
    include_wrong_bank: bool = False
    only_wrong_bank: bool = False
    shuffle_questions: bool = False
    shuffle_options: bool = False
    seed: int = Field(ge=0)

    @model_validator(mode="after")
    def valid_mix(self):
        if self.only_wrong_bank and self.chapter_ids:
            raise ValueError("only_wrong_bank cannot be combined with chapter_ids")
        return self

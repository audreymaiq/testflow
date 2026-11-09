"""Bounded HTTP boundary to a separately deployed page extraction runtime."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError
from testflow_contracts.page import PageSchema

MAX_RESPONSE_BYTES = 10 * 1024 * 1024


class ExtractionError(Exception):
    def __init__(self, code: str, *, retryable: bool):
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True)
class PageExtraction:
    page: PageSchema
    raw_output: object
    provider_name: str
    model_name: str
    model_version: str
    artifact_digest: str
    latency_ms: int


def _read_response(response) -> dict:
    content = response.read(MAX_RESPONSE_BYTES + 1)
    if len(content) > MAX_RESPONSE_BYTES:
        raise ExtractionError("INFERENCE_RESPONSE_TOO_LARGE", retryable=False)
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError("INFERENCE_RESPONSE_INVALID", retryable=False) from exc
    if not isinstance(payload, dict):
        raise ExtractionError("INFERENCE_RESPONSE_INVALID", retryable=False)
    return payload


def extract_page(
    *,
    service_url: str,
    image_png: bytes,
    page_no: int,
    subject_hint: str = "",
    timeout_seconds: int = 60,
    token: str = "",
) -> PageExtraction:
    """Call one configured internal runtime; never accept a URL from an end user."""
    if not service_url.startswith(("http://", "https://")):
        raise ValueError("service_url must be an HTTP(S) URL")
    if not image_png or page_no < 1 or timeout_seconds < 1:
        raise ValueError("invalid extraction input")
    body = json.dumps(
        {
            "image_b64": base64.b64encode(image_png).decode("ascii"),
            "page_no": page_no,
            "subject_hint": subject_hint or None,
            "schema_version": 1,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(service_url.rstrip("/") + "/v1/extract-page", data=body, headers=headers)
    started = monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = _read_response(response)
    except HTTPError as exc:
        if exc.code in {408, 429, 500, 502, 503, 504}:
            raise ExtractionError("INFERENCE_UNAVAILABLE", retryable=True) from exc
        raise ExtractionError("INFERENCE_REJECTED", retryable=False) from exc
    except (TimeoutError, URLError) as exc:
        raise ExtractionError("INFERENCE_UNAVAILABLE", retryable=True) from exc
    try:
        page = PageSchema.model_validate(payload["page_json"])
        if page.page_no != page_no:
            raise ExtractionError("INFERENCE_PAGE_MISMATCH", retryable=False)
        model_name = payload["model_name"]
        if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 80:
            raise ValueError("model_name is required")
        provider_name = payload.get("provider_name", "internal")
        model_version = payload.get("model_version", "")
        artifact_digest = payload.get("artifact_digest", "")
        if (
            not isinstance(provider_name, str)
            or not provider_name.strip()
            or len(provider_name) > 80
            or not isinstance(model_version, str)
            or len(model_version) > 80
            or not isinstance(artifact_digest, str)
            or (artifact_digest and re.fullmatch(r"[0-9a-fA-F]{64}", artifact_digest) is None)
        ):
            raise ValueError("invalid model provenance")
        return PageExtraction(
            page=page,
            raw_output=payload.get("raw_output", {}),
            provider_name=provider_name,
            model_name=model_name,
            model_version=model_version,
            artifact_digest=artifact_digest,
            latency_ms=round((monotonic() - started) * 1000),
        )
    except (KeyError, ValueError, ValidationError) as exc:
        raise ExtractionError("INFERENCE_RESPONSE_INVALID", retryable=False) from exc

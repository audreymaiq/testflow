"""Synthetic inference wire-contract tests; no model quality claim."""

import json
from io import BytesIO
from urllib.error import HTTPError

import pytest

from apps.imports import inference_client


def response(page_no=2, **changes):
    payload = {
        "page_json": {
            "schema_version": 1,
            "page_no": page_no,
            "blocks": [
                {
                    "type": "question",
                    "number_label": "Câu 1",
                    "kind": "MCQ",
                    "text": "Hai cộng hai bằng mấy?",
                    "choices": [{"label": "A", "text": "Ba"}, {"label": "B", "text": "Bốn"}],
                }
            ],
        },
        "raw_output": {"text": "synthetic"},
        "provider_name": "local-runtime",
        "source": "VLM",
        "model_name": "synthetic-fixture",
        "model_version": "test-v1",
        "artifact_digest": "a" * 64,
    }
    payload.update(changes)
    return BytesIO(json.dumps(payload).encode("utf-8"))


def call():
    return inference_client.extract_page(
        service_url="http://inference.internal:8001/",
        image_png=b"\x89PNG synthetic",
        page_no=2,
        subject_hint="Toán",
        timeout_seconds=5,
        token="test-token",
    )


def test_valid_response_is_checked_and_model_provenance_is_retained(monkeypatch):
    def fake_urlopen(request, timeout):
        assert request.full_url == "http://inference.internal:8001/v1/extract-page"
        assert timeout == 5
        assert request.get_header("Authorization") == "Bearer test-token"
        payload = json.loads(request.data)
        assert payload["page_no"] == 2
        assert payload["schema_version"] == 1
        assert payload["subject_hint"] == "Toán"
        return response()

    monkeypatch.setattr(inference_client, "urlopen", fake_urlopen)
    output = call()
    assert output.page.page_no == 2
    assert output.page.blocks[0].text == "Hai cộng hai bằng mấy?"
    assert output.raw_output == {"text": "synthetic"}
    assert output.model_name == "synthetic-fixture"
    assert output.source == "VLM"
    assert output.artifact_digest == "a" * 64
    assert output.latency_ms >= 0


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (lambda: response(page_no=3), "INFERENCE_PAGE_MISMATCH"),
        (lambda: response(model_name=""), "INFERENCE_RESPONSE_INVALID"),
        (lambda: response(source="UNKNOWN"), "INFERENCE_RESPONSE_INVALID"),
        (lambda: response(artifact_digest="not-a-digest"), "INFERENCE_RESPONSE_INVALID"),
        (
            lambda: response(page_json={"schema_version": 2, "page_no": 2}),
            "INFERENCE_RESPONSE_INVALID",
        ),
        (lambda: BytesIO(b"not JSON"), "INFERENCE_RESPONSE_INVALID"),
    ],
)
def test_malformed_or_mismatched_output_never_reaches_draft(monkeypatch, payload, code):
    monkeypatch.setattr(inference_client, "urlopen", lambda request, timeout: payload())
    with pytest.raises(inference_client.ExtractionError) as exc:
        call()
    assert exc.value.code == code
    assert exc.value.retryable is False


def test_oversized_response_is_rejected_before_parsing(monkeypatch):
    monkeypatch.setattr(inference_client, "MAX_RESPONSE_BYTES", 10)
    monkeypatch.setattr(inference_client, "urlopen", lambda request, timeout: response())
    with pytest.raises(inference_client.ExtractionError) as exc:
        call()
    assert exc.value.code == "INFERENCE_RESPONSE_TOO_LARGE"


@pytest.mark.parametrize("status", [422, 503])
def test_http_errors_classify_retryability(monkeypatch, status):
    def reject(request, timeout):
        raise HTTPError(request.full_url, status, "synthetic", {}, None)

    monkeypatch.setattr(inference_client, "urlopen", reject)
    with pytest.raises(inference_client.ExtractionError) as exc:
        call()
    assert exc.value.retryable is (status == 503)


def test_network_timeout_is_retryable(monkeypatch):
    def fail_timeout(request, timeout):
        raise TimeoutError("synthetic timeout")

    monkeypatch.setattr(inference_client, "urlopen", fail_timeout)
    with pytest.raises(inference_client.ExtractionError) as exc:
        call()
    assert exc.value.code == "INFERENCE_UNAVAILABLE"
    assert exc.value.retryable


def test_invalid_configuration_fails_before_network():
    with pytest.raises(ValueError):
        inference_client.extract_page(service_url="file:///private", image_png=b"x", page_no=1)


def test_text_layer_request_does_not_send_image_and_requires_text_source(monkeypatch):
    def accepted(request, timeout):
        payload = json.loads(request.data)
        assert payload["text_layer"] == "Câu hỏi được trích trực tiếp từ PDF"
        assert "image_b64" not in payload
        return response(source="TEXT_LAYER")

    monkeypatch.setattr(inference_client, "urlopen", accepted)
    output = inference_client.extract_page(
        service_url="http://inference.internal:8001",
        text_layer="Câu hỏi được trích trực tiếp từ PDF",
        page_no=2,
    )
    assert output.source == "TEXT_LAYER"

    monkeypatch.setattr(
        inference_client, "urlopen", lambda request, timeout: response(source="VLM")
    )
    with pytest.raises(inference_client.ExtractionError, match="INFERENCE_RESPONSE_INVALID"):
        inference_client.extract_page(
            service_url="http://inference.internal:8001", text_layer="PDF text", page_no=2
        )

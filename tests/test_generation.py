from unittest.mock import Mock

import pytest
import requests

from src.generation.base import (
    
    FallbackGenerator,
    GenerationResult,
    OllamaUnavailable,
)
from src.generation.dummy import DummyGenerator
from src.generation.ollama import OllamaGenerator

@pytest.fixture
def documents():
    return [{"chunk_id": "json-1", "title": "JSON", "section": "json.dumps", "text": "dumps returns a string.",
             "source_url": "https://docs.python.org/3.12/library/json.html"}]


def response(content):
    result = Mock()
    result.json.return_value = {"message": {"content": content}}
    return result


def test_ollama_sends_grounding_and_uses_requested_model(monkeypatch, documents):
    post = Mock(return_value=response("It returns a string. [1]"))
    monkeypatch.setattr("src.generation.ollama.requests.post", post)
    generator = OllamaGenerator(model="qwen3.5:4b", timeout=900)

    result = generator.generate("What is dumps?", documents)

    assert result == GenerationResult("It returns a string. [1]", "ollama")
    args, kwargs = post.call_args
    assert args == ("http://127.0.0.1:11434/api/chat",)
    assert kwargs["timeout"] == (2.0, 900.0)
    payload = kwargs["json"]
    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is False and payload["think"] is False
    assert payload["options"]["num_predict"] == 192
    assert "Python documentation assistant" in payload["messages"][0]["content"]
    assert "dumps returns a string" in payload["messages"][1]["content"]
    assert "Section: json.dumps" in payload["messages"][1]["content"]


@pytest.mark.parametrize("failure", [requests.ConnectionError(), requests.Timeout(), requests.HTTPError()])
def test_provider_failure_falls_back(monkeypatch, documents, failure):
    monkeypatch.setattr("src.generation.ollama.requests.post", Mock(side_effect=failure))
    result = FallbackGenerator(OllamaGenerator()).generate("What?", documents)
    assert result.backend == "dummy"
    assert "dumps returns a string." in result.text
    assert "https://docs.python.org/3.12/library/json.html" in result.text
    assert result.fallback_reason


@pytest.mark.parametrize("content", ["", "No citation", "Incorrect [2]", "Text [0]", "Text [1] https://wrong.test", "<think>private</think> [1]"])
def test_unusable_responses_fall_back(monkeypatch, documents, content):
    monkeypatch.setattr("src.generation.ollama.requests.post", Mock(return_value=response(content)))
    result = FallbackGenerator(OllamaGenerator()).generate("What?", documents)
    assert result.backend == "dummy" and result.fallback_reason


def test_malformed_response_falls_back(monkeypatch, documents):
    bad_response = Mock()
    bad_response.json.return_value = {"message": {}}
    monkeypatch.setattr("src.generation.ollama.requests.post", Mock(return_value=bad_response))
    assert FallbackGenerator(OllamaGenerator()).generate("What?", documents).backend == "dummy"


def test_programming_errors_do_not_silently_fallback(documents):
    class Broken:
        def generate(self, question, docs):
            raise TypeError("programming bug")
    with pytest.raises(TypeError, match="programming bug"):
        FallbackGenerator(Broken()).generate("What?", documents)


def test_dummy_preserves_verbatim_evidence_and_sources(documents):
    assert DummyGenerator().generate("What?", documents).text == (
        "[1] dumps returns a string.\nSource: https://docs.python.org/3.12/library/json.html"
    )


@pytest.mark.parametrize("timeout", [0, float('inf'), -1, True])
def test_invalid_timeout_rejected(timeout):
    with pytest.raises(ValueError):
        OllamaGenerator(timeout=timeout)

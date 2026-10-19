import importlib.util
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from pypdf import PdfWriter

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_elsevier_api.py"
spec = importlib.util.spec_from_file_location("elsevier_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)


@pytest.mark.parametrize("pages,passed", [(1, False), (9, True)])
def test_diagnostic_never_counts_metadata_or_preview_as_full_text(
    tmp_path, monkeypatch, capsys, pages, passed
):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    doi = "10.1016/j.apenergy.2011.11.048"
    xml = (
        f"<root><coredata><doi>{doi}</doi><startingPage>274</startingPage>"
        "<endingPage>282</endingPage></coredata></root>"
    ).encode()
    client = httpx.Client
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "api.elsevier.com"
        assert request.headers["X-ELS-APIKey"] == "private-test-key"
        if request.url.params.get("view") == "FULL":
            return httpx.Response(400, json={"service-error": {"status": {
                "statusCode": "INVALID_INPUT",
                "statusText": "private-test-key https://example.com/?apiKey=private-test-key",
            }}})
        if request.headers["Accept"] == "application/pdf":
            return httpx.Response(200, content=buffer.getvalue())
        if request.headers["Accept"] == "text/xml":
            return httpx.Response(200, content=xml)
        return httpx.Response(200, json={"entitled": False})

    monkeypatch.setenv("ELSEVIER_API_KEY", "private-test-key")
    monkeypatch.setattr(diagnostic, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setattr(diagnostic.httpx, "Client", lambda **kwargs: client(
        **kwargs, transport=httpx.MockTransport(handler)
    ))
    monkeypatch.setattr("sys.argv", [str(SCRIPT), doi, "--output-root", str(tmp_path)])
    assert diagnostic.main() == (0 if passed else 1)
    report = json.loads(next(tmp_path.glob("*/检测报告.json")).read_text(encoding="utf-8"))
    assert report["full_text_verified"] is passed
    assert len(requests) == 5
    text = capsys.readouterr().out
    assert "private-test-key" not in text
    assert "private-test-key" not in json.dumps(report)
    assert not report["probes"][0]["full_text_verified"]
    assert not report["probes"][4]["full_text_verified"]
    if not passed:
        assert next(tmp_path.glob("*/*_UNVERIFIED.pdf"))


def test_compare_keys_uses_each_entered_key_without_changing_environment(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("ELSEVIER_API_KEY", "existing-environment-key")
    secrets = iter(["first-private-key", "", "second-private-key", "second-private-token"])
    answers = iter(["", "q"])
    calls = []
    monkeypatch.setattr(diagnostic.getpass, "getpass", lambda prompt: next(secrets))
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))

    def fake_main(argv, *, api_key, institution_token):
        calls.append((argv, api_key, institution_token))
        return 1 if len(calls) == 1 else 0

    monkeypatch.setattr(diagnostic, "main", fake_main)
    options = SimpleNamespace(doi="10.1016/j.apenergy.2011.11.048", timeout=30, output_root=tmp_path)
    assert diagnostic.compare_keys(options) == 0
    assert calls[0][1:] == ("first-private-key", None)
    assert calls[1][1:] == ("second-private-key", "second-private-token")
    assert calls[0][0][0] == calls[1][0][0]
    import os

    assert os.environ["ELSEVIER_API_KEY"] == "existing-environment-key"
    output = capsys.readouterr().out
    assert "private-key" not in output and "private-token" not in output
    assert "API 01" in output and "API 02" in output
    assert not list(tmp_path.iterdir())


def test_wrong_doi_input_reprompts_without_echoing_accidental_key(monkeypatch, capsys):
    answers = iter(["accidentally-pasted-private-key", ""])
    monkeypatch.setattr("builtins.input", lambda prompt: next(answers))
    assert diagnostic.read_doi() == diagnostic.DEFAULT_DOI
    output = capsys.readouterr().out
    assert "DOI 格式不正确" in output
    assert "accidentally-pasted-private-key" not in output


def test_credential_copy_wrappers_and_invalid_header_text():
    assert diagnostic.clean_credential('ELSEVIER_API_KEY="test-private-key"') == "test-private-key"
    for value in ["key with spaces", "中文密钥", "key\nnext-line"]:
        with pytest.raises(ValueError):
            diagnostic.clean_credential(value)

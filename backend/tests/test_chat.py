from app import assistant


def test_chat_english_auto(client):
    r = client.post("/api/chat", json={"message": "How do I get a TAJ card?", "topic": "healthcare"})
    assert r.status_code == 200
    body = r.json()
    assert body["language"] == "en" and body["topic"] == "healthcare" and body["mock"] is True
    assert body["reply"]


def test_chat_hungarian_auto(client):
    r = client.post("/api/chat", json={"message": "Hogyan kapok TAJ kártyát?"})
    assert r.json()["language"] == "hu"


def test_chat_forced_language(client):
    r = client.post("/api/chat", json={"message": "Hogyan kapok TAJ kártyát?", "language": "en"})
    assert r.json()["language"] == "en"


def test_chat_rejects_other_languages_and_topics(client):
    assert client.post("/api/chat", json={"message": "hi", "language": "pt"}).status_code == 422
    assert client.post("/api/chat", json={"message": "hi", "topic": "food"}).status_code == 422
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_chat_with_history(client):
    r = client.post("/api/chat", json={"message": "And then?", "history": [
        {"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]})
    assert r.status_code == 200


def test_topics(client):
    t = client.get("/api/topics").json()
    assert [x["id"] for x in t] == ["healthcare", "university", "immigration", "translation"]
    assert all(set(x["label"]) == {"en", "hu"} for x in t)


def test_detect_language():
    assert assistant.detect_language("Where is the dormitory?") == "en"
    assert assistant.detect_language("Hol van a kollégium?") == "hu"
    assert assistant.detect_language("a cat is a pet") == "en"


def test_prompt_rules():
    p = assistant.build_system_prompt("hu", "translation")
    assert "magyarul" in p and "Hungarian first" in p and "112" in p


def test_knowledge_is_injected(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "KNOWLEDGE_DIR", tmp_path)
    (tmp_path / "README.md").write_text("ignore me", encoding="utf-8")
    (tmp_path / "test-questions.md").write_text("ignore me too", encoding="utf-8")
    (tmp_path / "healthcare.md").write_text("TAJ fact. Source: https://example.org", encoding="utf-8")
    p = assistant.build_system_prompt("en", "healthcare")
    assert "TAJ fact" in p and "ignore me" not in p and "VERIFIED KNOWLEDGE" in p


def test_no_knowledge_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(assistant, "KNOWLEDGE_DIR", tmp_path / "missing")
    assert "VERIFIED KNOWLEDGE (prepared" not in assistant.build_system_prompt("en", "general")


def test_ai_failure_is_502(client, monkeypatch):
    from app import agent

    monkeypatch.setattr(agent, "MOCK_MODE", False)
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "invalid")

    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(assistant, "answer", boom)
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 502


class _Resp:
    def __init__(self, text):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]


def _fake_openai(monkeypatch, behaviour):
    """behaviour: dict model -> Exception or reply text; records the call order."""
    calls = []

    class FakeClient:
        def __init__(self, **kw):
            self.chat = type("Chat", (), {"completions": self})()

        def create(self, model, **kw):
            calls.append(model)
            r = behaviour[model]
            if isinstance(r, Exception):
                raise r
            return _Resp(r)

    import openai
    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    return calls


class Overloaded(Exception):
    status_code = 503


class NoCredits(Exception):
    status_code = 429
    body = {"code": "insufficient_quota"}


def test_fallback_model_used_when_main_overloaded(monkeypatch):
    calls = _fake_openai(monkeypatch, {"main": Overloaded(), "backup": "Hello"})
    r = assistant.answer("hi", "en", "general", [], "k", "main", False, None, ["backup"])
    assert calls == ["main", "backup"] and r["model"] == "backup" and r["reply"] == "Hello"


def test_no_fallback_on_quota_error(monkeypatch):
    calls = _fake_openai(monkeypatch, {"main": NoCredits(), "backup": "Hello"})
    try:
        assistant.answer("hi", "en", "general", [], "k", "main", False, None, ["backup"])
        assert False, "should raise"
    except NoCredits:
        pass
    assert calls == ["main"]


def test_all_models_overloaded_raises(monkeypatch):
    _fake_openai(monkeypatch, {"main": Overloaded(), "backup": Overloaded()})
    try:
        assistant.answer("hi", "en", "general", [], "k", "main", False, None, ["backup"])
        assert False, "should raise"
    except Overloaded:
        pass

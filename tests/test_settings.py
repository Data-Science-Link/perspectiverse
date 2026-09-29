from pipeline.settings import load_dotenv, load_settings


def test_dotenv_fills_missing_names_without_overriding(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "export OPENAI_BASE_URL=https://api.deepinfra.com/v1/openai",
                'OPENAI_MODEL="meta-llama/Llama-3.3-70B-Instruct-Turbo"',
                "OPENAI_API_KEY=",
                "KEEP_ME=from-file",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("KEEP_ME", "from-process")
    load_dotenv(env_file)
    assert env_file.read_text(encoding="utf-8").count("OPENAI_API_KEY=") == 1
    import os

    assert os.environ["OPENAI_BASE_URL"] == "https://api.deepinfra.com/v1/openai"
    assert os.environ["OPENAI_MODEL"] == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    assert "OPENAI_API_KEY" not in os.environ or not os.environ.get("OPENAI_API_KEY")
    assert os.environ["KEEP_ME"] == "from-process"


def test_deepinfra_base_url_selects_llama_in_settings(monkeypatch, tmp_path):
    config = tmp_path / "pipeline.yaml"
    config.write_text("label_backend: auto\nopenai_model: gpt-4o-mini\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepinfra.com/v1/openai")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    settings = load_settings(config)
    assert settings["openai_model"] == "meta-llama/Llama-3.3-70B-Instruct-Turbo"

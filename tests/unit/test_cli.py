from moggy import __version__
from moggy.config import get_settings
from typer.testing import CliRunner

runner = CliRunner()


def test_version_output():
    from moggy.cli import app

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert f"TraderMoggy v{__version__}" in result.output


def test_help_lists_commands():
    from moggy.cli import app

    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
    assert "config" in result.output


def test_unknown_command_exits_nonzero():
    from moggy.cli import app

    result = runner.invoke(app, ["doesnotexist"])
    assert result.exit_code != 0


def test_config_redacts_secrets(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-supersecret")
    monkeypatch.setenv("REDDIT_CLIENT_ID", "myredditid")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "myredditscret")

    from moggy.cli import app

    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "***" in result.output
    assert "sk-ant-supersecret" not in result.output
    assert "myredditid" not in result.output
    assert "myredditscret" not in result.output


def test_config_shows_non_secret_fields(monkeypatch):
    monkeypatch.setenv("DISCOVER_LIMIT", "42")
    monkeypatch.setenv("OUTPUT_DIR", "/tmp/testout")

    from moggy.cli import app

    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
    assert "42" in result.output
    assert "/tmp/testout" in result.output


def test_data_error_is_exported():
    from moggy.data import DataError

    err = DataError(source="test", message="something failed")
    assert err.source == "test"
    assert err.message == "something failed"
    assert err == DataError(source="test", message="something failed")


def test_config_empty_secret_not_redacted(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    display = get_settings().display()
    assert display["anthropic_api_key"] != "***"


def test_settings_defaults(monkeypatch):
    for key in ("DEFAULT_MODEL", "DISCOVER_LIMIT", "DISCOVER_MIN_SCORE", "OUTPUT_DIR"):
        monkeypatch.delenv(key, raising=False)

    s = get_settings()
    assert s.default_model == "claude-sonnet-4-6"
    assert s.discover_limit == 15
    assert s.discover_min_score == 0.0
    assert s.output_dir == "./output"
    assert s.reddit_user_agent == "MoggyTrader/0.1"


def test_settings_cache_returns_same_object():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_cache_clears():
    s1 = get_settings()
    get_settings.cache_clear()
    s2 = get_settings()
    assert s1 is not s2


def test_namespace_packages_importable():
    import moggy.agents
    import moggy.buzz
    import moggy.output
    import moggy.research

    assert moggy.agents is not None
    assert moggy.buzz is not None
    assert moggy.output is not None
    assert moggy.research is not None

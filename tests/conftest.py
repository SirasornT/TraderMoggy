import pytest

from moggy.config import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def isolate_env_file(tmp_path, monkeypatch):
    """Prevent ambient .env files in the working directory from polluting tests."""
    monkeypatch.chdir(tmp_path)

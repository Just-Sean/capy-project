"""gunicorn.conf.py: the production server's settings."""

import runpy
import types
from pathlib import Path

import pytest
from gunicorn.config import Config

CONFIG_FILE = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"


def load(monkeypatch, **environment):
    """Run the config file the way Gunicorn does and return only the settings it
    defines (leaving out Python's own names and imported modules)."""
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    values = runpy.run_path(str(CONFIG_FILE))
    return {
        name: value
        for name, value in values.items()
        if not name.startswith("__") and not isinstance(value, types.ModuleType)
    }


def gunicorn_config(monkeypatch, **environment):
    """A Gunicorn Config with the file's settings applied, as Gunicorn would use it."""
    config = Config()
    for name, value in load(monkeypatch, **environment).items():
        config.set(name, value)  # raises if a value has the wrong type
    return config


def test_every_name_is_a_real_gunicorn_setting(monkeypatch):
    # Gunicorn silently ignores unknown names, so a typo would just be lost.
    known = Config().settings
    unknown = [name for name in load(monkeypatch) if name not in known]
    assert unknown == []


def test_gunicorn_accepts_every_value(monkeypatch):
    assert gunicorn_config(monkeypatch).control_socket_disable is True


def test_production_values(monkeypatch):
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    config = gunicorn_config(monkeypatch)
    assert config.workers == 1
    assert config.timeout == 30
    assert config.graceful_timeout == 30
    assert config.max_requests == 1000
    assert config.max_requests_jitter == 100
    assert config.accesslog == config.errorlog == "-"


def test_listens_only_on_this_machine_even_with_port_set(monkeypatch):
    # Without an explicit bind, a PORT variable makes Gunicorn listen on 0.0.0.0.
    config = gunicorn_config(monkeypatch, PORT="9000")
    assert config.bind == ["127.0.0.1:8000"]


def test_workers_come_from_web_concurrency(monkeypatch):
    assert gunicorn_config(monkeypatch, WEB_CONCURRENCY="5").workers == 5


def test_a_wrong_web_concurrency_fails_loudly(monkeypatch):
    with pytest.raises(ValueError):
        load(monkeypatch, WEB_CONCURRENCY="lots")

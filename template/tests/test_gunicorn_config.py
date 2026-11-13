"""gunicorn.conf.py: the production server's settings."""

import runpy
from pathlib import Path

import pytest
from gunicorn.config import Config

CONFIG_FILE = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"


def load(monkeypatch, **environment):
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    values = runpy.run_path(str(CONFIG_FILE))
    return {k: v for k, v in values.items() if not k.startswith("__") and k != "os"}


def test_every_name_is_a_real_gunicorn_setting(monkeypatch):
    # Gunicorn silently ignores unknown names, so a typo would just be lost.
    known = Config().settings
    unknown = [name for name in load(monkeypatch) if name not in known]
    assert unknown == []


def test_gunicorn_accepts_every_value(monkeypatch):
    config = Config()
    for name, value in load(monkeypatch).items():
        config.set(name, value)  # raises if a value has the wrong type
    assert config.control_socket_disable is True


def test_production_values(monkeypatch):
    monkeypatch.delenv("WEB_CONCURRENCY", raising=False)
    values = load(monkeypatch)
    assert values["workers"] == 1
    assert values["worker_tmp_dir"] == "/dev/shm"  # noqa: S108 (see gunicorn.conf.py)
    assert values["accesslog"] == values["errorlog"] == "-"
    assert values["max_requests"] > 0
    assert "bind" not in values  # 127.0.0.1 by default; the Dockerfile sets 0.0.0.0


def test_workers_come_from_web_concurrency(monkeypatch):
    assert load(monkeypatch, WEB_CONCURRENCY="5")["workers"] == 5


def test_a_wrong_web_concurrency_fails_loudly(monkeypatch):
    with pytest.raises(ValueError):
        load(monkeypatch, WEB_CONCURRENCY="lots")

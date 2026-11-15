"""Production refuses to start in an unsafe shape; the shipped Compose file fails closed."""

import asyncio
import re
from pathlib import Path

import pytest

from app import config, startup
from app.startup import UnsafeStartup, enforce_safe_startup, production_problems, wait_for_docker

ROOT = Path(__file__).resolve().parent.parent


def test_safe_production_settings_have_no_problems():
    assert production_problems(allow_unsafe_host=False, allow_code_override=False, docker_available=True) == []


@pytest.mark.parametrize(
    ("kwargs", "needle"),
    [
        ({"allow_unsafe_host": True}, "ALLOW_UNSAFE_HOST_SUBPROCESS"),
        ({"allow_code_override": True}, "ALLOW_CODE_OVERRIDE"),
        ({"docker_available": False}, "Docker"),
    ],
)
def test_each_unsafe_setting_is_named(kwargs, needle):
    settings = {"allow_unsafe_host": False, "allow_code_override": False, "docker_available": True, **kwargs}
    problems = production_problems(**settings)
    assert len(problems) == 1 and needle in problems[0]


def test_all_problems_are_reported_together():
    assert len(production_problems(allow_unsafe_host=True, allow_code_override=True, docker_available=False)) == 3


def _production(monkeypatch, **overrides):
    monkeypatch.setattr(config, "IS_DEV", False)
    monkeypatch.setattr(config, "APP_ENV", "production")
    monkeypatch.setattr(config, "ALLOW_UNSAFE_HOST_SUBPROCESS", False)
    monkeypatch.setattr(config, "ALLOW_CODE_OVERRIDE", False)
    monkeypatch.setattr(config, "DOCKER_STARTUP_WAIT_SECONDS", 0)
    monkeypatch.setattr(config, "API_KEY", "k")
    for name, value in overrides.items():
        monkeypatch.setattr(config, name, value)


def test_production_with_safe_settings_starts(monkeypatch):
    _production(monkeypatch)
    enforce_safe_startup(lambda: True)  # no exception


@pytest.mark.parametrize("flag", ["ALLOW_UNSAFE_HOST_SUBPROCESS", "ALLOW_CODE_OVERRIDE"])
def test_production_refuses_dangerous_flags(monkeypatch, flag):
    _production(monkeypatch, **{flag: True})
    with pytest.raises(UnsafeStartup, match=flag):
        enforce_safe_startup(lambda: True)


def test_production_refuses_without_docker(monkeypatch):
    _production(monkeypatch)
    with pytest.raises(UnsafeStartup, match="Docker"):
        enforce_safe_startup(lambda: False)


def test_development_skips_the_checks(monkeypatch):
    monkeypatch.setattr(config, "IS_DEV", True)
    monkeypatch.setattr(config, "ALLOW_UNSAFE_HOST_SUBPROCESS", True)
    enforce_safe_startup(lambda: False)  # local experiments stay possible


def test_missing_smtp_only_warns(monkeypatch, caplog):
    _production(monkeypatch, SMTP_HOST="", MAIL_FROM="")
    enforce_safe_startup(lambda: True)
    assert "SMTP is not configured" in caplog.text


def test_waits_for_a_slow_socket_proxy():
    answers = iter([False, False, True])
    naps = []
    assert wait_for_docker(lambda: next(answers), timeout=60, sleep=naps.append, interval=1) is True
    assert naps == [1, 1]


def test_gives_up_after_the_timeout():
    assert wait_for_docker(lambda: False, timeout=0, sleep=lambda _: None) is False


def test_server_lifespan_runs_the_check(monkeypatch):
    from app import main

    _production(monkeypatch, ALLOW_CODE_OVERRIDE=True)
    monkeypatch.setattr(main, "_is_docker_available", lambda: True)

    async def boot():
        async with main.lifespan(main.app):
            pass

    with pytest.raises(UnsafeStartup):
        asyncio.run(boot())
    assert startup.enforce_safe_startup is main.enforce_safe_startup


def test_compose_fails_closed_and_stays_local():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "APP_ENV=${APP_ENV:-production}" in compose
    ports = re.findall(r'^\s*-\s*"([^"]+):8000"', compose, flags=re.M)
    assert ports and all(p.startswith("127.0.0.1:") for p in ports), ports
    for flag in ("ALLOW_UNSAFE_HOST_SUBPROCESS", "ALLOW_CODE_OVERRIDE"):
        assert flag not in compose  # never switched on by the shipped stack

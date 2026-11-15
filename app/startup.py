"""Checks that run before the server accepts traffic.

Outside development the server refuses to start in an unsafe shape instead of
starting and quietly running model output somewhere it shouldn't.
"""

import logging
import time
from collections.abc import Callable

from app import config

logger = logging.getLogger("self_improving_agent")


class UnsafeStartup(RuntimeError):
    """The configuration is not safe to serve in production."""


def production_problems(*, allow_unsafe_host: bool, allow_code_override: bool, docker_available: bool) -> list[str]:
    """Every reason this configuration must not serve production traffic."""
    problems = []
    if allow_unsafe_host:
        problems.append("ALLOW_UNSAFE_HOST_SUBPROCESS is on, so model output could run on the host")
    if allow_code_override:
        problems.append("ALLOW_CODE_OVERRIDE is on, so /execute would run any code a caller sends")
    if not docker_available:
        problems.append("Docker is not reachable, so there is no sandbox to run code in")
    return problems


def wait_for_docker(
    probe: Callable[[], bool], timeout: float, sleep: Callable[[float], None] = time.sleep, interval: float = 2.0
) -> bool:
    """Polls `probe` until it answers or `timeout` seconds pass.

    In Compose the socket proxy can come up a moment after the API, so one failed
    probe at boot doesn't mean Docker is missing.
    """
    deadline = time.monotonic() + max(0.0, timeout)
    while True:
        if probe():
            return True
        if time.monotonic() >= deadline:
            return False
        sleep(interval)


def enforce_safe_startup(docker_probe: Callable[[], bool]) -> None:
    """Raises UnsafeStartup in production when the server shouldn't run as configured."""
    if config.IS_DEV:
        return
    problems = production_problems(
        allow_unsafe_host=config.ALLOW_UNSAFE_HOST_SUBPROCESS,
        allow_code_override=config.ALLOW_CODE_OVERRIDE,
        docker_available=wait_for_docker(docker_probe, config.DOCKER_STARTUP_WAIT_SECONDS),
    )
    if problems:
        detail = "; ".join(problems)
        raise UnsafeStartup(
            f"Refusing to start with APP_ENV={config.APP_ENV}: {detail}. "
            "Fix the setting, or set APP_ENV=development on a machine only you can reach."
        )
    from app import mailer

    if not mailer.is_configured():
        # Not fatal, but nobody can confirm an email address until it is set
        logger.warning("SMTP is not configured: sign-up, verification and reset emails won't be sent")
    if config.PUBLIC_BASE_URL.startswith("http://localhost"):
        logger.warning("PUBLIC_BASE_URL is %s: links in emails will point there", config.PUBLIC_BASE_URL)

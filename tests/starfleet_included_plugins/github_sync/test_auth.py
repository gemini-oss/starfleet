"""Tests for the GitHub Sync worker's GitHub authentication components

Tests out the authentication code for GitHub.

:Module: starfleet.tests.starfleet_included_plugins.github_sync.test_auth
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

# pylint: disable=unused-argument,too-many-arguments,too-many-locals
from datetime import datetime, timezone, UTC
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import jwt
import pytest


def test_make_app_token(unit_test_secrets: Dict[str, Any]) -> None:
    """This tests that we get a proper GitHub token back out"""
    from starfleet.worker_ships.plugins.github_sync.auth import GitHubAuthManager
    from tests.starfleet_included_plugins.github_sync.conftest import TEST_PUBLIC_KEY

    secret = unit_test_secrets["GitHubSyncWorker"]["fakeorg"]

    auth_manager = GitHubAuthManager()
    auth_manager._make_app_token("fakeorg", "1234567", secret)  # noqa
    token = auth_manager._app_tokens["fakeorg"]

    payload = jwt.decode(token, TEST_PUBLIC_KEY, algorithms=["RS256"])

    # Note breakpoints while debugging can cause issues with this due to timing. Make breakpoints for testing this after the "now ="
    now = int(datetime.now(tz=timezone.utc).timestamp())
    assert payload["iss"] == "1234567"
    assert now - 65 <= payload["iat"] < now
    assert now + 301 >= payload["exp"] > now


def test_make_installation_token(mock_installation_token: MagicMock) -> None:
    """This tests that we get a proper GitHub installation token out."""
    from starfleet.worker_ships.plugins.github_sync.auth import GitHubAuthError, GitHubAuthManager

    auth_manager = GitHubAuthManager()
    auth_manager._app_tokens["fakeorg"] = "sometokenlol"
    auth_manager._make_installation_token("fakeorg", "987654")

    assert auth_manager._installation_tokens["fakeorg"]["token"] == "lolsometoken"
    assert auth_manager._installation_tokens["fakeorg"]["expiration"] > int(datetime.now(UTC).timestamp())

    # Test with an invalid status code:
    mock_installation_token.post.return_value.status_code = 401
    with mock.patch("starfleet.worker_ships.plugins.github_sync.auth.LOGGER") as mocked_logger:
        with pytest.raises(GitHubAuthError):
            auth_manager._make_installation_token("fakeorg", "987654")

        assert "installation token: 401" in mocked_logger.error.call_args.args[0]


def test_authenticate_github(mock_installation_token: MagicMock) -> None:
    """This tests the full authentication functionality and caching logic."""
    from starfleet.worker_ships.plugins.github_sync.auth import GitHubAuthManager

    auth_manager = GitHubAuthManager()
    auth_token = auth_manager.authenticate("fakeorg", "1234567", "987654")
    assert auth_token == {"Authorization": "Bearer lolsometoken"}

    # Test the caching logic:
    with mock.patch("starfleet.worker_ships.plugins.github_sync.auth.LOGGER") as mocked_logger:
        assert auth_manager.authenticate("fakeorg", "1234567", "987654") == auth_token
        assert "Using cached credentials" in mocked_logger.debug.call_args.args[0]

        # Test the exceptions:
        mocked_logger.reset_mock()
        with pytest.raises(KeyError) as exc:
            auth_manager.authenticate("lolno", "1234567", "987654")
        assert exc.value.args[0] == "lolno"
        assert "organization: lolno" in mocked_logger.error.call_args.args[0]


def test_github_auth_decorator(mock_installation_token: MagicMock) -> None:
    """This tests that the GitHub auth decorator works and properly injects credentials to functions wrapped with it."""
    from starfleet.worker_ships.plugins.github_sync.auth import github_auth

    @github_auth
    def some_github_function(organization: str, some_other_arg: str, github_headers: Dict[str, str] = None, some_kwarg: str = None) -> None:
        assert organization == "fakeorg"
        assert github_headers == {"Authorization": "Bearer lolsometoken"}
        assert some_other_arg == "some other arg"
        assert some_kwarg == "some kwarg"

    some_github_function("fakeorg", "1234567", "987654", "some other arg", some_kwarg="some kwarg")  # pylint: disable=redundant-keyword-arg

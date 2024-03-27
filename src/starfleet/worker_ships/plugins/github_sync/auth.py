"""The Authentication code for the GitHubSyncWorker

Common utilities for GitHub authentication related work is here.

:Module: starfleet.worker_ships.plugins.gihtub_sync.auth
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Any, Callable

import jwt
import requests

from starfleet.utils.logging import LOGGER
from starfleet.utils.secrets import SECRETS_MANAGER

# pylint: disable=pointless-string-statement
"""GitHub authentication requires a few things to be done:
1. The app needs to be made in the org
2. The app needs to be installed in the org
3. You need to make what is referred to as an "app token", which makes use of the app's private key
4. With the "app token" you then need to obtain the "installation token" to operate in the org.
5. Once you have the "installation token", then you are able to make API calls to GitHub.
"""


class GitHubAuthError(Exception):
    """Error raised if we get an invalid response code back from GitHub when trying to get the installation token."""


class GitHubAuthManager:
    """This is a class that manages the GitHub authentication as a singleton."""

    def __init__(self):
        self._app_tokens: Dict[str, str] = {}
        self._installation_tokens: Dict[str, Dict[str, Any]] = {}

    def _make_app_token(self, organization: str, app_id: str, secret: str) -> None:
        """
        This will generate the "app" Bearer tokens that are used for obtaining the corresponding GitHub installation tokens.

        This follows GitHub's documentation here:
        https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps#authenticating-as-a-github-app
        """
        LOGGER.debug(f"[🔑] Generating app token for org: {organization}...")

        now = int(datetime.now(tz=timezone.utc).timestamp())
        payload = {
            "iat": now - 60,  # issued at time, 60 seconds in the past to allow for clock drift
            "exp": now + 300,  # JWT expiration time (can be a max of 10 minute, but we are setting to 3)
            "iss": app_id,  # GitHub App's identifier
        }

        token = jwt.encode(payload, secret, algorithm="RS256")
        self._app_tokens[organization] = token

    def _make_installation_token(self, organization: str, installation_id: str) -> None:
        """This will make the installation token for the corresponding app.

        Follows the instructions here: https://docs.github.com/en/developers/apps/building-github-apps/authenticating-with-github-apps#authenticating-as-an-installation
        """
        LOGGER.debug(f"[🔑] Generating the installation token for org: {organization}...")
        auth_header = {"Authorization": f"Bearer {self._app_tokens[organization]}"}
        result = requests.post(f"https://api.github.com/app/installations/{installation_id}/access_tokens", headers=auth_header, timeout=20)

        if result.status_code != 201:
            LOGGER.error(f"[💥] Invalid response back from GitHub while obtaining the installation token: {result.status_code}")
            raise GitHubAuthError()

        result_json = result.json()
        token = result_json["token"]
        expiration = int(datetime.strptime(result_json["expires_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp())
        self._installation_tokens[organization] = {"expiration": expiration, "token": token}

    def authenticate(self, organization: str, app_id: str, installation_id: str) -> Dict[str, str]:
        """This will perform all the logic required to authenticate to GitHub.

        This will raise a ValueError if the organization name is not in the configuration.
        """
        # If we have unexpired cached credentials, then use them:
        current_creds = self._installation_tokens.get(organization, {})
        if current_creds.get("expiration", 0) > int(datetime.now(tz=timezone.utc).timestamp()):
            LOGGER.debug("[💵] Using cached credentials.")
            return {"Authorization": f"Bearer {current_creds['token']}"}

        # Make the app token:
        try:
            secret = SECRETS_MANAGER.secrets["GitHubSyncWorker"][organization]
            self._make_app_token(organization, app_id, secret)
        except KeyError:
            LOGGER.error(f"[💥] We are missing the private key for the GitHub organization: {organization} in the GitHubSyncWorker's secret dictionary.")
            raise

        # Make the installation token:
        self._make_installation_token(organization, installation_id)

        return {"Authorization": f"Bearer {self._installation_tokens[organization]['token']}"}


GITHUB_AUTH_MANGER = GitHubAuthManager()


def github_auth(func: Callable) -> Callable:
    """This is a decorator for injecting GitHub Authorization headers into your function."""

    @wraps(func)
    def wrapped_function(organization: str, app_id: str, installation_id: str, *args, **kwargs) -> Any:
        """This is the wrapped function that will get the GitHub credentials injected into it.

        The function needs to take 3 positional args: the organization name, the App ID, and the Installation ID.
        The auth header is passed in via a keyword arg named `github_headers`, which is a Dict[str, str].

        Example usage:
        @github_auth
        def my_function(organization: str, github_headers: Dict[str, str] = None) -> None:
            ...
            requests.post("https://api.github.com...", headers=github_headers)
            ...
        """
        kwargs["github_headers"] = GITHUB_AUTH_MANGER.authenticate(organization, app_id, installation_id)
        return func(organization, *args, **kwargs)

    return wrapped_function

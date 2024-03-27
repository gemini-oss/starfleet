"""Starfleet's Slack notification module

This module contains functions that make it easy to provide notifications to Slack.

:Module: starfleet.utils.slack
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from typing import Any, Dict, List

from slack_sdk import WebClient

from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER
from starfleet.utils.secrets import SECRETS_MANAGER


class SlackError(Exception):
    """
    Raises an exception if there was an error sending a message to Slack. This raises an exception if there was an error (this should generally be sent if there was
    an error sending an error vs. a standard info message).
    """


class SlackClient:
    """This is a helper-class for interacting with Slack for sending out notifications."""

    def __init__(self, token: str = None):
        """
        This will instantiate a client. Preferred is to keep the kwargs blank in practice (pass in values for unit testing). Values will be lazily loaded if not present
        from the secrets and configuration managers.
        """
        if token:
            self._web_client = WebClient(token=token)
        else:
            self._web_client = None

        self._enabled = None

    def reset(self) -> None:
        """Used as a convenience in unit testing to blow away the existing Slack web client to avoid stale mocks."""
        self._web_client = None
        self._enabled = None

    def _post_message(self, channel_id: str, blocks: List[Dict[str, Any]]) -> bool:
        """
        This will post the message in question over to Slack. This will only post to slack if the support is enabled in the configuration (default is don't send to Slack)

        :returns bool: True if this was successful or False otherwise. (Returns True if Slack support is not enabled)
        """
        # If we are not configured to send to Slack then this is a noop:
        if self._enabled is None:
            self._enabled = STARFLEET_CONFIGURATION.config["STARFLEET"].get("SlackEnabled", False)

        if not self._enabled:
            return True

        if not self._web_client:
            self._web_client = WebClient(token=SECRETS_MANAGER.secrets["STARFLEET"]["SlackToken"])

        try:
            result = self._web_client.chat_postMessage(channel=channel_id, blocks=blocks, text=blocks[0]["text"]["text"])

            if not result.data["ok"]:
                LOGGER.error(f"[💥] Unable to post message to Slack:\nChannel: {channel_id},\nMessage: {blocks}")
                LOGGER.error(f"[💥] Slack response: {result}")
                return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            LOGGER.error(f"[😱] Unable to post message to Slack:\nChannel: {channel_id},\nMessage: {blocks}")
            LOGGER.exception(exc)
            return False

        return True

    def post_info(self, channel_id: str, title: str, body_markdown: str) -> None:
        """This is a shortcut message to send an info message to Slack."""
        message = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"ℹ️  {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body_markdown},
            },
        ]

        if not self._post_message(channel_id, message):
            LOGGER.error("[🙊] Failed to post informational message to Slack!")

    def post_success(self, channel_id: str, title: str, body_markdown: str) -> None:
        """This is a shortcut message to send a success message to Slack."""
        message = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"✅  {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body_markdown},
            },
        ]

        if not self._post_message(channel_id, message):
            LOGGER.error("[🙊] Failed to post success message to Slack!")

    def post_important(self, channel_id: str, title: str, body_markdown: str) -> None:
        """
        This is a shortcut message to send an "Important" message to Slack.

        :raises SlackError: If there is an error sending a message to slack.
        """
        message = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📣  {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body_markdown},
            },
        ]

        if not self._post_message(channel_id, message):
            LOGGER.error("[🙊] Failed to post important message to Slack!")

    def post_problem(self, channel_id: str, title: str, body_markdown: str) -> None:
        """
        This is a shortcut message to send a "Problem" message to Slack.

        :raises SlackError: If there is an error sending a message to slack.
        """
        message = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨  {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": body_markdown},
            },
        ]

        if not self._post_message(channel_id, message):
            raise SlackError()


# The token is provided automatically by SecretsManager when this is used
SLACK_CLIENT = SlackClient()

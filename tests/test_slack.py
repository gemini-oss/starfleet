"""Unit tests for Starfleets's Slack notification code.

Tests for the Starfleet Slack logic.

:Module: starfleet.tests.test_slack
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument,no-member
from typing import Any, Dict
from unittest import mock
from unittest.mock import MagicMock

import pytest


class ErrorResponse:
    """An error response from Slack."""

    def __init__(self):
        self.data = {"ok": False}


def test_slack_lazy_load(mock_slack_api: MagicMock) -> None:
    """This tests the lazy load logic for the Slack WebClient"""
    from starfleet.utils.slack import SlackClient

    test_client = SlackClient()
    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_success("some_channel", "Success!", "it worked!")
        assert not mocked_logger.error.called


def test_post_slack_info_message(mock_slack_api: MagicMock) -> None:
    """This tests that we can post an informational message to Slack."""
    from starfleet.utils.slack import SlackClient

    test_client = SlackClient(token="lolol")
    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_info("some_channel", "The Title!", "some _markdown_ text!")

        assert not mocked_logger.error.called
        assert test_client._web_client.chat_postMessage.call_args.kwargs["channel"] == "some_channel"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][0]["text"]["text"] == "ℹ️  The Title!"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"] == "some _markdown_ text!"

        # And with an error:
        mocked_logger.reset_mock()
        test_client._web_client.chat_postMessage.reset_mock()
        test_client._web_client.chat_postMessage.return_value = ErrorResponse()
        test_client.post_info("some_channel", "The Title!", "some _markdown_ text!")
        assert "some_channel" in mocked_logger.error.call_args_list[0][0][0]
        assert mocked_logger.error.call_args_list[2][0][0] == "[🙊] Failed to post informational message to Slack!"


def test_post_slack_success_message(mock_slack_api: MagicMock) -> None:
    """This tests that we can post a success message to Slack."""
    from starfleet.utils.slack import SlackClient

    test_client = SlackClient(token="lolol")
    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_success("some_channel", "The Title!", "some _markdown_ text!")

        assert not mocked_logger.error.called
        assert test_client._web_client.chat_postMessage.call_args.kwargs["channel"] == "some_channel"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][0]["text"]["text"] == "✅  The Title!"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"] == "some _markdown_ text!"

        # And with an error:
        mocked_logger.reset_mock()
        test_client._web_client.chat_postMessage.reset_mock()
        test_client._web_client.chat_postMessage.return_value = ErrorResponse()
        test_client.post_success("some_channel", "The Title!", "some _markdown_ text!")
        assert "some_channel" in mocked_logger.error.call_args_list[0][0][0]
        assert mocked_logger.error.call_args_list[2][0][0] == "[🙊] Failed to post success message to Slack!"


def test_post_slack_important_message(mock_slack_api: MagicMock) -> None:
    """This tests that we can post an important message to Slack."""
    from starfleet.utils.slack import SlackClient

    test_client = SlackClient(token="lolol")
    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_important("some_channel", "The Title!", "some _markdown_ text!")

        assert not mocked_logger.error.called
        assert test_client._web_client.chat_postMessage.call_args.kwargs["channel"] == "some_channel"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][0]["text"]["text"] == "📣  The Title!"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"] == "some _markdown_ text!"

        # And with an error:
        mocked_logger.reset_mock()
        test_client._web_client.chat_postMessage.reset_mock()
        test_client._web_client.chat_postMessage.return_value = ErrorResponse()
        test_client.post_important("some_channel", "The Title!", "some _markdown_ text!")
        assert "some_channel" in mocked_logger.error.call_args_list[0][0][0]
        assert mocked_logger.error.call_args_list[2][0][0] == "[🙊] Failed to post important message to Slack!"


def test_post_slack_problem_message(mock_slack_api: MagicMock) -> None:
    """This tests that we can post an error message to Slack."""
    from starfleet.utils.slack import SlackClient, SlackError

    test_client = SlackClient(token="lolol")
    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_problem("some_channel", "The Title!", "some _markdown_ text!")

        assert not mocked_logger.error.called
        assert test_client._web_client.chat_postMessage.call_args.kwargs["channel"] == "some_channel"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][0]["text"]["text"] == "🚨  The Title!"
        assert test_client._web_client.chat_postMessage.call_args.kwargs["blocks"][1]["text"]["text"] == "some _markdown_ text!"

        # And with an error:
        mocked_logger.reset_mock()
        test_client._web_client.chat_postMessage.reset_mock()
        test_client._web_client.chat_postMessage.return_value = ErrorResponse()
        with pytest.raises(SlackError):
            test_client.post_problem("some_channel", "The Title!", "some _markdown_ text!")
        assert "some_channel" in mocked_logger.error.call_args_list[0][0][0]


def test_with_slack_exception(mock_slack_api: MagicMock) -> None:
    """This tests that we can handle an exception raised by Slack itself."""
    from starfleet.utils.slack import SlackClient

    test_client = SlackClient(token="lolol")
    test_client._web_client = MagicMock()
    test_client._web_client.chat_postMessage = MagicMock(side_effect=Exception("some error"))

    with mock.patch("starfleet.utils.slack.LOGGER") as mocked_logger:
        test_client.post_info("some_channel", "The Title!", "some _markdown_ text!")

        assert "some_channel" in mocked_logger.error.call_args_list[0][0][0]
        assert mocked_logger.error.call_args_list[1][0][0] == "[🙊] Failed to post informational message to Slack!"


def test_disable_slack_config(mock_slack_api: MagicMock, test_configuration: Dict[str, Any]) -> None:
    """This tests that we don't send messages to slack if we set the disabled flag to True."""
    from starfleet.utils.slack import SlackClient

    test_configuration["STARFLEET"]["SlackEnabled"] = False

    test_client = SlackClient(token="lolol")
    test_client.post_success("some_channel", "The Title!", "some _markdown_ text!")

    assert not test_client._web_client.chat_postMessage.called

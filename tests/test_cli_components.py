"""Tests for Starfleet's CLI components

Verifies that the CLI components are functioning properly.

:Module: starfleet.tests.test_cli_components
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, Dict

# pylint: disable=unused-argument
import click
from click.testing import CliRunner

from starfleet.cli.components import StarfleetCliLoader, StarfleetClickGroup
from starfleet.worker_ships.loader import StarfleetWorkerShipLoader


def test_cli_startup(test_worker_ship_loader: StarfleetWorkerShipLoader, test_cli_loader: StarfleetCliLoader, test_configuration: Dict[str, Any]) -> None:
    """This tests the main CLI startup entrypoint to load the testing worker ships.

    This also tests most of the CLI loader at the same time.
    """
    runner = CliRunner()

    assert test_configuration["STARFLEET"]["SlackEnabled"]  # This should be set to enabled before the CLI runs.

    # This needs to be defined here to guarantee that the main worker ship and CLI loading doesn't take place prior to mocking
    # (need to mock out both before this loads):
    @click.group(cls=StarfleetClickGroup)
    def cli_group_testing() -> None:
        """A CLI group for testing"""

    result = runner.invoke(cli_group_testing)  # noqa
    assert result.exit_code == 0

    # After the CLI runs we should not have Slack enabled:
    assert not test_configuration["STARFLEET"]["SlackEnabled"]

    assert len(cli_group_testing.commands["testing-plugin"].commands) == 2  # noqa
    assert len(cli_group_testing.commands["testing-plugin-group-two"].commands) == 2  # noqa
    assert cli_group_testing.commands["testing-plugin"].commands["test-command-one"]  # noqa
    assert cli_group_testing.commands["testing-plugin"].commands["test-command-two"]  # noqa
    assert cli_group_testing.commands["testing-plugin-group-two"].commands["group-two-command-one"]  # noqa
    assert cli_group_testing.commands["testing-plugin-group-two"].commands["group-two-command-two"]  # noqa


def test_main_cli() -> None:
    """This tests that the main CLI can load successfully."""
    from starfleet.cli.entrypoint import cli

    runner = CliRunner()
    result = runner.invoke(cli)  # noqa
    assert result.exit_code == 0
    assert "Starfleet is a totally awesome whole-infrastructure automation tool." in result.output

    # Not testing the loaded plugins since that will depend on what is or is not enabled in the configuration.

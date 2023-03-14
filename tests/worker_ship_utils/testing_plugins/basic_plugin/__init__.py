"""A sample worker plugin.

Sample worker plugin for unit testing purposes.

:Module: starfleet.tests.worker_ship_utils.testing_plugins.basic_plugin
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import click

from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip, WorkerShipBaseConfigurationTemplate
from starfleet.worker_ships.base_payload_schemas import WorkerShipPayloadBaseTemplate


@click.group()
def testing_plugin() -> None:
    """This is the main group for testing the logic for the test plugin."""


@testing_plugin.command()
def test_command_one():
    """Command to test CLIs"""


@testing_plugin.command()
def test_command_two():
    """Command to test CLIs"""


@click.group()
def testing_plugin_group_two() -> None:
    """This is a second group for testing the logic for the test plugin."""


@testing_plugin_group_two.command()
def group_two_command_one():
    """Command to test CLIs"""


@testing_plugin_group_two.command()
def group_two_command_two():
    """Command to test CLIs"""


class TestingStarfleetWorkerPlugin(StarfleetWorkerShip):
    """Testing Starfleet worker plugin."""

    worker_ship_name = "TestingStarfleetWorkerPlugin"
    configuration_template_class = WorkerShipBaseConfigurationTemplate
    payload_template_class = WorkerShipPayloadBaseTemplate

    def execute(self, commit: bool = False) -> None:
        """This will execute the job from the payload."""
        raise NotImplementedError("pew pew pew")  # pragma: no cover


class TestingStarfleetWorkerPluginTwo(TestingStarfleetWorkerPlugin):
    """A second testing Starfleet worker plugin."""

    def execute(self, commit: bool = False) -> None:
        """This will execute the job from the payload."""
        raise NotImplementedError("pew pew pew")  # pragma: no cover

    worker_ship_name = "TestingStarfleetWorkerPluginTwo"


class TestingStarfleetWorkerPluginThree(TestingStarfleetWorkerPlugin):
    """A second testing Starfleet worker plugin."""

    worker_ship_name = "TestingStarfleetWorkerPluginThree"

    def execute(self, commit: bool = False) -> None:
        """This will execute the job from the payload."""
        raise NotImplementedError("pew pew pew")  # pragma: no cover


WORKER_SHIP_PLUGINS = [TestingStarfleetWorkerPlugin, TestingStarfleetWorkerPluginTwo, TestingStarfleetWorkerPluginThree]
CLICK_CLI_GROUPS = [testing_plugin, testing_plugin_group_two]

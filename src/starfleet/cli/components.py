"""Components for the CLI to make it function properly.

These are pulled out here to make it easy to test and avoid circular dependencies.

:Module: starfleet.cli.components
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Any, List

import click

import starfleet.worker_ships.plugins
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.worker_ships.loader import STARFLEET_WORKER_SHIPS
from starfleet.startup import base_start_up
from starfleet.utils.logging import LOGGER
from starfleet.utils.plugin_loader import find_plugins


LOGO = """
                _/                              _/_/  _/                        _/
     _/_/_/  _/_/_/_/    _/_/_/  _/  _/_/    _/      _/    _/_/      _/_/    _/_/_/_/
  _/_/        _/      _/    _/  _/_/      _/_/_/_/  _/  _/_/_/_/  _/_/_/_/    _/
     _/_/    _/      _/    _/  _/          _/      _/  _/        _/          _/
_/_/_/        _/_/    _/_/_/  _/          _/      _/    _/_/_/    _/_/_/      _/_/
"""


class StarfleetCliLoader:
    """This will locate all the CLIs."""

    # These are defined here for easy testability -- this is the same path to the worker ships:
    _worker_ship_path: str = starfleet.worker_ships.plugins.__path__
    _worker_ship_prefix: str = starfleet.worker_ships.plugins.__name__ + "."

    def __init__(self):
        self._clis: List[click.Group] = None  # noqa

    def load_clis(self):
        """This will load all Starfleet worker ship plugins and verify that they are set up properly. This is code that will mostly be used by both the
        Starbase and the CLI."""
        LOGGER.debug("[🖥️] Loading CLIs (which are just plugins)...")
        self._clis = []
        for _, cli_list in find_plugins(self._worker_ship_path, self._worker_ship_prefix, "CLICK_CLI_GROUPS", click.Group, verify_class=False).items():
            # Avoid too much debug output here...
            self._clis.extend(cli_list)
        LOGGER.debug(f"[🖥️] Completed loading {len(self._clis)} CLIs")

    @property
    def clis(self) -> List[click.Group]:
        """Gets the CLIs and lazy-loads them if not already set."""
        if self._clis is None:
            self.load_clis()

        return self._clis


STARFLEET_CLI_LOADER = StarfleetCliLoader()  # Not really needed to be defined here, but it makes unit testing 1000x easier.


class StarfleetClickGroup(click.Group):
    """The Starfleet Click Group. This is here to print the logo :D"""

    def __init__(self, **attrs: Any):
        super().__init__(**attrs)

        # Print out the awesome logo:
        click.echo(LOGO)

        # Base start up:
        base_start_up()

        # Load the worker ships (makes sure everything is all good):
        STARFLEET_WORKER_SHIPS.get_worker_ships()

        # Disable Slack alerts:
        STARFLEET_CONFIGURATION.config["STARFLEET"]["SlackEnabled"] = False

        # Load up the CLIs:
        for command in STARFLEET_CLI_LOADER.clis:
            self.add_command(command)

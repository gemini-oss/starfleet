"""The main CLI entrypoint for Starfleet.

This outlines the main CLI entrypoint objects that are to be used throughout.

:Module: starfleet.cli.entrypoint
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

import click

from starfleet.cli.components import StarfleetClickGroup


@click.group(cls=StarfleetClickGroup)
def cli() -> None:
    """Starfleet is a totally awesome whole-infrastructure automation tool."""

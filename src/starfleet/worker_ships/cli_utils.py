"""Starfleet's worker "ship" CLI utility functions

This contains utility functions for CLIs that make it easier to do things that need to be done.

:Module: starfleet.worker_ships.cli_utils
:Copyright: (c) 2022 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from io import TextIOWrapper
from typing import Dict, Any

import click
import yaml
from click import Context, Option, ClickException


def load_payload(ctx: Context, param: Option, value: TextIOWrapper) -> Dict[str, Any]:  # pylint: disable=W0613  # noqa
    """This is a utility function that will attempt to load the payload template YAML file. This is used as a click callback like so:

           @click.group()
           def some_worker_ship() -> None:
               pass

           @some_worker_ship.command()
           @click.option("--payload", required=True, type=click.File("r"), callback=load_payload) # <--- This is it!
           def some_template_command(template: Dict[str, Any]) -> None:
               # Do your own validation here for the template that is loaded with this function!

    NOTE: This will not perform the validation for the worker template! It was "too hard" to figure out a good
    way to do that, so instead I'm doing it the lazy way and forcing developers to just copy and paste code :P
    """
    try:
        loaded = yaml.safe_load(value.read())
        if not loaded:
            raise ClickException("[💥] The loaded YAML is EMPTY!!")

        return loaded

    except Exception as exc:
        click.echo("[💥] Problem loading the YAML template. See the stacktrace below!", err=True)
        raise exc

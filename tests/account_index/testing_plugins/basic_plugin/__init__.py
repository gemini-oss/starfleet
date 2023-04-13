"""A sample account index plugin used for unit testing

Sample account index plugin for unit testing purposes.

:Module: starfleet.tests.account_index.testing_plugins.basic_plugin
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
from typing import Dict, Set

from starfleet.account_index.plugins.starfleet_default_index import StarfleetDefaultAccountIndex
import tests.starfleet_included_plugins.account_index_generator


class TestingAccountIndexPlugin(StarfleetDefaultAccountIndex):
    """This is mostly a clone of the StarfleetDefaultAccountIndex, but slimmed down specifically for unit testing the Starbase."""

    # Intentionally not calling the super __init__ in this function (to not reach out to S3):
    def __init__(self):  # noqa pylint: disable=super-init-not-called
        """This will load the generatedIndex.json file that is used by the tests.starfleet_included_plugins.account_index_generator tests."""
        self.account_ids = set()
        self.alias_map: Dict[str, str] = {}
        self.ou_map: Dict[str, Set[str]] = {}
        self.regions_map: Dict[str, Set[str]] = {}
        self.tag_map: Dict[str, Dict[str, Set[str]]] = {}  # Dict of tag name -> tag value -> accounts

        path = f"{tests.starfleet_included_plugins.account_index_generator.__path__[0]}/generatedIndex.json"
        with open(path, "r", encoding="utf-8") as file:
            account_dict = json.loads(file.read())["accounts"]

        self._load_inventory(account_dict)


ACCOUNT_INDEX_PLUGINS = [TestingAccountIndexPlugin]

"""A sample account index plugin used for unit testing

Sample account index plugin for unit testing purposes.

:Module: starfleet.tests.account_index.testing_plugins.basic_plugin
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import json
import warnings
from typing import Dict, Set

from starfleet.account_index.plugins.starfleet_default_index import StarfleetDefaultAccountIndex
from starfleet.utils.niceties import get_all_regions

import tests.starfleet_included_plugins.account_index_generator


class TestingAccountIndexPlugin(StarfleetDefaultAccountIndex):
    """This is mostly a clone of the StarfleetDefaultAccountIndex, but slimmed down specifically for unit testing the Starbase."""

    # Intentionally not calling the super __init__ in this function (to not reach out to S3):
    def __init__(self):  # noqa pylint: disable=super-init-not-called
        """This will load the generatedIndex.json file that is used by the tests.starfleet_included_plugins.account_index_generator tests."""
        self.account_ids = set()
        self.alias_map: Dict[str, str] = {}
        self.account_name_map: Dict[str, str] = {}
        self.ou_map: Dict[str, Set[str]] = {}
        self.regions_map: Dict[str, Set[str]] = {}
        self.tag_map: Dict[str, Dict[str, Set[str]]] = {}  # Dict of tag name -> tag value -> accounts
        self.account_tag_map: Dict[str, Dict[str, str]] = {}  # Dict of account ID -> tag dictionary

        path = f"{tests.starfleet_included_plugins.account_index_generator.__path__[0]}/generatedIndex.json"
        with open(path, "r", encoding="utf-8") as file:
            account_dict = json.loads(file.read())["accounts"]

        # NOTE: Boto updates will change the supported regions for accounts. If we detect that the regions in the loaded index file are not the same as what boto3 now supports,
        # then we will override what is in the JSON with whatever the latest regions supported by boto3 to prevent tests from breaking
        # However, we will issue a warning if we detect this as it's not ideal to have the loaded tests not use the raw values from the file.
        all_regions = sorted(get_all_regions())
        append_regions = []

        for region in all_regions:
            if region not in account_dict["000000000001"]["Regions"]:
                append_regions.append(region)

        # If we have found missing regions, then boto3 was updated with new regions that are not present in the account index.
        if append_regions:
            corrected_regions = sorted(account_dict["000000000001"]["Regions"] + append_regions)

            warnings.warn(
                "[⚠️] Note: boto3 was updated and the generated index: `tests/starfleet_included_plugins/account_index_generator/generatedIndex.json` has an outdated list of "
                "regions. Please update the generatedIndex.json file by following the instructions on this file (the one that emitted this warning)."
            )

            # Instructions:
            # To update the generatedIndex.json file, you need to go to: src/starfleet/worker_ships/plugins/account_index_generator/ship.py,
            # and at the bottom of the `AccountIndexGeneratorShip` class, there is code you need to uncomment (these instructions are there as well). You have to run the unit tests
            # for the account index generator worker with those lines of code uncommented, and then clone over
            # that file to 'tests/starfleet_included_plugins/account_index_generator/generatedIndex.json'. Once finished, remember to re-comment out those lines.

            for account in account_dict.values():
                account["Regions"] = corrected_regions

        self._load_inventory(account_dict)


ACCOUNT_INDEX_PLUGINS = [TestingAccountIndexPlugin]

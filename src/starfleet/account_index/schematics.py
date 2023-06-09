"""Definitions for Account Index plugins.

This defines what is required for making an Account Index. The Account Index is a special plugin that is used by Starfleet to know which accounts are where.
This is what allows the Starbase to properly task Account and Account-Region payloads.

:Module: starfleet.account_index.schematics
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Set, Dict, Optional, TypeVar


class AccountIndex:  # pragma: no cover
    """
    This is the base class that ALL account index plugins in Starfleet need to subclass.

    Make sure that you put your boostrapping code in the __init__ function. That is where you will want to do things like load the configuration, or load up the index.
    """

    def get_accounts_by_ids(self, ids: Set[str]) -> Set[str]:
        """Return back a Set of account IDs for a given set of IDs present -- this effectively only returns back account IDs that exist in the inventory."""
        raise NotImplementedError("Pew Pew Pew")

    def get_accounts_by_aliases(self, aliases: Set[str]) -> Set[str]:
        """Return back a Set of account IDs for a given set of aliases"""
        raise NotImplementedError("Pew Pew Pew")

    def get_accounts_by_tag(self, tag_name: str, tag_value: str) -> Set[str]:
        """Return back a set of account IDs based on the tag name and value pair"""
        raise NotImplementedError("Pew Pew Pew")

    def get_accounts_by_ou(self, org_unit: str) -> Set[str]:
        """Return back a set of account IDs based on the OU membership"""
        raise NotImplementedError("Pew Pew Pew")

    def get_accounts_by_regions(self, regions: Set[str]) -> Dict[str, Set[str]]:
        """Return back a dictionary of the region and the set of accounts associated with it."""
        raise NotImplementedError("Pew Pew Pew")

    def get_accounts_for_all_regions(self) -> Dict[str, Set[str]]:
        """Return back a dictionary of the region and the set of all accounts associated with it -- but for ALL regions."""
        raise NotImplementedError("Pew Pew Pew")

    def get_all_accounts(self) -> Set[str]:
        """Return back a set of all account IDs."""
        raise NotImplementedError("Pew Pew Pew")

    def get_org_roots(self) -> Set[str]:
        """
        Return back the set of account IDs for Organization Root accounts. This is mostly used for the Account and Account/Region worker ships when specifying if the payload
        in question should operate in an AWS Organization Root account. If the flag in the template is set, then this will check if there is an Organization Root set and task a
        worker ship with the payload to operate in that corresponding organization root.

        Note: The typical and preferred implementation for Starfleet is to operate on 1 AWS Organization, however, there is no reason why it can't operate over many.
        If you only have 1 org, just return the one account that is the org root account.
        """
        raise NotImplementedError("Pew Pew Pew")

    def get_account_names(self, account_ids: Set[str]) -> Dict[str, Optional[str]]:
        """Return back a mapping of account id to account name for the given set of account IDs. If the account ID is not found, it's mapped value is None."""
        raise NotImplementedError("Pew Pew Pew")


AccountIndexInstance = TypeVar("AccountIndexInstance", bound=AccountIndex)

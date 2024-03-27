"""Account Resolution Logic

This defines the account resolution logic for account and account/region templates.

:Module: starfleet.account_index.resolvers
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from typing import Any, Dict, Set

from starfleet.account_index.loader import ACCOUNT_INDEX
from starfleet.utils.configuration import STARFLEET_CONFIGURATION
from starfleet.utils.logging import LOGGER


def resolve_worker_template_accounts(loaded_template: Dict[str, Any]) -> Set[str]:
    """
    This will resolve the accounts that a given worker template is supposed to operate on. This receives a deserialized dictionary that was based on the
    `starfleet.worker_ships.base_payload_schemas.BaseAccountPayloadTemplate` (or a subclass or equivalent).
    """
    # Get the accounts:
    resolved_accounts = resolve_include_exclude(loaded_template)

    # If we are NOT set to operate in the org root, then we need to remove org roots from the set if they are present:
    if not loaded_template["operate_in_org_root"]:
        # Get the org roots:
        org_roots = ACCOUNT_INDEX.index.get_org_roots()

        return resolved_accounts - org_roots

    return resolved_accounts


def resolve_worker_template_account_regions(loaded_template: Dict[str, Any], org_root_check: bool = True) -> Dict[str, Set[str]]:
    """
    This will resolve the accounts/regions that a given worker template is supposed to operate on. This receives a deserialized dictionary that was based on the
    `starfleet.worker_ships.base_payload_schemas.BaseAccountRegionPayloadTemplate` (or a subclass or equivalent).

    This will return a Dictionary of the account ID and set of regions to operate over.

    This is scoped to the `STARFLEET` configuration value for `ScopeToRegions`. If that is set, then that is the maximum list of regions that can be tasked.

    There is an optional parameter called `org_root_check`. This is a boolean that is default True. This is an optional if you want to use this function in
    a worker where you define a similar config to the BaseAccountRegionPayloadTemplate, but don't have a need for root checking. The AWS Config worker ship is an
    example of this.
    """
    # Get the accounts:
    if org_root_check:
        resolved_accounts = resolve_worker_template_accounts(loaded_template)
    else:
        resolved_accounts = resolve_include_exclude(loaded_template)

    # Grab the requested regions:
    excluded_regions = loaded_template["exclude_regions"] if loaded_template["exclude_regions"] else set()
    resolved_regions = loaded_template["include_regions"] - excluded_regions

    # Build the account/region map:
    account_region_map = {}

    # If a scope is applied in the `STARFLEET` configuration's `ScopeToRegions` variable, then apply the scoping:
    scoped_regions = set(STARFLEET_CONFIGURATION.config["STARFLEET"].get("ScopeToRegions", []))
    if scoped_regions:
        LOGGER.debug(f"[🌐] Region scoping is enabled to only task within the following regions: {', '.join(scoped_regions)}")
        regions_accounts_map = {}
        # Fetch the region->accounts mapping, but we are only going to process them if it's permitted in the scope:
        for region, accounts in ACCOUNT_INDEX.index.get_accounts_by_regions(resolved_regions).items():
            if region in scoped_regions:
                regions_accounts_map[region] = accounts

    # No scoping is set, so just use the raw index results:
    else:
        regions_accounts_map = ACCOUNT_INDEX.index.get_accounts_by_regions(resolved_regions)

    # Build the map account->regions map if the account is enabled for the region (and the region is specified in the template):
    for account in resolved_accounts:
        account_region_map[account] = set()
        for region, region_accounts in regions_accounts_map.items():
            if account in region_accounts:
                account_region_map[account].add(region)

    return account_region_map


def resolve_include_exclude(loaded_template: Dict[str, Any]) -> Set[str]:
    """
    This will resolve accounts that are included and excluded. This will return a set of accounts that are effectively included (sans the excluded accounts).
    This receives a deserialized dictionary that was based on the `starfleet.worker_ships.base_payload_schemas.BaseAccountPayloadTemplate` (or a subclass or equivalent).
    """
    included_accounts = resolve_include_account_specification(loaded_template["include_accounts"])
    excluded_accounts = resolve_account_specification(loaded_template["exclude_accounts"]) if loaded_template["exclude_accounts"] else set()

    # Subtract:
    return included_accounts - excluded_accounts


def resolve_account_specification(account_spec: Dict[str, Any]) -> Set[str]:
    """
    This will receive a dictionary that is based on the `starfleet.worker_ships.base_payload_schemas.AccountsSpecificationSchema` (or a subclass or equivalent)
    AND has already been deserialized.

    This will go through each account portion and return a giant set of each account in there.
    """
    account_set = set()

    # Load accounts by Account ID:
    account_set.update(ACCOUNT_INDEX.index.get_accounts_by_ids(set(account_spec["by_ids"])))

    # Load accounts by Account Names or Aliases:
    account_set.update(ACCOUNT_INDEX.index.get_accounts_by_aliases(set(account_spec["by_names"])))

    # Load accounts by Organization Units:
    for org_unit in set(account_spec["by_org_units"]):
        account_set.update(ACCOUNT_INDEX.index.get_accounts_by_ou(org_unit))

    # Load accounts by Tag Name/Value pair:
    for tag in account_spec["by_tags"]:
        account_set.update(ACCOUNT_INDEX.index.get_accounts_by_tag(tag["name"], tag["value"]))

    return account_set


def resolve_include_account_specification(include_account_spec: Dict[str, Any]) -> Set[str]:
    """
    This is exactly like the `resolve_account_specification` but this one handles the `IncludeAccounts` portion of the template. This basically calls out to the
    `resolve_account_specification` function above while also performing the `AllAccounts: True` logic.
    """
    if include_account_spec["all_accounts"]:
        return ACCOUNT_INDEX.index.get_all_accounts()

    return resolve_account_specification(include_account_spec)

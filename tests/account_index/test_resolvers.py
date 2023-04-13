"""Tests for the account resolution logic

This tests the account resolution logic where based on the template provided, it will return back the set of accounts that the template is supposed to apply to.

:Module: starfleet.tests.account_index.test_resolvers
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
from typing import Any, Dict

import boto3
import yaml

from starfleet.account_index.schematics import AccountIndexInstance


def test_resolve_include_account_specification(test_index: AccountIndexInstance) -> None:
    """This tests the inclusion logic and also resolve_account_specification."""
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate
    from starfleet.account_index.resolvers import resolve_include_account_specification

    payload = """
        TemplateName: SomeAccounts
        TemplateDescription: A proper payload that is able to fetch some accounts
        IncludeAccounts:
            ByIds:
                 - "000000000018"
                 - "000000000017"
            ByNames:
                - Account 1
                - Account 2
                - Account 18
    """

    template = BaseAccountPayloadTemplate().load(yaml.safe_load(payload))
    assert resolve_include_account_specification(template["include_accounts"]) == {"000000000001", "000000000002", "000000000017", "000000000018"}

    # The rest will just return all the accounts since all the accounts are tagged the same way.
    # We want to test iterations where possible and all the combinations to ensure that we get the exact same results.
    results = {}

    # Tags:
    template["include_accounts"]["by_tags"] = [{"name": "Key1", "value": "Value1"}, {"name": "Key2", "value": "Value2"}, {"name": "Key3", "value": "Value3"}]
    results["tag_loop"] = resolve_include_account_specification(template["include_accounts"])
    for number in range(1, 4):
        template["include_accounts"]["by_tags"] = [{"name": f"Key{number}", "value": f"Value{number}"}]
        results[f"tag_key_{number}"] = resolve_include_account_specification(template["include_accounts"])

    # Root Parent:
    template["include_accounts"] = {
        "all_accounts": False,
        "by_ids": [],
        "by_names": [],
        "by_tags": [],
        "by_org_units": ["ROOT", "SomeOU", "r-123456", "ou-1234-5678910"],
    }
    results["ou_loop"] = resolve_include_account_specification(template["include_accounts"])
    for org_unit in ["ROOT", "r-123456"]:
        template["include_accounts"] = {"all_accounts": False, "by_ids": [], "by_names": [], "by_tags": [], "by_org_units": [org_unit]}
        results[f"ou_key_{org_unit}"] = resolve_include_account_specification(template["include_accounts"])

    # All:
    template["include_accounts"]["all_accounts"] = True
    all_accounts = resolve_include_account_specification(template["include_accounts"])

    # Verify:
    assert test_index.get_all_accounts() == all_accounts
    for value in results.values():
        assert all_accounts == value

    # Lastly, check out the non-root OU since that will lack the org root ID (Account 20):
    for org_unit in ["SomeOU", "ou-1234-5678910"]:
        template["include_accounts"] = {"all_accounts": False, "by_ids": [], "by_names": [], "by_tags": [], "by_org_units": [org_unit]}
        result = resolve_include_account_specification(template["include_accounts"])
        assert "000000000020" not in result
        assert len(result) == len(all_accounts) - 1


def test_resolve_include_exclude(test_index: AccountIndexInstance) -> None:
    """This tests the inclusion logic and also resolve_account_specification."""
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate
    from starfleet.account_index.resolvers import resolve_include_exclude

    payload = """
        TemplateName: SomeAccounts
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByIds:
                 - "000000000018"
                 - "000000000017"
            ByNames:
                - Account 1
                - Account 2
                - Account 18
        ExcludeAccounts:
            ByNames:
                - Account 1
                - Account 18
    """

    template = BaseAccountPayloadTemplate().load(yaml.safe_load(payload))
    assert resolve_include_exclude(template) == {"000000000002", "000000000017"}

    # Let's try something fun, like all accounts and removal of SomeOU:
    payload = """
        TemplateName: JustOneAccount
        TemplateDescription: Only 1 account - the org root - should be left over
        IncludeAccounts:
            AllAccounts: True
        ExcludeAccounts:
            ByOrgUnits:
                - SomeOU
    """
    template = BaseAccountPayloadTemplate().load(yaml.safe_load(payload))
    assert resolve_include_exclude(template) == {"000000000020"}


def test_resolve_worker_template_accounts(test_index: AccountIndexInstance) -> None:
    """This tests the worker template logic for resolving accounts and verifies that the org root logic works properly."""
    from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate
    from starfleet.account_index.resolvers import resolve_worker_template_accounts

    payload = """
        TemplateName: SomeAccounts
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByIds:
                 - "000000000018"
                 - "000000000017"
            ByNames:
                - Account 1
                - Account 2
                - Account 18
                - Account 20
        ExcludeAccounts:
            ByNames:
                - Account 1
                - Account 18
        OperateInOrgRoot: True
    """

    # This will test that this operates in the org root:
    template = BaseAccountPayloadTemplate().load(yaml.safe_load(payload))
    assert resolve_worker_template_accounts(template) == {"000000000002", "000000000017", "000000000020"}

    # Set the org root value to false:
    template["operate_in_org_root"] = False
    assert resolve_worker_template_accounts(template) == {"000000000002", "000000000017"}

    # Let's try something fun, like all accounts but not the org root via the flag not being set:
    payload = """
        TemplateName: NotOrgRoot
        TemplateDescription: All accounts except the org root
        IncludeAccounts:
            AllAccounts: True
    """
    template = BaseAccountPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_accounts(template)
    assert "000000000020" not in result
    assert len(result) == len(test_index.get_all_accounts()) - 1

    # ... and with it set:
    template["operate_in_org_root"] = True
    result = resolve_worker_template_accounts(template)
    assert "000000000020" in result
    assert result == test_index.get_all_accounts()


def test_resolve_worker_templates_disabled_regions(test_index: AccountIndexInstance, test_configuration: Dict[str, Any]) -> None:
    """This tests if we do not task for an account with a region disabled."""
    from starfleet.worker_ships.base_payload_schemas import BaseAccountRegionPayloadTemplate
    from starfleet.account_index.resolvers import resolve_worker_template_account_regions

    all_regions = set(boto3.session.Session().get_available_regions("ec2"))

    # Disable in 2 accounts:
    test_index.regions_map["ap-east-1"].remove("000000000001")
    test_index.regions_map["ap-east-1"].remove("000000000002")

    payload = """
        TemplateName: SomeAccountsAllRegions
        TemplateDescription: A proper payload that should task for all regions except the ones that are disabled.
        IncludeAccounts:
            ByNames:
                - Account 1
                - Account 2
                - Account 3
                - Account 4
        IncludeRegions:
            - ALL
    """
    template = BaseAccountRegionPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_account_regions(template)
    sans_ap_east_1 = set(boto3.session.Session().get_available_regions("ec2"))
    sans_ap_east_1.remove("ap-east-1")
    assert all_regions - sans_ap_east_1 == {"ap-east-1"}
    assert result == {"000000000001": sans_ap_east_1, "000000000002": sans_ap_east_1, "000000000003": all_regions, "000000000004": all_regions}


def test_resolve_worker_templates_account_regions(test_index: AccountIndexInstance, test_configuration: Dict[str, Any]) -> None:
    """This tests the Account/Region template for account and region resolution."""
    from starfleet.worker_ships.base_payload_schemas import BaseAccountRegionPayloadTemplate
    from starfleet.account_index.resolvers import resolve_worker_template_account_regions

    all_regions = set(boto3.session.Session().get_available_regions("ec2"))

    # This will test the "all regions" logic and some account exclusion and org root support:
    payload = """
        TemplateName: SomeAccountsAllRegions
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByNames:
                - Account 1
                - Account 2
                - Account 18
                - Account 20
        ExcludeAccounts:
            ByNames:
                - Account 1
        IncludeRegions:
            - ALL
        OperateInOrgRoot: True
    """
    template = BaseAccountRegionPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_account_regions(template)
    assert result == {"000000000002": all_regions, "000000000018": all_regions, "000000000020": all_regions}

    # Test the above but with the flag to disable the root org checking:
    payload = """
        TemplateName: SomeAccountsAllRegions
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByNames:
                - Account 1
                - Account 2
                - Account 18
                - Account 20
        ExcludeAccounts:
            ByNames:
                - Account 1
        IncludeRegions:
            - ALL
    """
    template = BaseAccountRegionPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_account_regions(template, org_root_check=False)
    assert result == {"000000000002": all_regions, "000000000018": all_regions, "000000000020": all_regions}

    # With some excluded regions:
    payload = """
        TemplateName: SomeAccountsAllRegions
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByNames:
                - Account 1
                - Account 2
        IncludeRegions:
            - us-east-1
            - us-east-2
            - us-west-1
        ExcludeRegions:
            - us-west-1
    """
    template = BaseAccountRegionPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_account_regions(template)
    assert result == {"000000000001": {"us-east-1", "us-east-2"}, "000000000002": {"us-east-1", "us-east-2"}}

    # By scoping the regions:
    test_configuration["STARFLEET"]["ScopeToRegions"] = ["us-east-2", "eu-west-1"]
    payload = """
        TemplateName: SomeAccountsAllRegions
        TemplateDescription: A proper payload that is able to fetch some accounts with some excluded
        IncludeAccounts:
            ByNames:
                - Account 1
                - Account 2
        IncludeRegions:
            - ALL
    """
    template = BaseAccountRegionPayloadTemplate().load(yaml.safe_load(payload))
    result = resolve_worker_template_account_regions(template)
    assert result == {"000000000001": {"us-east-2", "eu-west-1"}, "000000000002": {"us-east-2", "eu-west-1"}}

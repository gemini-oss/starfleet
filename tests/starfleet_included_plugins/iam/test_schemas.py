"""Tests for the IAM worker schemas

All the tests for schemas on the IAM workers.

:Module: starfleet.tests.starfleet_included_plugins.iam.test_schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""

from unittest import mock

import pytest
import yaml

from iambic.plugins.v0_1_0.aws.iam.role.models import AwsIamRoleTemplate
from marshmallow import ValidationError

from starfleet.account_index.schematics import AccountIndexInstance


def test_render_normal_schema() -> None:
    """This tests rendering a 'normal' schema without any special stanzas."""
    from starfleet.worker_ships.plugins.iam.schemas import IambicTemplateTypes, IamRoleWorkerShipPayloadTemplate, render_iambic_template

    payload = """
        TemplateName: NormalRoleTemplate
        TemplateDescription: This is a normal IAM role template
        IncludeAccounts:
          AllAccounts: True
        IambicRoleTemplate:
          properties:
            description: Some normal IAM role
            assume_role_policy_document:
              statement:
                - action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
              - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-normal-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """

    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))

    # Verify that we can properly render it:
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)

    # Assert we do in fact have a copy:
    assert schema["iambic_role_template"] != rendered_template

    should_equal = {
        "template_type": "NOQ::AWS::IAM::Role",
        "identifier": "NormalRoleTemplate",
        "iambic_managed": "enforced",
        "properties": schema["iambic_role_template"]["properties"],
        "file_path": "Starfleet",
    }
    assert rendered_template == should_equal

    # Make sure iambic is happy:
    AwsIamRoleTemplate.update_forward_refs()
    assert AwsIamRoleTemplate(**rendered_template)

    # Try it again with commit set to False:
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, False)
    assert rendered_template["iambic_managed"] == "import_only"
    should_equal.pop("iambic_managed")
    rendered_template.pop("iambic_managed")
    assert should_equal == rendered_template


def test_top_level_forbidden_fields() -> None:
    """This tests that the forbidden fields are not present in the top-level of the embedded iambic schema."""
    from starfleet.worker_ships.plugins.iam.schemas import IambicTemplateTypes, IamRoleWorkerShipPayloadTemplate, render_iambic_template

    payload = """
        TemplateName: BadTemplate
        TemplateDescription: This is a bad template
        IncludeAccounts:
          AllAccounts: True
        IambicRoleTemplate:
          StarfleetIncludeAccounts:
            AllAccounts: True
          StarfleetExcludeAccounts:
            ByNames:
              - "Account 1"
          included_accounts:
            - '*'
          excluded_accounts:
            - 'Account 1'
          included_orgs:
            - "org 1"
          excluded_orgs:
            - "org 2"
          IncludeAccounts:
            AllAccounts: True
          ExcludeAccounts:
            ByNames:
              - "Account 1"
          iambic_managed: enforced
          properties:
            description: Some bad IAM role
            assume_role_policy_document:
              statement:
                - action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
              - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-bad-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """
    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))

    # We are going to keep going and pop off one of the offending fields as we go along. We should get an exception for each one:
    forbidden_fields = {
        "StarfleetIncludeAccounts",
        "StarfleetExcludeAccounts",
        "included_accounts",
        "excluded_accounts",
        "included_orgs",
        "excluded_orgs",
        "IncludeAccounts",
        "ExcludeAccounts",
        "iambic_managed",
    }
    found_forbidden = set()
    for _ in forbidden_fields:
        with pytest.raises(ValidationError) as verr:
            render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)

        forbidden_field = verr.value.messages[0].split("Found forbidden top-level key: ")[1].split(" in the")[0]
        found_forbidden.add(forbidden_field)
        schema["iambic_role_template"].pop(forbidden_field)

    assert found_forbidden == forbidden_fields

    # All the top-level forbidden fields should be removed:
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    AwsIamRoleTemplate.update_forward_refs()
    assert AwsIamRoleTemplate(**rendered_template)


def test_nested_forbidden_fields() -> None:
    """This tests that we properly handle nested forbidden fields."""
    from starfleet.worker_ships.plugins.iam.schemas import IambicTemplateTypes, IamRoleWorkerShipPayloadTemplate, render_iambic_template

    payload = """
        TemplateName: BadTemplate
        TemplateDescription: This is a bad template
        IncludeAccounts:
          AllAccounts: True
        IambicRoleTemplate:
          properties:
            description: Some bad IAM role
            assume_role_policy_document:
              statement:
                - included_accounts:
                    - '*'
                  excluded_accounts:
                    - 'Account 1'
                  included_orgs:
                    - "org 1"
                  excluded_orgs:
                    - "org 2"
                  action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
              - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-bad-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """
    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))
    # We are going to keep going and pop off one of the offending fields as we go along. We should get an exception for each one:
    forbidden_fields = {"included_accounts", "excluded_accounts", "included_orgs", "excluded_orgs"}
    found_forbidden = set()
    for _ in forbidden_fields:
        with pytest.raises(ValidationError) as verr:
            render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)

        forbidden_field = verr.value.messages[0].split("Found forbidden key: ")[1].split(" in the")[0]
        found_forbidden.add(forbidden_field)
        schema["iambic_role_template"]["properties"]["assume_role_policy_document"]["statement"][0].pop(forbidden_field)

    assert found_forbidden == forbidden_fields

    # All the forbidden fields should be removed:
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    AwsIamRoleTemplate.update_forward_refs()
    assert AwsIamRoleTemplate(**rendered_template)


def test_include_exclude_account_logic(test_index: AccountIndexInstance) -> None:
    """This tests that the nested include/exclude account logic is working properly."""
    # pylint: disable=no-member
    from starfleet.worker_ships.plugins.iam.schemas import IambicTemplateTypes, IamRoleWorkerShipPayloadTemplate, render_iambic_template

    payload = """
        TemplateName: Account restricted role
        TemplateDescription: This is an account restricted role
        IncludeAccounts:
          AllAccounts: True
        IambicRoleTemplate:
          properties:
            description: Some normal IAM role
            assume_role_policy_document:
              statement:
                - action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
              - StarfleetIncludeAccounts:
                  AllAccounts: True
                StarfleetExcludeAccounts:
                  ByNames:
                    - "Account 1"
                policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-normal-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """
    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    for starfleet_field in ["StarfleetIncludeAccounts", "StarfleetExcludeAccounts"]:
        assert starfleet_field not in rendered_template["properties"]["managed_policies"][0]

    # Verify that iambic got the include/exclude accounts passed into it:
    AwsIamRoleTemplate.update_forward_refs()
    iambic_rendered = AwsIamRoleTemplate(**rendered_template)
    assert iambic_rendered.properties.managed_policies[0].excluded_accounts == ["000000000001"]
    assert set(iambic_rendered.properties.managed_policies[0].included_accounts) == test_index.get_all_accounts()

    # Try this logic again with just account exclusion:
    schema["iambic_role_template"]["properties"]["managed_policies"][0].pop("StarfleetIncludeAccounts")
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    for starfleet_field in ["StarfleetIncludeAccounts", "StarfleetExcludeAccounts"]:
        assert starfleet_field not in rendered_template["properties"]["managed_policies"][0]

    # Verify that iambic got the include/exclude accounts passed into it:
    AwsIamRoleTemplate.update_forward_refs()
    iambic_rendered = AwsIamRoleTemplate(**rendered_template)
    assert iambic_rendered.properties.managed_policies[0].excluded_accounts == ["000000000001"]
    assert iambic_rendered.properties.managed_policies[0].included_accounts == ["*"]  # iambic places an ['*'] here when no include accounts are passed in

    # Try this logic again with just account inclusion:
    schema["iambic_role_template"]["properties"]["managed_policies"][0].pop("StarfleetExcludeAccounts")
    schema["iambic_role_template"]["properties"]["managed_policies"][0]["StarfleetIncludeAccounts"] = {"ByNames": ["Account 1", "Account 2"]}
    rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    for starfleet_field in ["StarfleetIncludeAccounts", "StarfleetExcludeAccounts"]:
        assert starfleet_field not in rendered_template["properties"]["managed_policies"][0]

    # Verify that iambic got the include/exclude accounts passed into it:
    AwsIamRoleTemplate.update_forward_refs()
    iambic_rendered = AwsIamRoleTemplate(**rendered_template)
    assert not iambic_rendered.properties.managed_policies[0].excluded_accounts
    assert set(iambic_rendered.properties.managed_policies[0].included_accounts) == {"000000000001", "000000000002"}

    # Try with no resolved accounts. This should log a warning and yield an empty list for the included/excluded accounts:
    schema["iambic_role_template"]["properties"]["managed_policies"][0]["StarfleetIncludeAccounts"] = {"ByNames": ["pewpewpew"]}
    schema["iambic_role_template"]["properties"]["managed_policies"][0]["StarfleetExcludeAccounts"] = {"ByNames": ["pewpewpew"]}
    with mock.patch("starfleet.worker_ships.plugins.iam.schemas.LOGGER") as mocked_logger:
        rendered_template = render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    for account_field in ["included_accounts", "excluded_accounts"]:
        assert not rendered_template["properties"]["managed_policies"][0][account_field]

    # Verify the emitted warning:
    warned_fields = {"StarfleetIncludeAccounts", "StarfleetExcludeAccounts"}
    found_fields = set()
    assert len(mocked_logger.warning.call_args_list) == len(warned_fields)
    for call in mocked_logger.warning.call_args_list:
        for field in warned_fields:
            if f"[❓] {field} did not resolve to any accounts in this stanza" in call[0][0]:
                found_fields.add(field)
    assert found_fields == warned_fields


def test_invalid_starfleet_include_exclude_schema() -> None:
    """This tests that we get errors if we misuse the StarfleetInclude/ExcludeAccounts schemas"""
    from starfleet.worker_ships.plugins.iam.schemas import IambicTemplateTypes, IamRoleWorkerShipPayloadTemplate, render_iambic_template

    payload = """
        TemplateName: Account restricted role
        TemplateDescription: This is an account restricted role
        IncludeAccounts:
          AllAccounts: True
        IambicRoleTemplate:
          properties:
            description: Some normal IAM role
            assume_role_policy_document:
              statement:
                - action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
              - StarfleetIncludeAccounts: {}
                StarfleetExcludeAccounts:
                  BySOMEFAKEFIELD:
                    - pew pew pew
                policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-normal-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """
    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))

    # Check that we get one of the expected errors:
    with pytest.raises(ValidationError) as verr:
        render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    assert "Missing an account field set." in verr.value.messages["ByIds"][0]

    # Now try with Exclude:
    schema["iambic_role_template"]["properties"]["managed_policies"][0].pop("StarfleetIncludeAccounts")
    with pytest.raises(ValidationError) as verr:
        render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    assert verr.value.messages["BySOMEFAKEFIELD"][0] == "Unknown field."

    # Let's test with an account field that is totally wrong:
    schema["iambic_role_template"]["properties"]["managed_policies"][0]["StarfleetExcludeAccounts"] = ["some", "value", "pewpewpew"]
    with pytest.raises(ValidationError) as verr:
        render_iambic_template(schema, IambicTemplateTypes.IAM_ROLE, True)
    assert verr.value.messages == {"StarfleetExcludeAccounts": ["Invalid input type."]}


def test_iambic_variables() -> None:
    """This tests that we also properly get the iambic variables"""
    from starfleet.worker_ships.plugins.iam.schemas import IamRoleWorkerShipPayloadTemplate, make_iambic_variables

    payload = """
        TemplateName: BadTemplate
        TemplateDescription: This is a bad template
        IncludeAccounts:
          AllAccounts: True
        IambicVariables:
            - Key: some-key
              Value: some-value
            - Key: some-other-key
              Value: some-other-value
        IambicRoleTemplate:
          properties:
            description: 'Some normal IAM role with a variable: {{ var.some-key }}'
            assume_role_policy_document:
              statement:
                - action:
                    - sts:AssumeRole
                    - sts:TagSession
                  effect: Allow
                  principal:
                    aws: arn:aws:iam::012345678910:role/some-other-role
              version: '2012-10-17'
            managed_policies:
                - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
            role_name: 'some-normal-role'
            tags:
              - key: owner
                value: cloud_admins@example.com
    """
    schema = IamRoleWorkerShipPayloadTemplate().load(yaml.safe_load(payload))

    # Make sure we can generate the iambic variables:
    iambic_vars = make_iambic_variables(schema["iambic_variables"])
    assert iambic_vars[0].key == "some-key"
    assert iambic_vars[0].value == "some-value"
    assert iambic_vars[1].key == "some-other-key"
    assert iambic_vars[1].value == "some-other-value"
    assert len(iambic_vars) == 2


def test_sorted_exception_logic() -> None:
    """
    This tests the logic in the iambic stanza rendering around sorting should there be an exception for unsupported types in sorting.
    The expected behavior is that this should ignore the exception and return the raw rendered list back out.
    """
    from starfleet.worker_ships.plugins.iam.schemas import render_iambic_stanza

    rendered = [True, False, "pewpewpew"]
    assert rendered == render_iambic_stanza(rendered)

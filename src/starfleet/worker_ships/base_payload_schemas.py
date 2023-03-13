"""Worker ship base payload schemas

This defines the base payload schemas that worker ship need to use.

:Module: starfleet.worker_ships.base_payload_schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import List, Any, Dict

from marshmallow import Schema, fields, INCLUDE, validates, ValidationError, validate, validates_schema


class WorkerShipPayloadBaseTemplate(Schema):
    """
    This is the base worker ship payload template schema. All template schemas will need to be subclasses of this.
    The instantiated object type hint is `WorkerShipPayloadBaseTemplateInstance`.

    Note: All payload YAMLs should be written in UpperCamelCase, but will be programmatically referenced in snake_case. This is intentionally
    different from the Configuration because this will be programmatically referenced _and_ mutated in Python. The Configuration
    is just a plan old dictionary which isn't manipulated, hence the difference.
    """

    template_name = fields.String(required=True, data_key="TemplateName")
    template_description = fields.String(required=True, data_key="TemplateDescription")

    class Meta:
        """By default, we will include unknown values without raising an error."""

        unknown = INCLUDE


class AccountTagNameValueSchema(Schema):
    """
    This is a component of the AccountSpecificationSchema that holds account tag names and values.

    Length validation for this is coming from: https://docs.aws.amazon.com/organizations/latest/APIReference/API_Tag.html
    """

    name = fields.String(required=True, data_key="Name", validate=validate.Length(min=1, max=128))  # The name of the tag  # noqa
    value = fields.String(required=True, data_key="Value", validate=validate.Length(max=256))  # The value for the tag  # noqa


class AccountsSpecificationSchema(Schema):
    """
    This is a component for Account-able templates that hold the account specification fields.

    Validation is largely based on this: https://docs.aws.amazon.com/organizations/latest/APIReference/API_Account.html, but we're not doing regexes.
    """

    by_names = fields.List(fields.String(validate=validate.Length(min=1, max=128)), data_key="ByNames", load_default=[])  # List of account names  # noqa
    by_ids = fields.List(fields.String(validate=validate.Length(min=1, max=12)), data_key="ByIds", load_default=[])  # List of account IDs  # noqa
    by_org_units = fields.List(fields.String(), data_key="ByOrgUnits", load_default=[])  # List of Org OU IDs or OU Names  # noqa

    # List of tag name/value pairs:
    by_tags = fields.List(fields.Nested(AccountTagNameValueSchema()), data_key="ByTags", load_default=[])

    @validates("by_org_units")
    def validate_org_units(self, data: List[str], **kwargs) -> None:  # pylint: disable=unused-argument # noqa
        """
        This validates the org OUs supplied look correct.
        See: https://docs.aws.amazon.com/organizations/latest/APIReference/API_OrganizationalUnit.html
        """
        errors = {}
        for index, org_unit in enumerate(data):
            if len(org_unit) == 0:
                errors[index] = ["Length must be greater than 0."]

            # If it begins with "ou", make sure it has the correct number of characters:
            if org_unit.startswith("ou-") and len(org_unit) > 68:
                errors[index] = ["Length must be less than 68 for OU IDs."]

            # If it's a name, then check the name length:
            elif len(org_unit) > 128:
                errors[index] = ["Length must be less than 128 for OU Names."]

        if errors:
            raise ValidationError(errors)


class IncludeAccountsSpecificationSchema(AccountsSpecificationSchema):
    """This extends the AccountsSpecificationSchema where it has an additional field for AllAccounts, which isn't used in exclusion."""

    all_accounts = fields.Boolean(data_key="AllAccounts", load_default=False)

    @validates_schema(pass_original=True)
    def verify_all_accounts_flag(self, data: Dict[str, Any], original_data: Dict[str, Any], **kwargs) -> None:  # pylint: disable=unused-argument  # noqa
        """
        This validates that the schema is correct by ensuring that if the `AllAccounts: True` flag is set
        that the other fields are not set. You can't set both AllAccounts to True and also have the other fields
        present.
        """
        errors = {}
        if data.get("all_accounts"):  # Check the properly parsed.
            # Verify that no other field is present with values: (uses the original data to get the proper field name)
            for field, value in original_data.items():
                if field != "AllAccounts" and value:
                    errors[field] = ["Can't specify other parameters when `AllAccounts` is set to `True`."]

        if errors:
            raise ValidationError(errors)


class BaseAccountPayloadTemplate(WorkerShipPayloadBaseTemplate):
    """This is a payload template for worker ships that have an ACCOUNT fan out strategy."""

    include_accounts = fields.Nested(IncludeAccountsSpecificationSchema(), data_key="IncludeAccounts", required=True)
    exclude_accounts = fields.Nested(AccountsSpecificationSchema(), data_key="ExcludeAccounts", load_default={})

    # SPECIAL NOTE: The Starbase will _NOT_ task the org root unless BOTH the IncludeAccounts contains the org root
    # account within it, AND OperateInOrgRoot is set to True
    operate_in_org_root = fields.Boolean(load_default=False, data_key="OperateInOrgRoot")

    # This field is populated by the Starbase. The Starbase will raise a fuss if this field is filled out in the template:
    starbase_assigned_account = fields.String(data_key="StarbaseAssignedAccount", load_default=None)
    # ^^ The worker ship will rely on this field to determine the AWS account to operate in.


# TODO: Implement this:
# class BaseAccountRegionPayloadTemplate(BaseAccountPayloadTemplate):
#     """This is a payload template for worker ships that have an ACCOUNT/REGION fan out strategy."""
#     include_regions = fields.List(fields.String(), data_key="IncludeRegions", required=True)
#     exclude_regions = fields.List(fields.String(), data_key="ExcludeRegions", load_default=[])

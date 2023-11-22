"""Starfleet's IAM worker ship schemas

:Module: starfleet.worker_ships.plugins.iam.schemas
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import copy
from enum import Enum
from typing import Any, Dict, List

from marshmallow import ValidationError, fields, Schema, validate

from starfleet.account_index.resolvers import resolve_account_specification, resolve_include_account_specification
from starfleet.utils.logging import LOGGER
from starfleet.worker_ships.base_payload_schemas import IncludeAccountsSpecificationSchema, AccountsSpecificationSchema, BaseAccountPayloadTemplate
from starfleet.worker_ships.ship_schematics import WorkerShipBaseConfigurationTemplate
from starfleet.worker_ships.plugins.iam.iambic_imports import Variable


class IambicTemplateTypes(Enum):
    """This is the list of iambic template types that we support."""

    IAM_ROLE = "NOQ::AWS::IAM::Role"


def render_iambic_template(template: Dict[str, Any], template_type: IambicTemplateTypes, commit: bool) -> Dict[str, Any]:
    """
    This will render an iambic template based on the Starfleet template that we received. This will perform all the work to substitute the Starfleet specific attributes in and
    convert them into iambic attributes.

    Starfleet is wrapping an iambic template. Starfleet is handling all the account related logic and then passing to iambic the current AWS account context to operate in.
    This means that the following iambic directives:
    - `included_accounts`
    - `excluded_accounts`
    - `included_orgs`
    - `excluded_orgs`

    Should NOT be used in your template. Instead, substitute these with `StarfleetIncludeAccounts` and `StarfleetExcludeAccounts` in the *same exact* schema as the
    `IncludeAccounts` and `ExcludeAccounts` directive that you already use for Starfleet. Starfleet will properly render out the iambic templates to either include
    -- or not include -- the template stanzas in the final rendered iambic template based on the AWS account it has been tasked by the Starbase (or the CLI) to operate in.
    """
    # First, check the top level components of the template. We do not need to have any account directives in there since those are already provided by
    # the Starfleet Account template.
    forbidden_fields = {  #
        "included_accounts",
        "excluded_accounts",
        "included_orgs",
        "excluded_orgs",
        "IncludeAccounts",
        "ExcludeAccounts",
        "StarfleetIncludeAccounts",
        "StarfleetExcludeAccounts",
        "iambic_managed",
    }

    for forbidden in forbidden_fields:
        if forbidden in template["iambic_role_template"]:
            raise ValidationError(f"Found forbidden top-level key: {forbidden} in the Iambic template.")

    # Next, iterate over the template and do all the required work:
    rendered_template = render_iambic_stanza(copy.deepcopy(template["iambic_role_template"]))

    # Inject the identifier and template_type into the template:
    rendered_template["identifier"] = template["template_name"]
    rendered_template["template_type"] = template_type.value
    rendered_template["file_path"] = "Starfleet"  # This is a placeholder value that iambic requires
    rendered_template["iambic_managed"] = "enforced" if commit else "import_only"
    return rendered_template


def make_iambic_variables(template_variables: List[Dict[str, str]]) -> List[Variable]:
    """This will make the iambic variable objects from the Starfleet template variables."""

    iambic_variables = []
    for variable in template_variables:
        iambic_variables.append(Variable(key=variable["key"], value=variable["value"]))

    return iambic_variables


def render_iambic_stanza(template_stanza: Any) -> Any:  # pylint: disable=too-many-branches
    """This is going to recursively iterate over the iambic template and render out the stanzas as appropriate."""
    # Is this a dictionary?
    if isinstance(template_stanza, dict):
        rendered = {}
        account_specification = {}

        for key, value in template_stanza.items():
            # Is this a forbidden field?
            if key in {"included_accounts", "excluded_accounts", "included_orgs", "excluded_orgs"}:
                raise ValidationError(
                    f"Found forbidden key: {key} in the iambic template stanza: {template_stanza}. Need to use `StarfleetIncludeAccounts` "
                    "and/or `StarfleetExcludeAccounts` instead."
                )

            try:
                if key == "StarfleetIncludeAccounts":  # pylint: disable=no-else-continue
                    schema = IncludeAccountsSpecificationSchema()
                    include_accounts = schema.load(value)
                    accounts = list(resolve_include_account_specification(include_accounts))
                    if not accounts:
                        LOGGER.warning(f"[❓] StarfleetIncludeAccounts did not resolve to any accounts in this stanza: {template_stanza}")
                    account_specification["included_accounts"] = accounts
                    continue  # No need to recurse this field since we resolved it.

                elif key == "StarfleetExcludeAccounts":
                    schema = AccountsSpecificationSchema()
                    exclude_accounts = schema.load(value)
                    accounts = list(resolve_account_specification(exclude_accounts))
                    if not accounts:
                        LOGGER.warning(f"[❓] StarfleetExcludeAccounts did not resolve to any accounts in this stanza: {template_stanza}")
                    account_specification["excluded_accounts"] = accounts
                    continue  # No need to recurse this field since we resolved it.

            # If there was an error, make the `_schema` value something more obvious to the user, like the Include/Exclude section name:
            except ValidationError as verr:
                LOGGER.error(f"[👾] The field: {key} does not properly conform to the {key} specification.")
                if verr.messages_dict.get("_schema"):
                    verr.messages_dict[key] = verr.messages_dict.pop("_schema")
                raise verr

            rendered[key] = render_iambic_stanza(value)

        # Update the rendered template with the account specification if it is present:
        rendered.update(account_specification)

    elif isinstance(template_stanza, list):
        rendered = []
        for item in template_stanza:
            rendered.append(render_iambic_stanza(item))

        try:
            sorted_list = sorted(rendered)
            rendered = sorted_list
        except Exception:  # noqa # nosec # pylint: disable=broad-except
            return rendered

    else:
        rendered = template_stanza

    # If nothing else, return:
    return rendered


class IambicVariable(Schema):
    """This is an iambic variable that get passed into the iambic worker."""

    key = fields.String(required=True, validate=validate.Length(min=1), data_key="Key")
    value = fields.String(required=True, validate=validate.Length(min=1), data_key="Value")


class IamRoleWorkerShipPayloadTemplate(BaseAccountPayloadTemplate):
    """This is the payload template for the IamRoleWorkerShip. This will wrap an embedded iambic template."""

    iambic_role_template = fields.Dict(required=True, data_key="IambicRoleTemplate")
    iambic_variables = fields.List(fields.Nested(IambicVariable()), required=False, load_default=[], data_key="IambicVariables")


class IamRoleWorkerConfigurationTemplate(WorkerShipBaseConfigurationTemplate):
    """This is the configuration template that defines how to configure the IamRoleWorker."""

    worker_role_to_assume = fields.String(required=True, data_key="WorkerRoleToAssume")
    worker_role_session_name = fields.String(required=False, load_default="StarfleetIamRoleWorkerShip", data_key="WorkerRoleSessionName")

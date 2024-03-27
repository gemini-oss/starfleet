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
from click import Context, Option, ClickException, Command

from starfleet.account_index.resolvers import resolve_worker_template_accounts, resolve_worker_template_account_regions
from starfleet.worker_ships.ship_schematics import WorkerShipPayloadBaseTemplate, StarfleetWorkerShip, StarfleetWorkerShipInstance
from starfleet.worker_ships.base_payload_schemas import BaseAccountPayloadTemplate, BaseAccountRegionPayloadTemplate


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


class BadWorkerError(Exception):
    """This is raised if the developer didn't follow the instructions when setting up the Click group. You need to have:

    ```
        ...
        @click.group()
        @click.pass_context
        def some_worker(ctx: Context) -> None
            # VERY IMPORTANT: Instantiate the worker:
            ctx.obj = MyWorkerShip()
        ...
    ```
    """


class BadWorkerTemplateError(Exception):
    """This is raised if the developer is using the wrong Starfleet command type. I.e. using StarfleetAccountRegionCommand for a non ACCOUNT_REGION worker"""


class StarfleetSingleInvokeCommand(Command):
    """
    This is a Click command class that defines the basic minimum parameters that is needed for a SINGLE_INVOCATION worker.
    At a minimum, an SINGLE_INVOCATION worker will need a payload.

    This is used as follows:
    ```
        import click
        from click import Context

        from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip


        class MyWorkerShip(StarfleetWorkerShip):
            ...


        @click.group()
        @click.pass_context
        def some_worker(ctx: Context) -> None
            # VERY IMPORTANT: Instantiate the worker:
            ctx.obj = MyWorkerShip()


        @some_worker.command(cls=StarfleetSingleInvokeCommand)
        @click.option("--some-example-flag", is_flag=True, help="Some flag to add in addition to the other required things")
        def do_work(ctx: Context, commit: bool, some_example_flag: bool, **kwargs) -> None:
            worker = ctx.obj
            # ...
            worker.execute(commit=commit)
    ```
    """

    def __init__(self, name, callback, **kwargs):
        """This is the overridden __init__ that will set up the parameters that we need."""
        params = kwargs.pop("params", [])

        params += [
            click.Option(["--payload"], required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML"),
            click.Option(["--commit"], is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made"),
        ]
        super().__init__(name, callback=callback, params=params, **kwargs)

    def invoke(self, ctx: Context) -> Any:
        """
        Wrap the invocation with our own code to perform all the validation logic required to verify that the template is valid
        """
        worker: StarfleetWorkerShipInstance = ctx.obj
        if not isinstance(worker, StarfleetWorkerShip):
            click.echo(
                "[⛔] The CLI for this is not set up properly. The developer needs to set `ctx.obj = YourWorkerShip()` in the Click group. "
                "See the developer guide for details.",
                err=True,
            )
            raise BadWorkerError()

        if not issubclass(worker.payload_template_class, WorkerShipPayloadBaseTemplate):
            click.echo(
                "[⛔] The CLI for this is not set up properly. This CLI command class is for SINGLE_INVOCATION workers and the worker ship needs to have a template class"
                "that is derived from WorkerShipPayloadBaseTemplate. See the developer guide for details.",
                err=True,
            )
            raise BadWorkerTemplateError()

        # Confirm that the template is correct:
        click.echo("[🛃] Validating the template...")
        worker.load_template(ctx.params["payload"])

        click.echo(f"[🆗] Template OK: Executing worker: {worker.worker_ship_name}...")
        return super().invoke(ctx)


class StarfleetAccountCommand(Command):
    """
    This is a Click command class that defines the basic minimum parameters that are needed for an ACCOUNT worker.
    At a minimum, an ACCOUNT worker will need a payload, and an AWS account ID.

    This is used as follows:
    ```
        import click
        from click import Context

        from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip


        class MyWorkerShip(StarfleetWorkerShip):
            ...


        @click.group()
        @click.pass_context
        def some_worker(ctx: Context) -> None
            # VERY IMPORTANT: Instantiate the worker:
            ctx.obj = MyWorkerShip()


        @some_worker.command(cls=StarfleetAccountCommand)
        @click.option("--some-example-flag", is_flag=True, help="Some flag to add in addition to the other required things")
        def do_work(ctx: Context, commit: bool, some_example_flag: bool, **kwargs) -> None:
            worker = ctx.obj
            # ...
            worker.execute(commit=commit)
    ```
    """

    def __init__(self, name, callback, **kwargs):
        """This is the overridden __init__ that will set up the parameters that we need."""
        params = kwargs.pop("params", [])

        params += [
            click.Option(["--payload"], required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML"),
            click.Option(["--account-id"], required=True, type=str, help="The AWS account ID to operate in"),
            click.Option(["--commit"], is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made"),
        ]
        super().__init__(name, callback=callback, params=params, **kwargs)

    def invoke(self, ctx: Context) -> Any:
        """
        Wrap the invocation with our own code to perform all the validation logic required to:
            1. Verify that the template is valid
            2. Verify that the template in question is applicable to the account that we are in
            3. Update the payload's StarbaseAssignedAccount to simulate this being invoked from the Starbase
        """
        worker: StarfleetWorkerShipInstance = ctx.obj
        if not isinstance(worker, StarfleetWorkerShip):
            click.echo(
                "[⛔] The CLI for this is not set up properly. The developer needs to set `ctx.obj = YourWorkerShip()` in the Click group. "
                "See the developer guide for details.",
                err=True,
            )
            raise BadWorkerError()

        if not issubclass(worker.payload_template_class, BaseAccountPayloadTemplate):
            click.echo(
                "[⛔] The CLI for this is not set up properly. This CLI command class is for ACCOUNT workers and the worker ship needs to have a template class"
                "that is derived from BaseAccountPayloadTemplate. See the developer guide for details.",
                err=True,
            )
            raise BadWorkerTemplateError()

        # Step 1: Confirm that the template is correct:
        click.echo("[🛃] Validating the template...")
        worker.load_template(ctx.params["payload"])

        # Step 2: Verify that the account/region provided is applicable to this template:
        click.echo("[🌎] Confirming the account passed in is applicable for this template...")
        accounts = resolve_worker_template_accounts(worker.payload)
        if ctx.params["account_id"] not in accounts:
            raise click.ClickException("[🙅‍♂️] The account provided is not applicable for this template. Not doing anything.")

        # Step 3: Update the payload to include the account and region details as if the Starbase tasked this:
        worker.payload["starbase_assigned_account"] = ctx.params["account_id"]

        click.echo(f"[🆗] Template OK: Executing worker: {worker.worker_ship_name}...")
        return super().invoke(ctx)


class StarfleetAccountRegionCommand(Command):
    """
    This is a Click command class that defines the basic minimum parameters that are needed for an ACCOUNT_REGION worker.
    At a minimum, an ACCOUNT-REGION worker will need a payload, an AWS account ID, and an AWS region.

    This is used as follows:
    ```
        import click
        from click import Context

        from starfleet.worker_ships.ship_schematics import StarfleetWorkerShip


        class MyWorkerShip(StarfleetWorkerShip):
            ...


        @click.group()
        @click.pass_context
        def some_worker(ctx: Context) -> None
            # VERY IMPORTANT: Instantiate the worker:
            ctx.obj = MyWorkerShip()


        @some_worker.command(cls=StarfleetAccountRegionCommand)
        @click.option("--some-example-flag", is_flag=True, help="Some flag to add in addition to the other required things")
        def do_work(ctx: Context, commit: bool, some_example_flag: bool, **kwargs) -> None:
            worker = ctx.obj
            # ...
            worker.execute(commit=commit)
    ```
    """

    def __init__(self, name, callback, **kwargs):
        """This is the overridden __init__ that will set up the parameters that we need."""
        params = kwargs.pop("params", [])

        params += [
            click.Option(["--payload"], required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML"),
            click.Option(["--account-id"], required=True, type=str, help="The AWS account ID to operate in"),
            click.Option(["--region"], required=True, type=str, help="The AWS region to operate in"),
            click.Option(["--commit"], is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made"),
        ]
        super().__init__(name, callback=callback, params=params, **kwargs)

    def invoke(self, ctx: Context) -> Any:
        """
        Wrap the invocation with our own code to perform all the validation logic required to:
            1. Verify that the template is valid
            2. Verify that the template in question is applicable to the account and region that we are in
            3. Update the payload's StarbaseAssignedRegion, and StarbaseAssignedAccount to simulate this being invoked from the Starbase
        """
        worker: StarfleetWorkerShipInstance = ctx.obj
        if not isinstance(worker, StarfleetWorkerShip):
            click.echo(
                "[⛔] The CLI for this is not set up properly. The developer needs to set `ctx.obj = YourWorkerShip()` in the Click group. "
                "See the developer guide for details.",
                err=True,
            )
            raise BadWorkerError()

        if not issubclass(worker.payload_template_class, BaseAccountRegionPayloadTemplate):
            click.echo(
                "[⛔] The CLI for this is not set up properly. This CLI command class is for ACCOUNT_REGION workers and the worker ship needs to have a template class"
                "that is derived from BaseAccountRegionPayloadTemplate. See the developer guide for details.",
                err=True,
            )
            raise BadWorkerTemplateError()

        # Step 1: Confirm that the template is correct:
        click.echo("[🛃] Validating the template...")
        worker.load_template(ctx.params["payload"])

        # Step 2: Verify that the account/region provided is applicable to this template:
        click.echo("[🌎] Confirming the account and region passed in are applicable for this template...")
        account_regions = resolve_worker_template_account_regions(worker.payload)
        if ctx.params["region"] not in account_regions.get(ctx.params["account_id"], set()):
            raise click.ClickException("[🙅‍♂️] The account/region provided is not applicable for this template. Not doing anything.")

        # Step 3: Update the payload to include the account and region details as if the Starbase tasked this:
        worker.payload["starbase_assigned_account"] = ctx.params["account_id"]
        worker.payload["starbase_assigned_region"] = ctx.params["region"]

        click.echo(f"[🆗] Template OK: Executing worker: {worker.worker_ship_name}...")
        return super().invoke(ctx)

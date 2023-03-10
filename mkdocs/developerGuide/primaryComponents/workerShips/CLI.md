# CLI - Command Line Interface Plugins

We provide a CLI in Starfleet so that we are able to invoke the workers on demand locally. This assists with debugging and the occasional need to invoke a workload.

To make expose CLIs, you need to make use of Click `Group`s. The `AccountIndexGeneratorShip` provides an example:

```python
@click.group()
def account_inventory() -> None:
    """This is the worker ship for generating an S3 account inventory"""


@account_inventory.command()
@click.option("--payload", required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML")
@click.option("--commit", is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made")
def generate(payload: Dict[str, Any], commit: bool) -> None:
    """This will generate an AWS account inventory from the organizations API"""
    if not commit:
        LOGGER.warning("[⚠️] Commit flag is disabled: not saving report to S3")

    worker = AccountIndexGeneratorShip()
    worker.load_template(payload)
    worker.execute(commit=commit)

    LOGGER.info("[✅] Done!")
```

!!! tip
    You will really want to get familiar with [Click's documentation](https://click.palletsprojects.com/) for groups and commands.


## The Click `Group`
All CLI commands are to be a part of a `click` group. The groups are a collection of commands. The general gist for this is that when the CLI is used, it's going to be: `starfleet GROUP COMMAND ARGS`.

We first make a function that is _named_ as the command group we want. In the example above, we wrap a function named `account_inventory` with a `@click.group()` decorator. This will make it so that `starfleet account-inventory` is a command available (`click` will substitute underscores (`_`) with hyphens (`-`) automatically for you).

You can make as many groups as you want. We will discuss later how to make it so that these are loaded on start up.

## The Click `Command`s
You will define the commands themselves with Click commands that are a part of the `Group`. This is done by making a function that is wrapped with the group function as a decorator like in the example:

```python
@account_inventory.command()
# ...
def generate(payload: Dict[str, Any], commit: bool) -> None:
    # ...
```

Put together it's:

```python
@click.group()
def your_group() -> None:
    pass

@your_group.command()
def your_command() -> None:
    pass
```
In this example, the command to execute it is `starfleet your-group your-command`. You can add in as many commands as you want.

## Recommended Options
We recommend that you always add a `--commit` flag to your commands. Please copy and paste:

```python
@click.option("--commit", is_flag=True, default=False, show_default=True, help="Must be supplied for changes to be made")
```

... and decorate your command with it.

We also provide a convenience option for loading a payload YAML file to supply to your worker ship. To use it, copy and paste:

```python
@click.option("--payload", required=True, type=click.File("r"), callback=load_payload, help="This is the worker payload YAML")
```
The main thing here is the `callback=load_payload`, which does a some work to load the payload. Note: this does not validate the payload; you will still need to do that.

### General Usage
In general, you will want to just copy and paste what we have in the `AccountIndexGeneratorShip`, which for commands you will always want something that will instantiate the worker ship, load the payload template, and then execute the workload.

See above for the example.

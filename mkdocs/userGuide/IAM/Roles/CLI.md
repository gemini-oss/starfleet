# IAM Role Worker CLI

The IAM Role worker CLI resides under the `iam role` sub-command. Below are the CLI options

```bash
starfleet iam role
Usage: starfleet iam role [OPTIONS] COMMAND [ARGS]...

  This is the worker ship for processing a Starfleet-wrapped iambic.org IAM
  role template.

  Note: The account index is utilized for these commands and as such, AWS
  credentials may be required to run them.

Options:
  --help  Show this message and exit.

Commands:
  sync             This will invoke iambic to sync out the IAM role.
  validate-iambic  This will validate the supplied Starfleet-wrapped...
```

## The `iam role validate-iambic` command
This command is used to ensure that template itself is mostly well formed. This will not perform any account resolution logic and is mostly used to confirm that the template will make its way to IAMbic and that IAMbic is satisfied with the template.

This command does _not_ require AWS credentials and does not take in any arguments other than the path to the file to validate. The `commit` flag has no effect on this command. Example:

```bash
starfleet iam role --payload some/path/to/the/payload.yaml
```

The output will inform you if there are any problems or not and what fixes should be performed if there are any issues.

## The `iam role sync` command
This is analogous to all the other `sync` commands for the other workers. This command does require AWS credentials and will perform both the validation for a given AWS account and if the `commit` flag is supplied, it will perform any changes required.

Here is an example of how to run it in commit mode on account ID `111111111111`:

```bash
starfleet iam role sync --payload some/path/to/the/payload.yaml --account-id 111111111111 --commit
```

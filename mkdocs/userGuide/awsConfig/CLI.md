# AWS Config Worker CLI

The AWS Config worker has just 1 CLI command (`sync`), which syncs the AWS Config template to the given AWS Account ID and region in question.

Below is the CLI options:

```bash
Usage: starfleet aws-config sync [OPTIONS]

  This will sync the AWS Config payload in the desired account and region.

Options:
  --payload FILENAME  This is the worker payload YAML  [required]
  --account-id TEXT   The AWS account ID to operate in  [required]
  --region TEXT       The AWS region to operate in  [required]
  --commit            Must be supplied for changes to be made
  --help              Show this message and exit.
```

## The `aws-config sync` command
Running the sync command requires that you have the required Starfleet AWS credentials exported in the environment. Here is an example of how to run it in commit mode on account ID `111111111111` in `us-east-1`:

```bash
starfleet aws-config sync --payload some/path/to/the/payload.yaml --account-id 111111111111 --region us-east-1 --commit
```

# User Guide
This page outlines how to use Starfleet and provides a guide around using each included worker ship.

As previously mentioned, the purpose of Starfleet is to augment AWS Organizations. It should be used to enable features that you need everywhere to help maintain a secure cloud infrastructure state.

In this section of the documentation, we provide a general overview of how to use each included plugin, as well as some common troubleshooting.

## General Gist
In general Starfleet works based on a combination of:

1. The Starbase
1. Deployed Workers
1. Configuration
1. Payloads

Each worker has its own Configuration and Payload definitions. You should be familiar with the [Architecture](../architecture/Overview.md) and [Installation Guide](../installation/Overview.md) before moving on to this section because it will make a lot of the topics discussed familiar.

## General Troubleshooting
The Starbase and the worker ship plugins are Lambda functions and will output logs to CloudWatch LogGroups. Reviewing the logs in the log group will provide you with the best details on what's happening under the hood.

## Command Line Interface
Starfleet has a command line interface that is executable via the `starfleet` command once you are in an activate virtual environment. All plugins should expose some command groups that you can execute and then explore for additional details.

In general, you will need AWS credentials for Starfleet to utilize to ensure that these commands can run. This is mostly documented in the [Installation Guide](../installation/IAM.md).

Each worker ship should have documentation on how to execute the respective commands.

### Common CLI Components
In general all worker ships utilize common components to expose their CLIs. All worker ships will have a the following fields in common:

#### Payload (`--payload`)
The payload flag (`--payload`) specifies where to load the payload YAML (`--payload path/to/payload/template`) for the worker ship CLI. This is used as follows:

```bash
starfleet account-index generate --payload some/path/to/your/payload.yaml
```

#### The Commit Flag (`--commit`)
The commit flag (`--commit`) must be added to inform the worker ship plugin that it should operate in a commit mode to make changes. Not including the flag will ensure that the worker ship runs in read-only mode.

Omitting the `--commit` flag is analogous to running `terraform plan`, and adding the `--commit` flag is analogous to running `terraform apply`.

Example of it's usage is:

```bash
starfleet account-index generate --payload some/path/to/your/payload.yaml --commit
```

#### Account ID (`--account-id`)
In addition to the above, Account worker ships will also require an `--account-id` argument that takes in the 12-digit AWS Account ID of the AWS account to operate the payload template against. Here is an example of that being used:

```bash
starfleet some-account-worker some-command --payload some/path/to/the/payload.yaml --account-id 111111111111
```

#### Region (`--region`)
Account/Region workers need both the `--account-id` and the `--region` flags passed in. The region is the name of the AWS region to operate in. Here is an example:

```bash
starfleet aws-config sync --payload some/path/to/the/payload.yaml --account-id 111111111111 --region us-east-1
```

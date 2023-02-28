# Account Index
Starfleet has the concept of an account index. This is an inventory of all AWS accounts that Starfleet can operate over. For simplicity and clarity of documentation, we are going to make the assumption that you are a user of AWS Organizations and have exactly one AWS Organization with many accounts under it.

The account index keeps a list of accounts that at a minimum need to keep track of:

1. AWS account IDs
1. Enabled regions for accounts
1. AWS account names
1. AWS account tags
1. Organization Units (if applicable)
1. Organization Roots (if applicable)

The payload templates will specify the account identifiers listed above for `ACCOUNT` or `ACCOUNT-REGION` payload templates (via the `IncludeAccounts` or `ExcludeAccounts` directives [as documented here](PayloadTemplates.md#account-worker-templates)). The account indexer allows Starfleet to figure out which accounts (or accounts/regions) need to be tasked with a given payload.

The Account Indexer is also a "ship" in Starfleet (i.e. it's a plugin). The name of the plugin must be present within the `STARFLEET` configuration under the field `AccountIndex`. Example:
```yaml
AccountIndex: StarfleetDefaultAccountIndex
```

!!! note
    Starfleet can support any number of accounts and organizations. As long as your account indexer can index it, it can support it!

## Default Account Indexer
Starfleet includes with an account index generator worker ship (`AccountIndexGeneratorShip`) that lists all the accounts in AWS Organizations, fetches their enabled regions, tags, and parent OUs, and then saves this as a JSON file to an S3 bucket.

In addition to the worker ship for generating the index, Starfleet also ships with an account index plugin (`StarfleetDefaultAccountIndex`) that leverages the saved JSON from the `AccountIndexGeneratorShip` to provide Starfleet with the account index capabilities.

This is described in much more detail in the User Guide.

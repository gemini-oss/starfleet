# Secrets Management in Starfleet

Starfleet relies on an optional AWS Secrets Manager component for storing sensitive data, like tokens, passwords, and encryption keys. If you don't have a need for this then you don't need to make use of this.

The [Developer Guide](../developerGuide/primaryComponents/SecretsManager.md) has the raw details on how this works programmatically, but for this guide, we are going to explore how to configure it and make use if it.

!!! note "Cached Data Notice"
    Like the other components in Starfleet, the loaded data will persist in memory on subsequent runs of the Lambda function. This has the benefit of not needing to make repeated AWS Secrets Manager API calls, which saves money. The downside to this is that AWS will persist the secrets value in memory as long as the container running your Lambda function remains operational (this happens on the AWS backend; you don't have control over it). If you make an update to the secret string, subsequent Lambda calls may not yet see it and you could operate off of the old cached secrets value.

    AWS will periodically rotate the Lambda container out every few hours if no code has changed. The only way for you to force your Lambda function's container to rotate out is to actually update the code for your Lambda function.

!!! tip "Slack"
    If you make use of Slack for alerts, then you need to configure the Secrets Management in Starfleet. Continue reading this page for details.

## The Secret
Starfleet uses an AWS Secrets Manager secret for storing sensitive data. The data in the secret is stored as a JSON string that looks like this:

```json
{
    "STARFLEET": {
        "SlackToken": "the-token-here"
    },
    "WORKER_NAME": "Any value - this can be a string, nested Dict, etc.",
    "...More Workers Here..."
}
```

You will need to create a secret named `Starfleet` in AWS secrets manager in the same account and region as Starfleet. The initial value for this JSON should look like this:
```json
{
    "STARFLEET": {}
}
```

Once this is saved, you will need to ensure that all Starfleet components that need access to this secret have their AWS Lambda function IAM roles be given the following permissions to access the secret:
```json
{
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "secretsmanager:GetSecretValue",
            "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:SECRET-ID-HERE"
        }
    ]
}
```

We recommend making this a managed policy that is attached to all the worker IAM roles.

## Configuration
If you are making use of the Secrets Management feature, you have to make sure that the Starfleet configuration is configured to point to it. Under the main `STARFLEET` stanza of the configuration you need to have the following:

* **`SecretsManager`** - This is a dictionary that outlines the ID of an AWS Secrets Manager secret. This allows Starfleet workers to reference secrets. If specified, this contains 2 required fields: `SecretId` and `SecretRegion`. The ID is the name of the secret and the region is the region for it. The secret should reside in the same AWS account as Starfleet.

This is what that looks like:

```yaml
STARFLEET:
  # ... All the other stuff here ...
  SecretsManager:
    SecretId: Starfleet        # This is the name of the AWS Secrets Manager secret. The secret must reside in the same AWS account as Starfleet.
    SecretRegion: us-east-2    # This is the AWS region for where the secret resides.

WorkerName:
  Enabled: True
  # ... All the other stuff here ...
```

## Example Secret Entry
An example of a secret JSON string for a Starfleet setup with Slack and a GitHub application for the `GitHubSyncWorkerShip` would look something like this:

```json
{
    "STARFLEET": {
        "SlackToken": "xoxb-REDACTED"
    },
    "GitHubSyncWorker": {
        "GITHUB_ORG_NAME_HERE": "-----BEGIN RSA PRIVATE KEY-----\nREDACTED\nREDACTED\nREDACTED\n-----END RSA PRIVATE KEY-----"
    }
}
```

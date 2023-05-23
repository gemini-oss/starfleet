# Secrets Manager
Starfleet includes a singleton component for interacting with AWS Secrets Manager. This allows you to securely store sensitive details that Starfleet workers can access.

## Secrets Format
The secrets are stored as a JSON string in Secrets Manager. It generally follows this format:

```json
{
    "STARFLEET": {
        "SlackToken": "the-token-here"
    },
    "WORKER_NAME": "Any value - this can be a string, nested Dict, etc.",
    "...More Workers Here..."
}
```

The secret entire secret as shown above is stored as a string in Secrets Manager. A singleton, `SECRETS_MANAGER` resides in `starfleet.utils.secrets`, and it will lazy load the secrets when you reference the `SECRETS_MANAGER.secrets` property, which is a simple Python dictionary.

You will also note the `SlackToken` above under the `STARFLEET` section of the JSON. That is where the Slack token is used for Slack alerts. Here is a small code snippet of the Slack component referencing the Slack token secret:


```python
if not self._web_client:
    self._web_client = WebClient(token=SECRETS_MANAGER.secrets["STARFLEET"]["SlackToken"])
```

You simply reference the secret out of the dictionary in the same way that you would for the Starfleet configuration.


## Configuration Requirement
If you are making use of the Secrets Management component, you have to make sure that the Starfleet configuration is configured to point to it. Under the main `STARFLEET` stanza of the configuration you need to have the following:

```yaml
  SecretsManager:
    SecretId: Starfleet        # This is the name of the AWS Secrets Manager secret. The secret must reside in the same AWS account as Starfleet.
    SecretRegion: us-east-2    # This is the AWS region for where the secret resides.
```

!!! note "IAM Permissions"
    If you make use of the secret, you will need to make sure that the Starfleet worker in question has IAM permissions to access the secret. See the included SAM template for an example of what this should look like.

!!! note "Cached Data Notice"
    Like the other singletons in Starfleet, the loaded data will persist in memory on subsequent runs of the Lambda function. This has the benefit of not needing to make repeated AWS Secrets Manager API calls, which saves money. The downside to this is that AWS will persist the secrets value in memory as long as the container running your Lambda function remains operational (this happens on the AWS backend; you don't have control over it). If you make an update to the secret string, subsequent Lambda calls may not yet see it and you could operate off of the old cached secrets value.

    AWS will periodically rotate the Lambda container out every few hours if no code has changed. The only way for you to force your Lambda function's container to rotate out is to actually update the code for your Lambda function.

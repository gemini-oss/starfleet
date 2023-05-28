# Secrets Management

Starfleet has an internal component for managing secrets that may be used throughout the application. This makes use of [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/) to securely store sensitive data, like tokens, keys, and passwords that a worker may need to utilize.

If making use of Slack alerts, then the Slack token will need to be stored here.

More details on the secrets management is in the User and Developer guides.

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

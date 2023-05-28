# GitHub Repository Sync Worker User Guide
This is the main user guide for the GitHub Repository Sync Worker ship. This page documents all that there is to know about this worker ship.

## What does it do?
This worker ship periodically syncs a GitHub repository with an S3 bucket. The primary purpose of this worker is to enable CI/CD capabilities in Starfleet. CI/CD happens when a repository on GitHub with the Starfleet payload template YAML files are synced with Starfleet's template S3 bucket. Whenever objects are placed into the bucket, a notification is sent out to the Starbase FanOut function, which will then fetch the updated template YAML and task the corresponding worker ship for processing.

However, this can be used for many GitHub -> S3 use cases.

## How it works
The GitHub Sync worker is a `SINGLE_INVOCATION` worker, no AWS account or region context is required. This works by:

1. Authenticating as a GitHub App to your GitHub organization
1. Downloading the .zip of the specified repository's branch
1. Optionally - extract the .zip file
1. Compare the downloaded data (either the raw .zip or the extracted files) with the data in S3. If the files are different, then it will upload them.
1. It will optionally delete files on the bucket that are not present in the repository

The worker will determine that a file needs to be uploaded if the file is missing in S3 or if the file in S3 has a checksum (S3 ETag) that is not the same as the file in the repo.

## Recommended use cases
This worker is optimal for the use case of syncing small text files to S3. I.e. the case of syncing Starfleet payload YAML templates. It is *not* recommended for syncing very large files or syncing a very large number of files. Keep in mind that this runs in a Lambda function so anything that can be accomplished by Lambda is what this is optimal for.

This worker could be a good use case for syncing static files to an S3 bucket to source a CloudFront distribution.

We also recommend that you run this worker with an EventBridge schedule set to `FIVE_MINUTES`.

## Alerting
The GitHub Sync worker supports alerts to Slack. It will alert on any errors that are encountered during execution. It will also emit `IMPORTANT` notices if it makes any changes to S3.

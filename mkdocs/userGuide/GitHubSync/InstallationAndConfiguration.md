# GitHub Repo Sync Worker: Installation & Configuration
This page outlines the installation and configuration for the GitHub Repo Sync worker ship.

## Installation
To install this, you need the following prerequisites:

1. You need to follow the instructions on the [previous page](ConfigureGitHubApp.md) to configure the GitHub application first
1. You need to have Secrets Manager configured with the secrets as documented on the previous page
1. You will need to have a GitHub repo that you want to perform the syncing on and also the S3 bucket in question

    !!! Note
        The bucket to sync the repository with does not need to reside in the same account as the Starfleet worker. If you have a cross-account use case, you will need to update the bucket policy to permit the cross-account write. We strongly recommend either disabling ACLs on the bucket or setting the object owner ship flag to `Bucket Owner Preferred`. The worker will upload all objects with the `bucket-owner-full-control` canned-acl so either disabling ACLs or setting `Bucket Owner Preferred` will work perfectly.

### AWS SAM Template
The AWS SAM template is below to get this worker deployed. The templates for testing and production are mostly the same. How each of them work is determined by the configuration of the worker and the corresponding templates. That is to say, the worker configuration specifies which path in the template S3 bucket to locate the GitHub Repo Sync worker payloads. The payloads outline the repository and target S3 bucket to sync to. This will be explained more in the template section. You can also turn off modification to files in S3 by setting the `STARFLEET_COMMIT` environment variable set to `False`.

!!! tip
    We have included the below SAM details in the `test_sam_template.yaml` file that is included with this repo. All you need to do is uncomment the sections labeled `Uncomment for the GitHub Repo Sync Worker` with the details outlined.

```yaml
Resources:
  # ...

  GitHubSyncWorkerDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-github-sync-worker-dlq
      RedriveAllowPolicy:
        redrivePermission: allowAll

  GitHubSyncWorkerQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-github-sync-worker
      VisibilityTimeout: 300  # This needs to be the same as the Lambda function timeout.
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt GitHubSyncWorkerDLQ.Arn
        maxReceiveCount: 4

  GitHubSyncWorker:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./src
      Handler: starfleet.worker_ships.plugins.github_sync.ship.lambda_handler
      Runtime: python3.10
      Architectures:
        - arm64
      MemorySize: 128
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt GitHubSyncWorkerQueue.Arn
            BatchSize: 2
      Environment:
        Variables:
          STARFLEET_COMMIT: True
      Policies:
        # Grant permissions to read and write to the templates bucket, so you can do CI/CD!
        - S3CrudPolicy:
            BucketName: !Ref StarfleetTemplateBucket
        # Add any additional S3 policies here!

  # ...
  AssumeRoleManagedPolicy:
    # ...
    PolicyDocument:
      Version: "2012-10-17"
      Statement:
        # ...
        # Add the secrets manager permissions as well for Slack alerts and GitHub access
        - Effect: Allow
          Action: secretsmanager:GetSecretValue
          Resource: arn:aws:secretsmanager:REGION:ACCOUNTNUMBER:secret:STARFLEET-SECRET-ID-HERE
    Roles:
      # ...
      - !Ref GitHubSyncWorkerRole  # GitHubSyncWorkerRole is created automatically by SAM and can be referenced

# ...
Outputs:
  # ...
  GitHubSyncWorkerQueue:
    Description: The Queue URL for the GitHub Sync Worker invocation queue
    Value: !GetAtt GitHubSyncWorkerQueue.QueueUrl
  GitHubSyncWorkerDLQ:
    Description: The Queue URL for the GitHub Sync Worker invocation DLQ
    Value: !GetAtt GitHubSyncWorkerDLQ.QueueUrl
  GitHubSyncWorker:
    Description: The GitHub Sync Worker ship function that syncs a GitHub repo with S3
    Value: !GetAtt GitHubSyncWorker.Arn
```

## Configuration
The last part of the installation process is to make sure that we have the correct configuration in place. Because this worker *requires* AWS Secrets Manager to be used, you need to make sure that the `STARFLEET` stanza of the configuration contains the details about Secrets Manager, by defining the `SecretsManager` part.

No other unique fields exist for this worker ship. Here is an example of it all together:

```yaml
STARFLEET:
  # ... All the other stuff here ...
  SecretsManager:
    SecretId: Starfleet        # This is the name of the AWS Secrets Manager secret. The secret must reside in the same AWS account as Starfleet.
    SecretRegion: REGION       # This is the AWS region for where the secret resides.

GitHubSyncWorkerShip:
  Enabled: True
  TemplatePrefix: GitHubSyncWorkerShip/
  InvocationQueueUrl: https://sqs.REGION.amazonaws.com/ACCOUNT-ID/starfleet-github-sync-worker
  InvocationSources:
    - EVENTBRIDGE_TIMED_EVENT
    - S3
  EventBridgeTimedFrequency: FIVE_MIN  # We recommend every 5 minutes
  # Optional for Slack Alerts:
#   AlertConfiguration:
#     ChannelId: SLACK CHANNEL ID
#     AlertPriority: INFORMATIONAL
```

!!! tip "Testing and Production paths for Starfleet payload templates"
    We strongly recommend using this worker for syncing the Starfleet templates from git to the S3 templates bucket. The recommended strategy is to have the `TemplatePrefix` for testing set to `testing/GitHubSyncWorkerShip/` and production to be set to `GitHubSyncWorkerShip/`, which is what's outlined in the example above.

    Later, in the payload templates, we will configure the testing payload to only care about items in the `testing/` path vs. production which will be configured to ignore the `testing/` path.

# Installing & Configuring the IAM Role Worker
Installing the IAM Role worker requires the following components:

1. The Starfleet worker role with permissions to perform IAM changes in all your accounts.
1. Update to the AWS SAM template to include all the additional components to deploy the worker
1. Updated configuration
1. Payload templates

!!! danger "Security Sensitive"
    As previously mentioned throughout the documentation, Starfleet is a privileged security application given that it has powerful
    permissions to mutate resources throughout your infrastructure. As such, this should be deployed in a security sensitive account
    with limited access.

## Update the Starfleet Account-Resident Roles
In the [installation guide](../../../installation/IAM.md), we discussed the creation of the Starfleet account resident roles that the workers will assume to perform their tasks. You will need to update these roles with the required IAM permissions. We are going to assume that for Test accounts, you will want read-only permissions, and for Prod accounts, you will want read/write permissions:

### Test Role - Read Only
Add the following to the `starfleet-worker-basic-test-role` permissions:

```yaml
ManagedPolicyArns:
    - arn:aws:iam::aws:policy/IAMReadOnlyAccess
```

### Prod Role - Read/Write
Add the following to the `starfleet-worker-basic-prod-role` permissions:

```yaml
ManagedPolicyArns:
    - arn:aws:iam::aws:policy/IAMFullAccess
```

## AWS SAM Template
For the AWS SAM template, you will need to add in this worker's components to it. The templates for testing and production are mostly the same. The only difference is that for production, we have the `STARFLEET_COMMIT` environment variable set to `True`. See the special note below about setting the `GIT_PYTHON_REFRESH` environment variable, which is required for the IAMbic library to work.

!!! tip
    We have included the below SAM details in the `test_sam_template.yaml` file that is included with this repo. All you need to do is uncomment the sections labeled `Uncomment for the IAM Role Worker` with the details outlined.

!!! danger "Global Environment Variable Required!"
    The IAMbic library requires that you set the following environment variable in the SAM configuration:

    ```yaml
    Globals:
      Function:
        Timeout: 300
        Environment:
          Variables:
            GIT_PYTHON_REFRESH: quiet  # Required for IAMbic in the IAM Role Worker
    ```
    We recommend that this be globally as it impacts both the worker and the Starbase.

### Test Template: No Commit
Here is a sample of what should be in your test template:

```yaml
Globals:
  Function:
    Timeout: 300
    Environment:
      Variables:
        GIT_PYTHON_REFRESH: quiet  # Required for IAMbic in the IAM Role Worker

# ...

Resources:
  # ...

IamRoleWorkerDLQ:
   Type: AWS::SQS::Queue
   Properties:
     QueueName: starfleet-iam-role-worker-dlq
     RedriveAllowPolicy:
       redrivePermission: allowAll

 IamRoleWorkerQueue:
   Type: AWS::SQS::Queue
   Properties:
     QueueName: starfleet-iam-role-worker
     VisibilityTimeout: 300  # This needs to be the same as the Lambda function timeout.
     RedrivePolicy:
       deadLetterTargetArn: !GetAtt IamRoleWorkerDLQ.Arn
       maxReceiveCount: 4

 IamRoleWorker:
   Type: AWS::Serverless::Function
   Properties:
     CodeUri: ./starfleet/src
     Handler: starfleet.worker_ships.plugins.iam.role_ship.lambda_handler
     Runtime: python3.10
     Architectures:
       - arm64
     MemorySize: 128
     Events:
       SQSEvent:
         Type: SQS
         Properties:
           Queue: !GetAtt IamRoleWorkerQueue.Arn
           BatchSize: 4
     Environment:
       Variables:
         STARFLEET_COMMIT: False
         GIT_PYTHON_REFRESH: quiet  # Iambic
     Policies:
       # Grant permissions to read from the Account Inventory S3 bucket:
       - S3ReadPolicy:
             BucketName: !Ref AccountIndexBucket


# ...
  AssumeRoleManagedPolicy:
    # ...
      Roles:
        - !Ref AccountIndexGeneratorRole  # AccountIndexGeneratorRole is created automatically by SAM and can be referenced
        # ...
        - !Ref IamRoleWorkerRole  # IamRoleWorkerRole is created automatically by SAM and can be referenced

# ...
Outputs:
  # ...
 IamRoleWorkerQueue:
   Description: The Queue URL for the IAM Role Worker invocation queue
   Value: !GetAtt IamRoleWorkerQueue.QueueUrl
 IamRoleWorkerDLQ:
   Description: The Queue URL for the IAM Role Worker invocation DLQ
   Value: !GetAtt IamRoleWorkerDLQ.QueueUrl
 IamRoleWorker:
   Description: The IAM Role Worker ship function that uses iambic to sync IAM roles in our infrastructure
   Value: !GetAtt IamRoleWorker.Arn
```

### Prod Template: Commit
The Prod template and the test template should look exactly the same, except you should set the `STARFLEET_COMMIT` environment variable to `True`.

## The Configuration
The last part of the installation process is to make sure that we have the correct configuration in place. Here is what that would generally look like:

```yaml
IamRoleWorkerShip:
  Enabled: True
  TemplatePrefix: IAM/Roles/  # We recommend this prefix in S3 for your payload templates
  InvocationQueueUrl: https://sqs.YOUR-REGION.amazonaws.com/YOUR-ACCOUNT-ID/starfleet-iam-role-worker
  InvocationSources:
    - EVENTBRIDGE_TIMED_EVENT
    - S3
  EventBridgeTimedFrequency: THIRTY_MIN
  WorkerRoleToAssume: starfleet-worker-basic-test-role  # swap for `starfleet-worker-basic-prod-role` in prod
```

There are 2 fields in the configuration that is defined for this worker:

1. **`WorkerRoleToAssume`** - This is the IAM role that the IAM Role worker needs to assume in all AWS accounts to perform it's job function. If you follow the instructions, this will be `starfleet-worker-basic-test|prod-role` depending on if this is the Test or Prod deployment.
1. **`WorkerRoleSessionName`** - *optional* - this is an optional string for what the assume role session name would be. By default this is `StarfleetIamRoleWorkerShip`.

Once you have all the components all set, you will want to use the SAM CLI to build and deploy everything.

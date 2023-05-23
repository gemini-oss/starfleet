# Installing & Configuring the AWS Config Worker
Installing the Config worker requires the following components:

1. The AWS Config requirements:
    - An IAM role in every AWS account that AWS Config needs to use for describing all your resources. This is not used by Starfleet, this is used by AWS Config itself.
    - An S3 bucket to hold your AWS Config details
1. The Starfleet worker role with permissions to make changes to AWS Config in all your accounts
1. Update to the AWS SAM template to include all the additional components to deploy the worker
1. Updated configuration
1. Payload templates

## AWS Config Requirements
You will need to perform some work that is required for AWS Config to be set up properly to function. You will need the AWS Config role set up everywhere, and also set up an S3 bucket to hold the Config data.

### The AWS Config Role
AWS Config needs to be able to assume an IAM role in your accounts that permit it to describe resources. This role needs to be resident in all accounts, and the role itself is quite simple. This role needs both access to the S3 bucket that holds all the AWS Config details, and permissions to describe the resources that AWS Config monitors. Below is a sample CloudFormation template syntax for this role:

```yaml
AWSConfigRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: config.amazonaws.com
          Action: sts:AssumeRole
          Condition:
            StringEquals:
              AWS:SourceAccount: !Ref 'AWS::AccountId'
    Description: Account-resident role for AWS Config
    RoleName: AWSConfigRole  # Feel free to name this whatever you want
    Policies:
      - Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - s3:GetBucket*
              - s3:ListBucket*
              - s3:PutObject*
            Resource:
              - arn:aws:s3:::YOUR-CONFIG-BUCKET-HERE
              - arn:aws:s3:::YOUR-CONFIG-BUCKET-HERE/*
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AWS_ConfigRole  # Required - this gives AWS Config all the permissions required
```

We recommend creating this as part of a CloudFormation StackSet applied to all accounts in your org (place this in the same template as the Starfleet account resident roles). You will want to have this created in all newly-created accounts in your organization as well. This role leverages the `arn:aws:iam::aws:policy/service-role/AWS_ConfigRole` managed policy to grant AWS Config the required permissions to describe all the resources that it monitors. Feel free to make changes to this as you see fit should you want or need to.

!!! danger "The Root Account"
    Unfortunately, because StackSets doesn't support your organization root account, you either have to make this role in that account, or make a separate CloudFormation stack based on the template above in that account.

!!! note "KMS"
    If you choose to use KMS (we don't recommend using KMS for this purpose; it provides zero security value for this use case), then you will need to make sure that the AWS Config IAM role also has access to the KMS key that is used for encrypting the S3 bucket. We strongly recommend using SSE-S3 instead of KMS for AWS Config.

### The Config S3 Bucket
You will want to follow the AWS Config documentation for setting up an S3 bucket to hold your AWS Config details. This S3 bucket should reside in a security sensitive account and will need to permit AWS Config to access it. The [AWS documentation here](https://docs.aws.amazon.com/config/latest/developerguide/s3-bucket-policy.html) is a good starting point, however, you will want to make your S3 bucket accessible by your organization.

This is a suggested S3 bucket policy:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AWSConfigBucketChecks",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:GetBucketAcl", "s3:ListBucket"],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-HERE",
            "Condition": {
                "StringEquals": {
                    "aws:PrincipalOrgID": "YOUR-ORG-ID"
                },
                "ArnLike": {
                    "aws:PrincipalArn": [
                        "arn:aws:iam::*:role/YOUR-CONFIG-ROLE-ABOVE"
                    ]
                }
            }
        },
        {
            "Sid": "AWSConfigBucketDelivery",
            "Effect": "Allow",
            "Principal": "*",
            "Action": ["s3:PutObject", "s3:PutObjectAcl"],
            "Resource": "arn:aws:s3:::YOUR-BUCKET-HERE/*",
            "Condition": {
                "StringEquals": {
                    "s3:x-amz-acl": "bucket-owner-full-control",
                    "aws:PrincipalOrgID": "YOUR-ORG-ID"
                },
                "ArnLike": {
                    "aws:PrincipalArn": [
                        "arn:aws:iam::*:role/YOUR-CONFIG-ROLE-ABOVE"
                    ]
                }
            }
        }
    ]
}
```

## Update the Starfleet Account-Resident Roles
In the [installation guide](../../installation/IAM.md), we discussed the creation of the Starfleet account resident roles that the workers will assume to perform their tasks. You will need to update these roles with AWS Config permissions. We are going to assume that for Test accounts, you will want read-only permissions, and for Prod accounts, you will want read/write permissions:

### Test Role - Read Only
Add the following to the `starfleet-worker-basic-test-role` permissions:

```yaml
Policies:
  # ...
  - PolicyName: config
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Sid: ReadOnly
          Effect: Allow
          Action:
            - config:Describe*
            - config:Get*
            - config:List*
          Resource: '*'
    # ...
```

### Prod Role - Read/Write
Add the following to the `starfleet-worker-basic-prod-role` permissions:

```yaml
Policies:
  # ...
  - PolicyName: config
    PolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Sid: ReadWrite
          Effect: Allow
          Action: config:*
          Resource: '*'
  - PolicyName: IAM
    PolicyDocument:
      Version: '2012-10-17'
        - Sid: PassRole
          Effect: Allow
          Action: iam:PassRole
          Resource:
            - arn:aws:iam::*:role/AWSConfigRole  # The name of your Config role above
```

For production, you will need the `iam:PassRole` permissions since the worker will be informing Config on which IAM role to make use of.

## AWS SAM Template
For the AWS SAM template, you will need to add in this worker's components to it. The templates for testing and production are mostly the same. The only difference is that for production, we operate off of a larger batch size to reduce costs, increase the RAM amount, and have the `STARFLEET_COMMIT` environment variable set to `True`.

!!! tip
    We have included the below SAM details in the `test_sam_template.yaml` file that is included with this repo. All you need to do is uncomment the sections labeled `Uncomment for the AWS Config worker` with the details outlined.

### Test Template: No Commit
Here is a sample of what should be in your test template:

```yaml
Resources:
  # ...

  AWSConfigWorkerDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-aws-config-worker-dlq
      RedriveAllowPolicy:
        redrivePermission: allowAll

  AWSConfigWorkerQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-aws-config-worker
      VisibilityTimeout: 300  # This needs to be the same as the Lambda function timeout.
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt AWSConfigWorkerDLQ.Arn
        maxReceiveCount: 4

  AWSConfigWorker:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./src
      Handler: starfleet.worker_ships.plugins.aws_config.ship.lambda_handler
      Runtime: python3.10
      Architectures:
        - arm64
      MemorySize: 128
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt AWSConfigWorkerQueue.Arn
            BatchSize: 2
      Environment:
        Variables:
          STARFLEET_COMMIT: False
      Policies:
        # Grant permissions to read from the inventory S3 bucket:
        - S3ReadPolicy:
            BucketName: !FindInMap
              - EnvMap
              - !Ref 'EnvironmentName'
              - AccountInventoryBucket

# ...
  AssumeRoleManagedPolicy:
    # ...
      Roles:
        - !Ref AccountIndexGeneratorRole  # AccountIndexGeneratorRole is created automatically by SAM and can be referenced
        - !Ref AWSConfigWorkerRole  # AWSConfigWorkerRole is created automatically by SAM and can be referenced

# ...
Outputs:
  # ...
  AWSConfigWorkerQueue:
    Description: The Queue URL for the AWS Config Worker invocation queue
    Value: !GetAtt AWSConfigWorkerQueue.QueueUrl
  AWSConfigWorkerDLQ:
    Description: The Queue URL for the AWS Config Worker invocation DLQ
    Value: !GetAtt AWSConfigWorkerDLQ.QueueUrl
  AWSConfigWorker:
    Description: The AWS Config Worker ship function that enables AWS Config everywhere
    Value: !GetAtt AWSConfigWorker.Arn
```

### Prod Template: Commit
Here is a sample of what should be in your prod template:

```yaml
Resources:

  # ...
  AWSConfigWorkerDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-aws-config-worker-dlq
      RedriveAllowPolicy:
        redrivePermission: allowAll

  AWSConfigWorkerQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: starfleet-aws-config-worker
      VisibilityTimeout: 300  # This needs to be the same as the Lambda function timeout.
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt StarbaseFanoutDLQ.Arn
        maxReceiveCount: 4

  AWSConfigWorker:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./starfleet/src
      Handler: starfleet.worker_ships.plugins.aws_config.ship.lambda_handler
      Runtime: python3.10
      Architectures:
        - arm64
      MemorySize: 256
      Events:
        SQSEvent:
          Type: SQS
          Properties:
            Queue: !GetAtt AWSConfigWorkerQueue.Arn
            BatchSize: 4
      Environment:
        Variables:
          STARFLEET_COMMIT: True
      Policies:
        # Grant permissions to read from the inventory S3 bucket:
        - S3ReadPolicy:
            BucketName: !FindInMap
              - EnvMap
              - !Ref 'EnvironmentName'
              - AccountInventoryBucket

# ...
  AssumeRoleManagedPolicy:
    # ...
      Roles:
        - !Ref AccountIndexGeneratorRole  # AccountIndexGeneratorRole is created automatically by SAM and can be referenced
        - !Ref AWSConfigWorkerRole  # AWSConfigWorkerRole is created automatically by SAM and can be referenced

# ...
Outputs:
  # ...
  AWSConfigWorkerQueue:
    Description: The Queue URL for the AWS Config Worker invocation queue
    Value: !GetAtt AWSConfigWorkerQueue.QueueUrl
  AWSConfigWorkerDLQ:
    Description: The Queue URL for the AWS Config Worker invocation DLQ
    Value: !GetAtt AWSConfigWorkerDLQ.QueueUrl
  AWSConfigWorker:
    Description: The AWS Config Worker ship function that enables AWS Config everywhere
    Value: !GetAtt AWSConfigWorker.Arn
```

## The Configuration
The last part of the installation process is to make sure that we have the correct configuration in place. Here is what that would generally look like:

```yaml
AwsConfigWorkerShip:
  Enabled: True
  TemplatePrefix: AwsConfigWorkerShip/
  InvocationQueueUrl: https://sqs.us-east-2.amazonaws.com/YOUR-ACCOUNT-ID/starfleet-aws-config-worker
  InvocationSources:
    - EVENTBRIDGE_TIMED_EVENT
    - S3
  EventBridgeTimedFrequency: SIX_HOURLY  # Feel free to alter this
  WorkerRoleToAssume: starfleet-worker-basic-test-role  # for test -- in PROD, make this starfleet-worker-basic-prod-role
```

There are 2 fields in the configuration that is defined for this worker:

1. **`WorkerRoleToAssume`** - This is the IAM role that the AWS Config Worker needs to assume in all AWS accounts to perform it's job function. If you follow the instructions, this will be `starfleet-worker-basic-test|prod-role` depending on if this is the Test or Prod deployment.
1. **`WorkerRoleSessionName`** - *optional* - this is an optional string for what the assume role session name would be. By default this is `StarfleetAwsConfigWorkerShip`.

Once you have all the components all set, you will want to use the SAM CLI to build and deploy everything.

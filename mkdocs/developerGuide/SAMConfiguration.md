# AWS SAM Configuration

Last but certainly not least is the AWS SAM specification. We provide a sample AWS SAM template to make things easy to deploy. We recommend setting up ECR to have a Dockerized Lambda function since the Starfleet dependencies may blow past the Lambda filesize limit. All examples below assume we are using ECR.

At a minimum, you'll need to have a defined Lambda function, IAM permissions (typically to assume a role -- with a target role that permits the access), and that's basically it.

The `AccountIndexGeneratorShip` is always a great example:

```yaml
# The DLQ:
AccountIndexGeneratorDLQ:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: starfleet-account-index-generator-dlq
    RedriveAllowPolicy:
      redrivePermission: allowAll

# The main event SQS Queue
AccountIndexGeneratorQueue:
  Type: AWS::SQS::Queue
  Properties:
    QueueName: starfleet-account-index-generator
    VisibilityTimeout: 300  # This needs to be the same as the Lambda function timeout.
    RedrivePolicy:
      deadLetterTargetArn: !GetAtt AccountIndexGeneratorDLQ.Arn
      maxReceiveCount: 4

# The Lambda function:
AccountIndexGenerator:
  Type: AWS::Serverless::Function
  Metadata:
    DockerTag: starfleet
    DockerContext: ./
    Dockerfile: Dockerfile
  Properties:
    PackageType: Image
    ImageConfig:
      Command:
        - starfleet.worker_ships.plugins.account_index_generator.ship.lambda_handler
    Architectures:
      - arm64
    MemorySize: 256
    Events:
      SQSEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt AccountIndexGeneratorQueue.Arn
          BatchSize: 2
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
      - S3WritePolicy:
          BucketName: !FindInMap
            - EnvMap
            - !Ref 'EnvironmentName'
            - AccountInventoryBucket

# ...

# Finally, the Starbase Fanout Function:
StarbaseFanoutFunction:
  Type: AWS::Serverless::Function
  DependsOn:
    - AccountIndexGeneratorQueue
  Metadata:
    DockerTag: starfleet
    DockerContext: ./
    Dockerfile: Dockerfile
  Properties:
    PackageType: Image
    ImageConfig:
      Command:
        - starfleet.starbase.entrypoints.fanout_payload_lambda_handler
    Architectures:
      - arm64
    Events:
      # Make one for each timed event:
      SQSEvent:
        Type: SQS
        Properties:
          Queue: !GetAtt StarbaseFanoutQueue.Arn
          BatchSize: 1  # Important! We only want 1 to ensure we don't hit timeouts.
    Policies:
      # Grant permissions to read from the Template S3 bucket:
      - S3ReadPolicy:
          BucketName: !Ref StarfleetTemplateBucket
      - SQSSendMessagePolicy:
          QueueName: !GetAtt AccountIndexGeneratorQueue.QueueName

# Common worker ship components here:
AssumeRoleManagedPolicy:
  Type: AWS::IAM::ManagedPolicy
  DependsOn:
    - AccountIndexGenerator
  Properties:
    Description: Grants Starfleet workers assume role permissions to common Starfleet worker IAM roles
    ManagedPolicyName: StarfleetWorkerAssumeRoles
    PolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Action: 'sts:AssumeRole'
          Resource:
            - !Sub
              - 'arn:aws:iam::*:role/${RoleName}'
              - RoleName: !FindInMap
                  - EnvMap
                  - !Ref 'EnvironmentName'
                  - BaseRoleName
    Roles:
      - !Ref AccountIndexGeneratorRole  # AccountIndexGeneratorRole is created automatically by SAM and can be referenced
```

Some important things to note are:

- We set the `STARFLEET_COMMIT` environment variable to True, which in the case of the `AccountIndexGeneratorShip` will result in it writing to the S3 buckets that are permitted in the policies section (we use a map and define TEST and PROD S3 buckets -- see `test_sam_template.yaml` in the code for more details)
- We always have an SQS queue and corresponding DLQ
- The Starbase fan out Lambda function needs to be able to publish events onto the worker's main event queue
- We made a sample managed policy for role assumption and we attach it to the worker's IAM role (this is automatically generated; it's the name of the YAML dictionary name, followed by `Role`.
  - So for the `AccountIndexGeneratorShip`, SAM will make an IAM role named `AccountIndexGeneratorRole`

!!! note
    The Queue URL of the main event Queue as shown above needs to be in the configuration for the worker.

## SAM Config
We strongly recommend that you make a SAM configuration environment (`samconfig.toml`) that sets up the SAM S3 bucket and all the build details required. We include an example [`samconfig.toml`](https://github.com/gemini-oss/starfleet/blob/main/samconfig.toml), which is pasted below:

```toml
version = 0.1
[TEST]
[TEST.deploy]
[TEST.deploy.parameters]
stack_name = "starfleet"
s3_bucket = "REPLACE-ME"  # The SAM CLI will generate this with a "guided" deploy option -- or you can just make this yourself.
s3_prefix = "starfleet"
region = "REPLACEME"
confirm_changeset = true
capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]  # Important -- you need these capabilities defined since this creates IAM roles
parameter_overrides = "EnvironmentName=\"TEST\""
image_repository = "REPLACE ME - IF YOU ARE  NOT USING ECR DELETE THIS LINE"

[TEST.validate.parameters]
region = "REPLACEME"
lint = true

[TEST.build.parameters]
use_container = true
template_file = "test_sam_template.yaml"  # Feel free to replace with your own filename


[PROD]
[PROD.deploy]
[PROD.deploy.parameters]
stack_name = "starfleet"
s3_bucket = "REPLACE-ME"  # The SAM CLI will generate this with a "guided" deploy option -- or you can just make this yourself.
s3_prefix = "starfleet"
region = "REPLACEME"
confirm_changeset = true
capabilities = ["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"]  # Important -- you need these capabilities defined since this creates IAM roles
parameter_overrides = "EnvironmentName=\"PROD\""
image_repository = "REPLACE ME - IF YOU ARE  NOT USING ECR DELETE THIS LINE"

[PROD.validate.parameters]
region = "REPLACEME"
lint = true

[PROD.build.parameters]
use_container = true
template_file = "prod_sam_template.yaml"  # Feel free to replace with your own filename
```

With a `samconfig.toml` like that you can then run `sam build --config-env TEST` to build your test Starfleet deployment and `sam deploy --config-env TEST` to deploy it. Swap out `TEST` with `PROD` for your production build and deployment.

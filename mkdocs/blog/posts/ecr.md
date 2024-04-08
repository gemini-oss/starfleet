---
date: 2024-04-08
authors:
  - mikegrima
categories:
  - General Announcement
---

# ECR/Dockerized Lambda Support
We made a small update to the docs to highlight deploying Starfleet with a Dockerized Lambda. This was necessary as Starfleet's dependencies made it larger than the `.zip` file size limit for Lambda.

The main steps to convert to this from a non-ECR set up is to:

1. Create the Private ECR repo in the same account/region you have Starfleet deployed in.
2. Update the `samconfig.toml` file.
3. Update the SAM template.
4. Re-build and deploy.

The Dockerized Lambda is built with the included `Dockerfile`, which should have everything needed and ready to go. You can test that the container builds by running `docker build .` from within the Starfleet directory.

## Update SAM Config
Once you create your ECR Repo, you then need to update your `samconfig.toml` file to include the line:
```
image_repository = "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/REPONAME"
```
... under your `.deploy.parameters` sections.

## Update your SAM Template
The SAM template also needs to be updated. Included now are 2 sample SAM Templates: `test_sam_template.yaml`, which is the ECR sample template, and `test_sam_template_NO_ECR.yaml`, which is the original non-ECR version.

You would need to update all the function entires to change it from:
```yaml
  StarbaseEventBridgeFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: ./src
      Handler: starfleet.starbase.entrypoints.eventbridge_timed_lambda_handler
      Runtime: python3.12
```
over to:

```yaml
  StarbaseEventBridgeFunction:
    Type: AWS::Serverless::Function
    Metadata:
      DockerTag: starfleet
      DockerContext: ./
      Dockerfile: Dockerfile
    Properties:
      PackageType: Image
      ImageConfig:
        Command:
          - starfleet.starbase.entrypoints.eventbridge_timed_lambda_handler
```

Update all the Lambda definitions to include the `Metadata` section as shown above (this is the same for all the functions) and update the `Properties` section to have the fields above. Remove the old fields. Note: the `Command` field is where you place the Lambda handler path - this is unique to each Lambda function.

For more information see [the ECR setup documentation](../../installation/SetupECR.md) and also [AWS's documentation here](https://docs.aws.amazon.com/AmazonECR/latest/userguide/repository-create.html).

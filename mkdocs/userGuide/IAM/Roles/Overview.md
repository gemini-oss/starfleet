# Starfleet IAM Role Worker
This is the main user guide for the IAM Role Worker ship.

## What does it do?
This is a Starfleet worker that makes it possible to sync IAM roles across all accounts in your infrastructure with both drift detection and prevention. This worker wraps the excellent [IAMbic](https://iambic.org/) library to perform the heavy lifting of the actual IAM work. If you haven't checked out [IAMbic](https://iambic.org) yet, please take a look at it. It's a full-featured IaC that unifies IAM management across the AWS world (and other identity providers) with lots of features and capabilities.

The long and short of it is that this worker embeds an [IAMbic IAM role template](https://docs.iambic.org/reference/schemas/aws_iam_role_template) within a Starfleet template to leverage Starfleet's account tasking capabilities to have IAMbic sync a role where you need it and how you need it configured.

Please familiarize yourself with the [IAMbic IAM role template schema](https://docs.iambic.org/reference/schemas/aws_iam_role_template), as that is used here.

## What does it NOT do?
This only syncs IAM roles, it does not sync the other IAM primitives. We may consider adding additional IAM capabilities in the future. This also does not support all of the IAMbic capabilities, but does support the majority of the IAM capabilities. That is detailed more below.

## How it works
The long and the short of it, we are simply embedding an IAMbic template within a Starfleet template. Starfleet performs the heavy lifting of tasking worker lambdas with the AWS account context to operate in. Starfleet then embeds the current account context within the IAMbic template that gets passed into the IAMbic library to sync the role.

Here is a sample role template:

```yaml
TemplateName: DevOpsAutomationRole
TemplateDescription: This is a role for DevOps automation to do DevOps things
IncludeAccounts:
  ByNames:
    - DevOpsTest
    - DevOpsProd
IambicRoleTemplate:  # <----- The IAMbic template gets embedded into here
  properties:
    role_name: DevOpsAutomationRole
    description: 'The DevOpsRole for DevOpsAutomation in {{ var.account_name }}'
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            service: ec2.amazonaws.com
      version: '2012-10-17'
    managed_policies:
      - policy_arn: arn:aws:iam::aws:policy/ReadOnlyAccess
    inline_policies:
      - policy_name: DevOpsThings
        statement:
          - sid: DevOpsThings
            effect: Allow
            action:
              - ec2:*
              - elasticloadbalancing:*
              - iam:PassRole
            resource: '*'
            version: '2012-10-17'

      # Give the DevOpsTest account access to the DevOpsTest S3 Bucket:
      - StarfleetIncludeAccounts:
          ByNames:
            - DevOpsTest
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopstest
              - aws:s3:::some-devops-bucket-devopstest/*
        version: '2012-10-17'

      # Give the DevOpsProd account access to the DevOpsProd S3 Bucket:
      - StarfleetIncludeAccounts:
          ByNames:
            - DevOpsProd
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopsprod
              - aws:s3:::some-devops-bucket-devopsprod/*
        version: '2012-10-17'
```

## What is different between this and vanilla IAMbic?
Starfleet is simply wrapping the IAMbic library so that you use Starfleet instead of vanilla IAMbic. The primary benefit is that if you are already using Starfleet, then you can start rolling out IAM roles where you need it with drift prevention. You just need to familiarize yourself with the IAMbic template format to begin using it.

### Caveats
There are some caveats between using the Starfleet IAM worker vs. vanilla IAMbic. All of the IAMbic specific syntax around account inclusion/exclusion is replaced with Starfleet's account resolution capabilities. Also, the expiration capability is not yet supported.

For example, instead of:

```yaml
   #...
      - included_accounts:
          - DevOpsProd
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopsprod
              - aws:s3:::some-devops-bucket-devopsprod/*
  # ...
```

You would use:
```yaml
  # ...
      # This uses the same syntax as other Starfleet templates. Simply swap `included/excluded_accounts` with `StarfleetInclude/ExcludeAccounts`
      - StarfleetIncludeAccounts:
          ByNames:
            - DevOpsProd
        policy_name: ArtifactBucket
        statement:
          - effect: allow
            action:
              - s3:Get*
              - s3:List*
              - s3:PutObject
            resource:
              - aws:s3:::some-devops-bucket-devopsprod
              - aws:s3:::some-devops-bucket-devopsprod/*
  # ...
```

Starfleet will render out the IAMbic templates with the proper account IDs and pass that onto IAMbic to complete the work.

## Alerting
The IAM Role Worker supports alerts to Slack. It will emit alerts regarding the changes that IAMbic made to the given role in the AWS account in question.

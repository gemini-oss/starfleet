# IAM Role Worker Templates
In this section, we discuss the IAM Role worker templates. The IAM Role worker is an `ACCOUNT` worker, and thus relies on the base account template components [that is discussed here](../../../architecture/PayloadTemplates.md#account-worker-templates). In addition to the base account details, there are some unique fields defined below:

## Template Schema
The IAM Role worker leverages the [IAMbic library](https://iambic.org) for syncing IAM roles. An [IAMbic IAM role template](https://docs.iambic.org/reference/schemas/aws_iam_role_template) is wrapped withing a Starfleet template. Most of the capabilities are supported, but there are some caveats as some features are not supported and for other features, you need to use Starfleet primitives instead.

Below is a sample template:

```yaml
TemplateName: SomeSampleRole
TemplateDescription: This is a sample role that is rolled out by Starfleet and IAMbic
IncludeAccounts:
  ByNames:
    - DevOpsTest
    - DevOpsProd
IambicVariables:
  - Key: some_key
    Value: some_value
IambicRoleTemplate:
  properties:
    role_name: some_sample_role
    description: A sample role that will be rolled out to {{ var.account_name }} with {{ var.some_key }} set
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            service: ec2.amazonaws.com
      version: '2012-10-17'
    managed_policies:
      - policy_arn: arn:aws:iam::aws:policy/IAMReadOnlyAccess  # Grant read-only access to IAM
    inline_policies:
      - StarfleetIncludeAccounts:  # In DevOpsTest, grant access to the test S3 bucket
          ByNames:
            - DevOpsTest
        policy_name: s3
        statement:
          - effect: Allow
            action:
              - s3:List*
              - s3:Get*
              - s3:PutObject
              - s3:DeleteObject
            resource:
              - arn:aws:s3:::devops-test-bucket
              - arn:aws:s3:::devops-test-bucket/*
        version: '2012-10-17'
      - StarfleetIncludeAccounts:  # In DevOpsProd, grant access to the prod S3 bucket
          ByNames:
            - DevOpsProd
        policy_name: s3
        statement:
          - effect: Allow
            action:
              - s3:List*
              - s3:Get*
              - s3:PutObject
              - s3:DeleteObject
            resource:
              - arn:aws:s3:::devops-prod-bucket
              - arn:aws:s3:::devops-prod-bucket/*
        version: '2012-10-17'
    tags:
      - key: jira
        value: DEVOPS-01
```

In the example above, the role deployed to the `DevOpsTest` account will get a different `s3` policy than the role deployed to the `DevOpsProd` account.

## Components
There are only 2 high level fields and they are defined as:

1. **`IambicVariables`** - Optional List of Dictionaries - This is for [defining variables](https://docs.iambic.org/reference/schemas/variable) that you want IAMbic to reference throughout the template. These are just `Key` and `Value` pairs.
1. **`IambicRoleTemplate`** - Dictionary - This is the embedded IAMbic template with some fields removed. More on that below.

## Account Inclusion and Exclusion
IAMBic has it's own primitives for declaring which accounts to include or exclude. When Starfleet renders the IAMbic template it adds these in. As such, instead of using the IAMbic `included_accounts`, `excluded_accounts`, `included_orgs`, `excluded_orgs`, you will want to use:

1. **`StarfleetIncludeAccounts`** - This is the exact same schema as `IncludeAccounts` in the [primary template](../../../architecture/PayloadTemplates.md#account-worker-templates). It works the exact same way an uses the exact same account resolution capabilities.
1. **`StarfleetExcludeAccounts`** - This is the exact same schema as `ExcludeAccounts` in the [primary template](../../../architecture/PayloadTemplates.md#account-worker-templates). It works the exact same way an uses the exact same account resolution capabilities.

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

## Unsupported and Forbidden Fields
Because Starfleet is wrapping IAMbic, Starfleet is deciding which fields are allowed (or not allowed) to appear in the IAMbic template. The following are the fields that you cannot use:

```yaml
- included_accounts  # Use StarfleetIncludeAccounts
- excluded_accounts  # Use StarfleetExcludeAccounts
- included_orgs  # Use StarfleetIncludeAccounts
- excluded_orgs  # Use StarfleetExcludeAccounts
- iambic_managed  # This is managed by Starfleet
```

If you have an IAMbic template, you'll need to strip out and/or swap (`include/exclude`) with the proper values.

Also, at this time, Starfleet does not support the vanilla `expires_at` field. We have [an open issue](https://github.com/gemini-oss/starfleet/issues/64) to address this in the future.

## Some Examples
Here is an example of an IAM role that should be deployed in each and every account, including the organization management account:

```yaml
TemplateName: DeployEverywhere
TemplateDescription: This is a sample role that is in all the accounts
IncludeAccounts:
  AllAccounts: True
OperateInOrgRoot: True
IambicVariables:
  - Key: some_key
    Value: some_value
IambicRoleTemplate:
  properties:
    role_name: deploy_everywhere
    description: A sample role that will be rolled out to {{ var.account_name }} with {{ var.some_key }} set
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            aws: arn:aws:iam::000000000000:role/some-imaginary-role
      version: '2012-10-17'
    managed_policies:
      - policy_arn: arn:aws:iam::aws:policy/IAMReadOnlyAccess  # Grant read-only access to IAM
```

Here is that same example above, but this time, we will exclude the `IAMReadOnlyAccess` managed policy in the `DevOpsProd` account:
```yaml
TemplateName: DeployEverywhere
TemplateDescription: This is a sample role that is in all the accounts
IncludeAccounts:
  AllAccounts: True
OperateInOrgRoot: True
IambicVariables:
  - Key: some_key
    Value: some_value
IambicRoleTemplate:
  properties:
    role_name: deploy_everywhere
    description: A sample role that will be rolled out to {{ var.account_name }} with {{ var.some_key }} set
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            aws: arn:aws:iam::000000000000:role/some-imaginary-role
      version: '2012-10-17'
    managed_policies:
      - StarfleetExcludeAccounts:
          ByNames:
            - DevOpsProd
        policy_arn: arn:aws:iam::aws:policy/IAMReadOnlyAccess  # Grant read-only access to IAM for all accounts except DevOpsProd
```

Here is that same example above, but this time, we are going to include the ability to create S3 buckets in the `DevOps` organization unit:
```yaml
TemplateName: DeployEverywhere
TemplateDescription: This is a sample role that is in all the accounts
IncludeAccounts:
  AllAccounts: True
OperateInOrgRoot: True
IambicVariables:
  - Key: some_key
    Value: some_value
IambicRoleTemplate:
  properties:
    role_name: deploy_everywhere
    description: A sample role that will be rolled out to {{ var.account_name }} with {{ var.some_key }} set
    assume_role_policy_document:
      statement:
        - action: sts:AssumeRole
          effect: Allow
          principal:
            aws: arn:aws:iam::000000000000:role/some-imaginary-role
      version: '2012-10-17'
    managed_policies:
      - StarfleetExcludeAccounts:
          ByNames:
            - DevOpsProd
        policy_arn: arn:aws:iam::aws:policy/IAMReadOnlyAccess  # Grant read-only access to IAM for all accounts except DevOpsProd
    inline_policies:
      - StarfleetIncludeAccounts:  # Only allow S3 bucket creation in the DevOps organization unit
          ByOrgUnits:
            - DevOps
        policy_name: CreateBuckets
        statement:
          - effect: allow
            action: s3:CreateBucket
            resource: '*'
```

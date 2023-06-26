# AWS Config Worker Templates
In this section, we discuss the AWS Config worker templates. The Config Worker is an `ACCOUNT_REGION` worker, and thus relies on the base account/region template components [that is discussed here](../../architecture/PayloadTemplates.md#account-region-worker-templates). In addition to the base account/region details, there are some unique fields defined below:

## Template Schema
The only required field is a very important one and that is the `DefaultConfiguration` section. Below is a sample template where this is defined:

!!! warning "Schema Change June 2023"
    The initial schema for this worker was changed in June 2023 to introduce support for AWS Config's resource
    exclusion feature in the recorders. The original schema is no longer functional. The main change is in the `RecordingGroup` section, which is defined
    in detail below.

Below is the most realistic example. We are not going to record EC2 instances anywhere because in this sample environment, they change too much and are too costly to have recorded.
Thus, by default, we are recording all resources except EC2 instances and global resources like IAM. For IAM and other global resources, we only want to record them in us-east-1
to avoid duplicate resource recording and the associated costs with that.

```yaml
TemplateName: AWSConfigEnablement
TemplateDescription: Enabling AWS Config
IncludeAccounts:
    AllAccounts: True
OperateInOrgRoot: True
IncludeRegions:
    - ALL
DefaultConfiguration:
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordEverythingExcept:
                - AWS::EC2::Instance
                - AWS::IAM::Role    # Record IAM in us-east-1 only -- see below
                - AWS::IAM::Group
                - AWS::IAM::User
    RetentionPeriodInDays: 2557
AccountOverrideConfigurations:
    -
        IncludeAccounts:
            AllAccounts: True
        IncludeRegions:
            - us-east-1
        DeliveryChannelDetails:
            BucketName: your-s3-bucket-here
            S3DeliveryFrequency: Twelve_Hours
        RecorderConfiguration:
            ConfigRoleName: AWSConfigRole
            RecordingEnabled: True
            RecordingGroup:
                RecordEverythingExcept:  # IAM will only be in us-east-1 to avoid recording global resources as they would be duplicated and increase recording cost
                    - AWS::EC2::Instance
        RetentionPeriodInDays: 2557
```

The `DefaultConfiguration` defines how AWS Config should be configured by default. That is to say, how it should be configured for all non-excluded (__and__ not overridden -- see next section) `IncludeAccounts` and `IncludeRegions` that the worker is tasked for. This outlines how we need to configure each component.

There are 3 major components of the `DefaultConfiguration`. Each section is then defined in more detail below with examples.

1. **`RecorderConfiguration`** - This defines how the in-account/region AWS Config recorder is configured. This specifies whether the recorder is enabled, and which resource types to record for, to name a few.
1. **`DeliveryChannelDetails`** - This defines the delivery channel. This is where you set the S3 bucket properties (and optionally SNS topic details).
1. **`RetentionPeriodInDays`** - This defines how long AWS config should retain configuration change data. The maximum value is 7 years including leap days (2557 days). We require this to be set. The minimum value is 30 days.

### `RecorderConfiguration`
The `RecorderConfiguration` section has the following fields (if not specified as optional, it's required):

1. `ConfigRoleName` - This is the name of the IAM role that AWS Config will use to describe resources in your account. If you followed the instructions on the previous page, this would be `AWSConfigRole`.
1. `RecordingEnabled` - Boolean that indicates if the recorder should be enabled or not
1. `RecordingGroup` - Dictionary that defines the `RecordingGroup` section.
1. `PreferredName` - *optional* - This is a preferred name that you want to have set for the Config recorder. By default, this is set to `default`. *Note:* Starfleet cannot rename an existing named recorder. Starfleet will use whatever existing recorder is present and update it to conform to the spec. More details on this is below.

The `RecordingGroup` is defined as:

1. `RecordEverything` - This is used if you want to record ALL AWS Config supported resources, including any new ones that get introduced. This is a dictionary - see more below.
1. `RecordSpecificResources` - This is an enumerated list of AWS resources that you want to record
1. `RecordEverythingExcept` - This is an enumerated list of AWS resources that you *don't* want to record. All other resource types are recorded including any new ones that AWS Config supports in the future.

#### The `RecordingGroup` details
The `RecordingGroup` allows you to specify which resources to record (or not record). There are 3 possible values (stated above: `RecordEverything`, `RecordSpecificResources`, or `RecordEverythingExcept`)
that this can have. You can only define 1 of these.

##### RECOMMENDED: Record all resources except for specific resources
If you want to record all resources except for specific resources, then the schema for that looks like this:

```yaml
RecordingGroup:
    RecordEverythingExcept:
        - AWS::EC2::Instance
        - AWS::EC2::Volume
        - AWS::EC2::NetworkInterface
```

We recommend this approach since it will record all resources except for the ones you specify. This is useful to avoid recording resources that change a lot, since that can jack up your AWS Config bill.
This allows you to record all the resources that don't excessively change a lot in your environment, which gives you the benefit of being able to track changes for the majority of your resources while keeping your bill in check.
In the example above, we will record all resources except for EC2 Instances, EBS Volumes, and ENIs.

We would also recommend having an override region where you do track the globals in.

##### Record specific resources
If you want to record specific resources, then the schema for that looks like this:

```yaml
RecordingGroup:
    RecordSpecificResources:
        - AWS::IAM::Role
        - AWS::IAM::Group
        - AWS::S3::Bucket
```

In this example, this will record only the resources specified, which in this case, are IAM Roles, IAM Groups, and S3 Buckets.

##### Record ALL AWS Config supported resources
If you want to record ALL resources, then the schema for that looks like this:

```yaml
RecordingGroup:
    RecordEverything:
        RecordGlobalsInTheseRegions:
            - us-east-1
```

Under `RecordEverything` there is list called `RecordGlobalsInTheseRegions`. This is a list of regions that you want to record global resources in. There are 3 possible values for this:

1. `- ALL` - If you want to record global resource types in all regions, then you can set this list to one item with the value of `- ALL`. This is not recommended since it will duplicate the recorded global resources in all the regions. This can result in a higher AWS Config bill.
1. `- NONE` - If you do not want to record global resource types in any region, then you can set this list to one item with the value of `- NONE`. This is not recommended since you will definitely want to record things like IAM, which is global.
1. A list of regions - If you want to record global resource types in a specific region, then you can set this list to any number of supported AWS Config regions.

*Examples for all resources:*

Record all resources including global resources in all regions:
```yaml
RecordingGroup:
    RecordEverything:
        RecordGlobalsInTheseRegions:
            - ALL
```

All resources except for global resources (i.e. don't record global resources anywhere):
```yaml
RecordingGroup:
    RecordEverything:
        RecordGlobalsInTheseRegions:
            - NONE
```

All resources, but only record global resources in `us-east-1` and `us-west-2`:
```yaml
RecordingGroup:
    RecordEverything:
        RecordGlobalsInTheseRegions:
            - us-east-1
            - us-west-2
```

### `DeliveryChannelDetails`
The `DeliveryChannelDetails` section defines how the delivery channel should be configured. The following fields are present (if not specified as optional, it's required):

1. `BucketName` - This is the name of the S3 bucket that AWS Config needs to have configured. This was discussed on the previous page.
1. `S3DeliveryFrequency` - An enumerated string for the frequency of when AWS Config should deliver data to the S3 bucket. The following are the valid values:
  ```
  One_Hour
  Three_Hours
  Six_Hours
  Twelve_Hours
  TwentyFour_Hours
  ```
1. `PreferredName` - *optional* - This is a preferred name that you want to have set for the Delivery Channel. By default, this is set to `default`. *Note:* Starfleet cannot rename an existing named delivery channel. Starfleet will use whatever existing delivery channel is present and update it to conform to the spec. More details on this is below.
1. `BucketKeyPrefix` - *optional* - This is the optional prefix in the S3 bucket that AWS Config should dump the data under. By default this is not set and is placed where AWS Config would by default place it. See the AWS Config documentation for where that is.
1. `S3KmsKeyArn` - *maybe optional* - If you are using KMS with S3 to encrypt your S3 data, then you need to specify the KMS Key ARN here. This is REQUIRED if you use KMS with S3, otherwise this should not be set.
1. `SnsTopicArn` - *optional* - This is the optional SNS topic to send notifications to whenever configuration changes are recorded. If you don't want to use this, then don't set this. See the AWS documentation for details on how this works and what it does.

### `RetentionConfigInDays`
This is documented above. Basically, this is how long (in days) that AWS Config should retain configuration history. The maximum value is 2557 days, the minimum is 30. This field is required.

## Overriding Account Defaults
We provide you the ability to provide Account/Region level overrides. This is useful if you need to opt-out or opt-in resource level configurations for a given set of accounts.
This is set via the *OPTIONAL* `AccountOverrideConfigurations` field. The `AccountOverrideConfigurations` is a list of all the items in the `DefaultConfiguration` schema but also has the ability to specify the account and region to run in.

Here is an example of what a full template with this would look like:

```yaml
TemplateName: AWSConfigEnablement
TemplateDescription: Enabling AWS Config
IncludeAccounts:
    AllAccounts: True
OperateInOrgRoot: True
IncludeRegions:
    - ALL
DefaultConfiguration:
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordEverything:
                RecordGlobalsInTheseRegions:
                    - us-east-1
    RetentionPeriodInDays: 2557
AccountOverrideConfigurations:
    -
        IncludeAccounts:
            ByNames:
                - 'Account One'
        IncludeRegions:
            - us-west-2
        DeliveryChannelDetails:
            BucketName: some-other-bucket
            BucketKeyPrefix: some/prefix/
            S3DeliveryFrequency: TwentyFour_Hours
            S3KmsKeyArn: arn:aws:kms:us-west-1:000000000001:key/1234-1445-1919232
            SnsTopicArn: arn:aws:sns:us-west-1:000000000001:topic/sometopic
            PreferredName: overridden
        RecorderConfiguration:
            PreferredName: overridden
            ConfigRoleName: SomeOtherRole
            RecordingEnabled: True
            RecordingGroup:
                RecordSpecificResources:
                    - AWS::S3::Bucket
                    - AWS::EC2::SecurityGroup
        RetentionPeriodInDays: 30
```

With the above template, when running in `Account One`/us-west-2 it will not use the `DefaultConfiguration`, it will instead use the overridden configuration. Here are the additional fields for account and regional specificity:

1. `IncludeAccounts` - Required - the accounts to override
1. `IncludeRegions` - Required - the regions to override
1. `ExcludeAccounts` - *optional* - The accounts to explicitly not apply the override to
1. `ExcludeRegions` - *optional* - The regions to explicitly not apply the override to

This is the same exact schema component that is used for the `ACCOUNT_REGION` worker base template as [documented here](../../architecture/PayloadTemplates.md#account-region-worker-templates). Everything else about this is the same as for the `DefaultConfiguration`.

!!! warning "Overlapping"
    The worker will check for overlapping Account/Region overrides. If one is located then it will raise an error and fail to apply the template.

If no overrides are found for an account/region pair, then the `DefaultConfiguration` is applied.

## Special Details
This section outlines some special details regarding the worker's behavior.

1. As mentioned above, `PreferredName` is a field that will _opportunistically_ set a name for a recorder or delivery channel if the field is set, _and_ there isn't already a recorder or delivery channel present. AWS Config does not allow you to update this field. To update the field, you need to delete the recorder or delivery channel and re-create it. Starfleet will not delete the recorder or delivery channel, and instead will find the one that is there and update it to conform to the rest of the spec.
1. A quick note is that when thinking about how this template is applied, you should think of it as the main template's `Include/Exclude` mostly applies to the `DefaultConfiguration`. Overrides are there to provide exceptions in specific accounts/regions under the main `Include*`. You can always create multiple templates and store them in the template S3 bucket path (default path is `AwsConfigWorker/`), however, we would recommend that you use just 1 template so everything is in one place.

## Some examples
The most realistic example is at the top. This section shows other examples you may or may not care about.

This is an example template that will enable AWS Config to all accounts and regions, including the Organization root, for all regions, for all resource types. Global resources will only be recorded in us-east-1:

```yaml
TemplateName: AWSConfigEnablement
TemplateDescription: Enabling AWS Config
IncludeAccounts:
    AllAccounts: True
OperateInOrgRoot: True
IncludeRegions:
    - ALL
DefaultConfiguration:
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordEverything:
                RecordGlobalsInTheseRegions:
                    - us-east-1
    RetentionPeriodInDays: 2557
```

This is an example that will enable AWS Config to all accounts and regions except `Account One`. In `Account Two`, only S3 buckets, and security groups will be recorded in regions not us-east-1. In `Account Two`/us-east-1, it will record S3 buckets, security groups, and IAM roles. For all other
account/region pairs, it will record all resources except EC2 instances:
```yaml
TemplateName: AWSConfigEnablement
TemplateDescription: Enabling AWS Config
IncludeAccounts:
    AllAccounts: True
ExcludeAccounts:
    ByNames:
        - "Account One"
OperateInOrgRoot: True
IncludeRegions:
    - ALL
DefaultConfiguration:
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordEverythingExcept:
                - AWS::EC2::Instance
    RetentionPeriodInDays: 2557
AccountOverrideConfigurations:
  -
    IncludeAccounts:
        ByNames:
            - "Account Two"
    IncludeRegions:
        - ALL
    ExcludeRegions:
        - us-east-1
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordSpecificResources:
                - AWS::S3::Bucket
                - AWS::EC2::SecurityGroup
    RetentionPeriodInDays: 2557
  -
    IncludeAccounts:
        ByNames:
            - "Account Two"
    IncludeRegions:
        - us-east-1
    DeliveryChannelDetails:
        BucketName: your-s3-bucket-here
        S3DeliveryFrequency: Twelve_Hours
    RecorderConfiguration:
        ConfigRoleName: AWSConfigRole
        RecordingEnabled: True
        RecordingGroup:
            RecordSpecificResources:
                - AWS::S3::Bucket
                - AWS::EC2::SecurityGroup
                - AWS::IAM::Role
    RetentionPeriodInDays: 2557
```

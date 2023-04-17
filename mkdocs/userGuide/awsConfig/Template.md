# AWS Config Worker Templates
In this section, we discuss the AWS Config worker templates. The Config Worker is an `ACCOUNT_REGION` worker, and thus relies on the base account/region template components [that is discussed here](../../architecture/PayloadTemplates.md#account-region-worker-templates). In addition to the base account/region details, there are some unique fields defined below:

## Template Schema
The only required field is a very important one and that is the `DefaultConfiguration` section. Below is a sample template where this is defined:

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
            ResourceTypes:
                - ALL
            GlobalsInRegions:
                - us-east-1
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

1. `ResourceTypes` - This is a list of strings that will be one of 2 possible values. It will either be a list of AWS Config supported resource types **-- OR --** it will simply be a list of 1 item: `- ALL`. More on that below.
1. `GlobalsInRegions` - This is a list of AWS regions that will record global resources. This is **only** used if `ResourceTypes` is set to a value of `- ALL`. For example, if you are recording all resource types, then you _must_ use this to define which AWS regions you want to record the global resource types (like IAM roles) in. Keep in mind, that if you record global resource types in more than 1 region, AWS will bill you duplicate times for change histories for those global resources. This field needs to be blank if you are _not_ recording `- ALL` resource types.

#### `RecordingGroup` details
The `RecordingGroup` allows you to specify which resources to record. As stated above, if you set the `ResourceTypes` field to `- ALL`, then it will set the `allResources: True` flag in the API to create or update the recorder. This will record all resources, and all newly supported resources that AWS Config adds in the future automatically. If `ResourceTypes` is set to `- ALL`, then you also need to define `GlobalsInRegions` to include the AWS regions to record the global resource types. We recommend that you set this to `us-east-1`, and optionally some other region if you would like to have multiple copies of global resources recorded.

If you don't want all resources to be recorded, then you need to set the `ResourceTypes` field to a list of AWS Config resource type names, [as defined in this page](https://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html). Some examples are `AWS::S3::Bucket`, and `AWS::IAM::Role`.

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
We provide you the ability to provide Account/Region level overrides. This is useful if you need to opt-out or opt-in resource level configurations for a given set of accounts. This is set via the *OPTIONAL* `AccountOverrideConfigurations` field. The `AccountOverrideConfigurations` is a list of all the items in the `DefaultConfiguration` schema but also has the ability to specify the account and region to run and not run in.

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
            ResourceTypes:
                - ALL
            GlobalsInRegions:
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
                ResourceTypes:
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
            ResourceTypes:
                - ALL
            GlobalsInRegions:
                - us-east-1
    RetentionPeriodInDays: 2557
```

This is an example that will enable AWS Config to all accounts and regions except `Account One`. In `Account Two`, only S3 buckets, and security groups will be recorded in regions not us-east-1. In `Account Two`/us-east-1, it will record S3 buckets, security groups, and IAM roles:
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
            ResourceTypes:
                - ALL
            GlobalsInRegions:
                - us-east-1
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
            ResourceTypes:
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
            ResourceTypes:
                - AWS::S3::Bucket
                - AWS::EC2::SecurityGroup
                - AWS::IAM::Role
    RetentionPeriodInDays: 2557
```

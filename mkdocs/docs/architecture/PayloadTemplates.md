# Payload YAML Templates

Each worker ship is provided with a payload that provides it with context on the specific job it needs to perform. This payload is a YAML file that lives in S3. The YAML needs to conform to a Python Marshmallow schema that the worker defines, and each worker's documentation should outline what those are and why.

All templates must end in `.yaml` and reside in the template S3 bucket. Different types of workers will have different template types, as described below. It is also highly recommended that for consistency, all field names exist in UpperCamelCase.

## General Template Philosophy
We have a general philosophy around how templates should be designed and implemented. That is:

1. Control structures like loops and if statements belong in code, not templates
1. There is a time and place for Jinja; just not all the times in all the places

Starfleet workers should do the heavy lifting so that templates are easy to read and parse. Human readable templates provide context faster, and reduce the likelihood of errors. This is especially important when operating at scale. This is why we chose YAML and chose sophisticated schema backends so that the complexity happens once; in the code; and not N times in templates (the concept of _Don't Repeat Yourself_, only for real.)

!!! success "Special Note"
    The details below are provided for you _for free_ when making Starfleet workers. You _do not_ need to worry about writing this code. Starfleet's code does all this work for you so you can focus on where the job needs to run and what it needs to do.

## Some Samples
Some sample templates are here:

Sample for the `AccountIndexGeneratorShip` - a worker ship that generates an AWS account index:
```yaml
TemplateName: AccountIndexGeneratorShip
TemplateDescription: The Account Index Generator Worker template
AccountInventoryBucket: some-s3-bucket-to-hold-the-account-index
InventoryBucketRegion: us-east-2
```
This YAML informs the `AccountIndexGeneratorShip` which S3 bucket to save the inventory to and also the region to save it in. The worker also has an optional field for the name of the saved report, which by default, this value is set to `accounts.json`. If you want more than 1 inventory report saved to different S3 buckets or locations, you can simply create more payload templates to specify that!

More examples will be provided when those worker ships are developed.

## Base Template
Each template has some fields that must be present in all payloads. There are just 2:

1. **`TemplateName`** - This is a friendly name for the template.
1. **`TemplateDescription`** - This is just a friendly description for what the template does.

## Account Worker Templates
If a worker has an `ACCOUNT` fan out strategy, then it will require the same things mentioned above in the base template, but **requires** you to specify the AWS accounts the template applies for. You can specify AWS accounts to include in the template (`IncludeAccounts`) or accounts to exclude from the template (`ExcludeAccounts`). The account resolution logic will _**always**_ ensure that the account exclusion takes precedence. Both `IncludeAccounts` and `ExcludeAccounts` are dictionaries. There is also another field called `OperateInOrgRoot`, which is a flag that allows Starfleet to operate in the Organization Root account (it won't by default).

### Account Inclusion
To include accounts for the template to operate in, there is a field called `IncludeAccounts`. This field has its own schema. It has nested components to define a combination on AWS accounts to target for a template.

You can target accounts by:

1. All AWS Accounts
1. By Account ID
1. By Account Name or Alias
1. By Tags
1. By Organization Unit
1. The Org Root*

!!! info "*Special note about the Organization Root account"
    The Organization Root is a very special account. By default, Starfleet will _not_ run in the organization root account _unless_ you explicitly tell it to by setting `OperateInOrgRoot` set to `True` _AND_ if the Org Root account is included the other `IncludeAccounts` fields.

These are described in further detail below.

#### All AWS Accounts
To have a template run across *ALL* AWS accounts, you would specify an `IncludeAccounts` that sets the `AllAccounts` flag to `True`. This looks like this:
```yaml
IncludeAccounts:
    AllAccounts: True
```
By default this field is `False`.

!!! danger
    If you set this field to `True`, then you cannot set the other fields for `IncludeAccounts`. Starfleet will throw an error if this is set.

#### By Account IDs
To have a template run across specific AWS accounts by account ID (12 digit string), you would specify an `IncludeAccounts` that sets `ByIds` to a list of AWS account numbers. This looks like this:
```yaml
IncludeAccounts:
    ByIds:
        - "111111111111"
        - "222222222222"
        - "333333333333"
```

By default this is an empty list. This field can be used in combination with all other fields except `AllAccounts` set to `True`. In the example above, this would only run in accounts with IDs `111111111111`, `222222222222`, and `333333333333`.

!!! danger
    AWS account IDs are *STRINGS*, not *Numbers!* As a result, _please_ wrap account IDs in quotes `""` to prevent the leading `0` in an account ID getting stripped off!

#### By Account Names
To have a template run across specific AWS accounts by an account name, you would specify an `IncludeAccounts` that sets `ByNames` to a list of AWS names. An account name in this context is what you would have an account named in AWS Organizations. This looks like this:
```yaml
IncludeAccounts:
    ByNames:
        - Dev Account
        - Staging Account
        - Production Account
```

By default this is an empty list. This field can be used in combination with all other fields except `AllAccounts` set to `True`. Account names are _case-insensitive_ - internally Starfleet handles everything as lowercase strings. In this example, this template would only apply to accounts that are named `Dev Account`, `Staging Account`, and `Production Account`. (Account names are unique in your environment)

!!! warning
    Be mindful of whitespaces. You can always wrap in `""` quotes.

TODO: We may implement a feature to operate on an Account Alias -- which would basically be a tag on the account with a list of names to use. We have not settled on this yet though.

#### By Account Tags
To have a template run across specific AWS accounts by how an account is tagged, you would specify an `IncludeAccounts` that sets `ByTags` to a list of tag name/value pairs. An account tag in this context is what you would have an account tagged as in AWS Organizations. This looks like this:
```yaml
IncludeAccounts:
    ByTags:
        - Name: Environment
          Value: Dev
        - Name: Environment
          Value: Test
        - Name: Business Unit
          Value: Marketing
```

By default this is an empty list. This field can be used in combination with all other fields except `AllAccounts` set to `True`. Tag names and values are _case-sensitive_. The account logic resolution for this is _inclusive_, or logical `OR`. The example above would run against AWS accounts that are tagged with tag name `Environment` with tag values `Dev` or `Test`, and it would also include accounts tagged with tag name `Business Unit` set to the value of `Marketing`.

!!! warning
    Be mindful of whitespaces. You can always wrap in `""` quotes.

!!! warning
    This uses _inclusive OR_ logic. It will include any accounts that have the tag name/value pairs set.

#### By Organization Unit
To have a template run across specific AWS accounts based on Organization Unit (OU) residency, you would specify an `IncludeAccounts` that sets `ByOrgUnits` to a list either OU name or OU ID. This looks like this:
```yaml
IncludeAccounts:
    ByOrgUnits:
        - Some Org Unit
        - Some Other Org Unit
        - ou-1234-5678910
```

By default this is an empty list. This field can be used in combination with all other fields except `AllAccounts` set to `True`. OU values are _case-insensitive_. The account logic resolution for this is _inclusive_, or logical `OR`. The example above would run against AWS accounts that exist in any of the specified OUs. In this example, it would include accounts that reside in `Some Org Unit`. or `Some Other Org Unit`, or `ou-1234-5678910`.

!!! warning
    Be mindful of whitespaces. You can always wrap in `""` quotes.

### Account Exclusion
If you need to explicitly avoid an account from being acted upon, then you need to specify the `ExcludeAccounts` dictionary. By default this is not set. The `ExcludeAccounts` dictionary is _exactly the same as the `IncludeAccounts` dictionary_, except that it lacks the `AllAccounts` flag. `AllAccounts` _only_ applies to `IncludeAccounts`.

By default, the Organization Root is not worked on unless it is included in `IncludeAccounts` and also if the `OperateInOrgRoot` flag is set to `True`.

### Some Examples
In addition to the examples above, here are some examples where everything comes together:

Here is an example of specifying that a template should apply to all accounts _except_ the organization root and accounts that are tagged as `Environment: Production`:
```yaml
IncludeAccounts:
    AllAccounts: True
ExcludeAccounts:
    ByTags:
        - Name: Environment
          Value: Production
```

Here is an example of applying to all accounts, including the org root:
```yaml
IncludeAccounts:
    AllAccounts: True
OperateInOrgRoot: True
```

Here is an example of applying to the `Infsec Staging` account, all accounts in the `DevOps`, `Financial`, and `Marketing` OUs and _excluding_ accounts named `DevOps Prod`, and `Financial Prod`.
```yaml
IncludeAccounts:
    ByNames:
        - InfoSec Staging
    ByOrgUnits:
        - DevOps
        - Financial
        - Marketing
ExcludeAccounts:
    ByNames:
        - DevOps Prod
        - Financial Prod
```

## Account-Region Worker Templates
This is not yet implemented but will be similar to above only with Regional context as well.

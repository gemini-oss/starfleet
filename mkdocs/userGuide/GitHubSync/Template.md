# GitHub Repo Sync Worker: Payload Template Schema
In this section, we discuss the GitHub Repo Sync worker templates. The GitHub Repo Sync worker is a `SINGLE_INVOCATION` worker, and does not require any AWS account on the account index.

## Template Schema
Here is an example of the schema:
```yaml
TemplateName: NameOfYourTemplate
TemplateDescription: Syncs the REPO-NAME to the BUCKET-NAME
Organization: YOUR-ORG-NAME-HERE
Repository: THE-REPO-HERE
BranchName: THE-BRANCH-NAME-HERE
GitHubAppId: "The GitHub App Id -- need to wrap in quotes as it's technically a number but this needs to be a string"
GitHubInstallationId: "The GitHub Installation ID -- ditto about wrapping in quotes"
BucketName: YOUR-S3-BUCKET
BucketRegion: S3 BUCKET REGION HERE
ExtractZipContents: True  # See below for details
DeleteMissingFiles: True  # See below for details

# https://www.regexpal.com/ is your friend
ExcludeRepoPaths:
  - "^testing\/.+$"  # Excluding the `testing/` path
  - "^README.md$"
  - "^.github\/.+$"
  - "^.gitignore$"
```

Below are the **required** fields that this worker needs:

1. **`Organization`** - This is the name of the GitHub organization that the repository resides in. Note: This must be the same exact value (case sensitive) that is in the Secret to reference the GitHub App private key.
1. **`Repository`** - This is the name of the repository to sync. You need to make sure that the GitHub App has permissions to download this repo.
1. **`BranchName`** - This is the name of the branch that you want to sync. Typically, this would be `main` or `master`.
1. **`GitHubAppId`** - This is the *Application ID* (documented in the [GitHub App Configuration page](ConfigureGitHubApp.md)). Wrap it in quotes because it's a numerical string.
1. **`GitHubInstallationId`** - This is the *Installation ID* (documented in the [GitHub App Configuration page](ConfigureGitHubApp.md)). Wrap it in quotes because it's a numerical string.
1. **`BucketName`** - This is the name of the S3 bucket you want to sync with
1. **`BucketRegion`** - This is the region that the bucket resides in
1. **`ExtractZipContents`** - Boolean - This indicates whether or not the downloaded `.zip` file from GitHub should be extracted or not. That is to say, if this field is `False`, then the downloaded `.zip` file itself is what will be synced with S3. If this is set to `True`, then the `.zip` is extracted and the extracted files is what will be compared with S3. This being set to `False` is useful if you wanted to have the entire repository itself be the artifact that you want stored in S3 for downstream processing. For the use case of syncing payload templates to the templates S3 bucket, you want this to be set to `True` so that each template is individually synced with S3.

Here are the **optional** fields:

1. **`IncludeRepoPaths`** - List of Regex Strings - This is a list of regex strings indicate the paths on the local disk that should be synced with S3. By default, this value is set to: `["^.+$"]`, which will match on everything. As mentioned on the previous page, if you wanted to sync the templates repository with S3, then for the testing deployment, you could have this set to `- "^testing\/.+$"`, which would only sync repository files that exist in the `testing\` path.
1. **`ExcludeRepoPaths`** - List of Regex Strings - This is a list of regex strings that indicate the paths on the local disk that should *not* be synced with S3. This takes precedence over the `IncludeRepoPaths`. In the included example above, we are ignoring specific files that we don't want synced with S3, like the `.gitignore` file. By default, this field is an empty list: `[]`.
1. **`KeyPrefix`** - This is the starting prefix in the S3 bucket that should be assessed. By default, the root of the S3 bucket is what the worker examines. If you wanted to only sync files that reside within the `foo/` prefix of the bucket, then you would want to set this value to `foo/`. All repo files would then be set to reside in `foo/filename...` on the bucket.
1. **`DeleteMissingFiles`** - Boolean - By default, this is set to `False`. If this is set to `True`, then the worker will *delete* any object in the S3 bucket that is *not* found in the GitHub repository. This flag being enabled keeps the S3 bucket contents 1:1 in sync with the repository.

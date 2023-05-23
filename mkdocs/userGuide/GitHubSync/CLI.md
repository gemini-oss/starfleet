# GitHub Repo Sync Worker CLI

The GitHub Repo Sync worker has 3 commands. All commands require AWS credentials used by Starfleet to be exported into the environment. All commands are under the `sync-github` sub-command.

All commands require a `--payload` parameter to point to the path of the YAML payload.

```bash
starfleet sync-github
Usage: starfleet sync-github [OPTIONS] COMMAND [ARGS]...

  This is the worker ship for syncing a GitHub repo with S3.

Options:
  --help  Show this message and exit.

Commands:
  download                This is a helpful debugging command to download...
  get-installation-token  This returns the installation token for the...
  run                     This will run the syncing of the repository...
```

## The `get-installation-token` command
The `get-installation-token` command is used for debugging purposes. It outputs an ephemeral GitHub authorization bearer token for the GitHub App specified in the payload template. This token can be used to make authenticated API calls to GitHub. You can use this with curl or Postman to debug the GitHub App's ability to make authenticated calls to GitHub.

Help text:
```bash
starfleet sync-github get-installation-token --help
Usage: starfleet sync-github get-installation-token [OPTIONS]

  This returns the installation token for the given organization, application
  id, and installation id provided in the payload template. This is mostly
  used for local testing and debugging.

Options:
  --payload FILENAME  This is the worker payload YAML  [required]
  --commit            Must be supplied for changes to be made [does not do anything]
  --help              Show this message and exit.
```

The `--commit` flag does not have any purpose for this command.

Here is a sample command that would generate the token:
```bash
starfleet sync-github get-installation-token --payload /path/to/payload.yaml
```

## The `download` command
The `download` command simply downloads the GitHub repository to the local disk. It will extract the `.zip` file downloaded from GitHub if the payload specifies the `ExtractZipContents` flag set to `True`. This is mostly used for debugging purposes.

Help text:
```bash
starfleet sync-github download --help
Usage: starfleet sync-github download [OPTIONS]

  This is a helpful debugging command to download the repository. This will
  extract the contents if the payload specifies the `ExtractZipContents` flag
  set to `True`. You simply provide the payload template and the location for
  where you want the repo to be downloaded (and optionally extracted), and it
  will be saved to that path as `REPO_NAME.zip` (and extracted as `REPO_NAME-
  COMMIT-HASH/`).

  The commit flag doesn't do anything for this command.

Options:
  --save-dir PATH     A local directory to save the zip in.  [required]
  --payload FILENAME  This is the worker payload YAML  [required]
  --commit            Must be supplied for changes to be made [does not do anything]
  --help              Show this message and exit.
```

The `--commit` flag does not have any purpose for this command.

Here is a sample command that would save the repo to the Desktop:
```bash
starfleet sync-github get-installation-token --payload /path/to/payload.yaml --save-dir ~/Desktop/
```

## The `run` command
The `run` command performs the full function of the workload where it will download the repo, optionally extract the contents, and attempt to sync with S3. This works the same way the Lambda function in the cloud would. This optionally allows you to specify a download directory to persist the downloaded components.

Help text:
```bash
starfleet sync-github run --help
Usage: starfleet sync-github run [OPTIONS]

  This will run the syncing of the repository against the payload's specified
  S3 bucket.

Options:
  --save-dir PATH     An optional local directory to save and retain the
                      contents within. If not supplied, then this will create
                      a temporary directory and delete it.
  --payload FILENAME  This is the worker payload YAML  [required]
  --commit            Must be supplied for changes to be made
  --help              Show this message and exit.
```

The `--commit` flag will attempt to make changes to the S3 bucket's files if there is a change that needs to run.

Here is a sample command that would save the repo to the Desktop, and also attempt to sync the changes to S3. Commit enabled:
```bash
starfleet sync-github run --payload /path/to/payload.yaml --save-dir ~/Desktop/ --commit
```

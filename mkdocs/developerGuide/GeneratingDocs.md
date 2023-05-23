# Generating the Documentation

This page outlines how to generate the lovely docs you are currently reading!

The docs are generated via [`mkdocs`](https://www.mkdocs.org) with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/). All of the docs are markdown files that reside in the `mkdocs/` directory, and the docs site is configured via the `mkdocs.yml` file.

## Dependencies
All of the dependencies to build the docs are installed as part of the test dependencies (defined in `pyproject.toml`). This is obtained by running:

```bash
source venv/bin/activate  # Make sure you are in your venv
pip install -e ."[tests]"
```

## Running mkdocs
You can run `mkdocs` locally by running:

```bash
source venv/bin/activate  # Make sure you are in your venv
mkdocs serve
```

... and then opening your web browser to `http://localhost:8000`. Errors and warnings will appear in the console output. Please make sure there are none before submitting documentation updates.

## Building the docs
The docs are built by running:

```bash
source venv/bin/activate  # Make sure you are in your venv
mkdocs build
```

Doing this will generate the docs to the `site/` directory. You need to rename this directory to `docs/`. This directory is _not_ included in the _main_ branch of the repository. Instead, we have another branch called `gh-pages` where this is committed to. This is what GitHub uses to host the site you are reading right now.

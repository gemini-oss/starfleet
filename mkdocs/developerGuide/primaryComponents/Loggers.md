# Loggers

We have a common logger that you should make use of throughout Starfleet. This is configured on startup whenever any Python file imports it.

To use the logger you need to import it and the interact with it using `LOGGER`:

```python
# Import the logger:
from starfleet.utils.logging import LOGGER

# ...

# Use the Logger:
LOGGER.info("[🛸] something to log...")
```

The logger is configured to log out everything in a nice format that appears in the Lambda CloudWatch Logs and should appear nicely in any log aggregation system you want to make use of. Things like the log level and 3rd party loggers to ignore is set in the configuration ([details here](../../architecture/Configuration.md#optional-fields)).

!!! tip
    One thing you will commonly see throughout the Starfleet codebase are log entries with emojis wrapped in brackets. We just ❤️ Emojis here (and believe it or not, it makes it easier to locate entires in a log system 🤣)

    *Protip:* make a bookmark for [https://emojipedia.org/](https://emojipedia.org/)

If you want to see the raw code for the logger take a look at `starfleet.utils.logging`.

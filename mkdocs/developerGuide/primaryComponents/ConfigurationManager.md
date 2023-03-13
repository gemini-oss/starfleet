# Configuration Manager

It is very important to understand the configuration! Make sure you first review the [Architecture section for Configuration](../../architecture/Configuration.md) before reading this section. The configuration is provided as a singleton object in `starfleet.utils.configuration` and is used like this:

```python
# Import the configuration manager:
from starfleet.utils.configuration import STARFLEET_CONFIGURATION

# ...

# Use the configuration
some_config_entry = STARFLEET_CONFIGURATION.config["STARFLEET"]  # Fetch the dictionary under the STARFLEET configuration section
some_other_config_entry = STARFLEET_CONFIGURATION.config["AccountIndexGeneratorShip"]  # Fetch the dictionary under the AccountIndexGeneratorShip worker ship definition
```

All of the configuration is obtained by using `STARFLEET_CONFIGURATION.config`. `config` is a dictionary that is lazy loaded property that contains a dictionary of all the configuration YAML data. The configuration is loaded once on startup by it going to the `src/starfleet/configuration_files/` path, loading all the nested `.yaml` files and then merging them into one large dictionary.

### Configuration Schemas
There are Marshmallow schemas for configuration, however these are loaded piecemeal and not all at once. This can be confusing so we'll tackle this in parts to make this more clear.

#### Base Configuration Schema
There is a `BaseConfigurationSchema` that resides in `starfleet.utils.config_schema`, which defines the schema for the `STARFLEET` section of the configuration. This schema is used when loading the initial configuration, and verifies that the `STARFLEET` section is correct.

#### Worker Ship Configurations
The worker ship configurations are documented later in detail. However, for now we'll mention that the worker ship configurations are validated against the worker ship defined schemas when the worker ship plugins are loaded later on during startup.

### Unit Testing Configuration
Mocking out the configuration is extremely important for running unit tests. We have defined a pytest fixture that sets the configuration manager's `config` property to a testing dictionary suitable for all the unit tests. The really nice thing about this is that this sets the testing configuration for *all* the unit tests as long as the `test_configuration` fixture is used during the tests (or inherited from another fixture you are using). This is another reason why we really like using Singletons - it makes mocking things out very easy and globally for the code when testing.

The `test_configuration` fixture is defined in `tests.conftest`. Unit tests have configuration YAML files stored in a separate location under `tests/test_configuration_files/`. The configuration manager is configured by the fixture to load files from that location instead of `src/starfleet/configuration_files` to make testing clean and isolated. This is a pattern that is frequently used throughout Starfleet.

As you develop features, you will want to make changes to the configuration to include the details you need for testing the code you are writing. You can easily do that by making a pytest fixture that looks like this:

```python
@pytest.fixture
def my_worker_ship_configuration(test_configuration: Dict[str, Any]) -> None:
    """This will inject my code's configuration into the configuration manager for use throughout the app."""
    my_apps_config = {"some_field": "some_value", "some_other_field": "some_other_value"}

    test_configuration["MyWorkerShip"] = my_apps_config

# ...

def test_my_ships_configuration(my_worker_ship_configuration: None) -> None:
    """This tests that the configuration manager has the configuration set by my fixture loaded within it."""
    from starfleet.utils.configuration import STARFLEET_CONFIGURATION

    assert STARFLEET_CONFIGURATION.config["MyWorkerShip"] == {"some_field": "some_value", "some_other_field": "some_other_value"}
    # ^^ This will be True
```

!!! tip
    You will want to really understand how pytest fixtures work. We use them extensively. Please review the pytest documentation for more details.

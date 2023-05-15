"""A general set of niceties that Starfleet workers can use to do things that are nice.

This mostly defines some shortcut code utilities that workers can use for a variety of use cases.

:Module: starfleet.worker_ships.niceties
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
import datetime
import json
from typing import Any
from urllib.parse import unquote_plus


def un_wrap_json(json_obj: Any) -> Any:
    """Helper function to unwrap nested JSON in the AWS Config resource configuration."""
    # pylint: disable=C0103,W0703,R0911
    # Is this a field that we can safely return?
    if isinstance(json_obj, (type(None), int, bool, float)):  # noqa
        return json_obj

    # Is this a Datetime? Convert it to a string and return it:
    if isinstance(json_obj, datetime.datetime):
        return str(json_obj)

    # Is this a Dictionary?
    if isinstance(json_obj, dict):
        decoded = {}
        for k, v in json_obj.items():
            decoded[k] = un_wrap_json(v)

    # Is this a List?
    elif isinstance(json_obj, list):
        decoded = []
        for x in json_obj:
            decoded.append(un_wrap_json(x))

        # Yes, try to sort the contents of lists. This is because AWS does not consistently store list ordering for many resource types:
        try:
            sorted_list = sorted(decoded)
            decoded = sorted_list
        except Exception:  # noqa  # nosec   # If we can't sort then NBD
            pass
    else:
        # Try to load the JSON string:
        try:
            # Check if the string starts with a "[" or a "{" (because apparently '123' is a valid JSON 😒😒😒)
            for check_field in ["{", "[", '"{', '"[']:  # Some of the double-wrapping is really ridiculous 😒
                if json_obj.startswith(check_field):
                    decoded = json.loads(json_obj)

                    # If we loaded this properly, then we need to pass the decoded JSON back in for all the nested stuff:
                    return un_wrap_json(decoded)

            # Check if this string is URL Encoded - if it is, then re-run it through:
            decoded = unquote_plus(json_obj)
            if decoded != json_obj:
                return un_wrap_json(decoded)

            return json_obj

        # If we didn't get a JSON back (exception), then just return the raw value back:
        except Exception:  # noqa
            return json_obj

    return decoded

"""A general set of niceties that Starfleet can use to do things that are nice.

This mostly defines some shortcut code utilities that workers can use for a variety of use cases.

:Module: starfleet.utils.niceties
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
from typing import Set

import boto3


def get_all_regions(service: str = "ec2") -> Set[str]:
    """
    This will return all supported AWS regions for the supplied service. By default, this returns the set for EC2.

    This is placed here as a function so that we can easily mock out the values with a static set of values that will persist throughout boto3 updates.
    """
    return set(boto3.session.Session().get_available_regions(service))

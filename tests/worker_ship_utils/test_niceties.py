"""Tests the worker ship niceties.

:Module: starfleet.tests.worker_ship_utils.test_niceties
:Copyright: (c) 2023 by Gemini Trust Company, LLC., see AUTHORS for more info
:License: See the LICENSE file for details
:Author: Mike Grima <michael.grima@gemini.com>
"""
# pylint: disable=unused-argument
import datetime


def test_unwrap_json() -> None:
    """This tests the unwrapping of AWS Config json."""
    from starfleet.worker_ships.niceties import un_wrap_json

    # Simple AWS policy JSON:
    test_str = (
        '{"policyText": "{\\"Version\\":\\"2008-10-17\\",\\"Statement\\":[{\\"Sid\\":\\"AccountReadOnly\\",\\"Effect\\":\\"Allow\\",\\"Principal\\":{'
        '\\"AWS\\":[\\"arn:aws:iam::000000000001:root\\"]},\\"Action\\":[\\"s3:Get*\\",\\"s3:List*\\"],\\"Resource\\":['
        '\\"arn:aws:s3:::some-bucket\\",\\"arn:aws:s3:::some-bucket/*\\"]}]}"} '
    )
    should_equal = {
        "policyText": {
            "Version": "2008-10-17",
            "Statement": [
                {
                    "Sid": "AccountReadOnly",
                    "Effect": "Allow",
                    "Principal": {"AWS": ["arn:aws:iam::000000000001:root"]},
                    "Action": ["s3:Get*", "s3:List*"],
                    "Resource": ["arn:aws:s3:::some-bucket", "arn:aws:s3:::some-bucket/*"],
                }
            ],
        }
    }
    assert un_wrap_json(test_str) == should_equal

    # With URL encoding:
    test_str_with_url_encoding = (
        '{"path":"/","roleName":"SomeRole","roleId":"AROAALSKDJFLAKSDJFKLJSDF",'
        '"arn":"arn:aws:iam::000000000001:role/SomeRole","createDate":"2023-11-12T18:41:33.000Z",'
        '"assumeRolePolicyDocument":"%7B%22Version%22%3A%222012-10-17%22%2C%22Statement%22%3A%5B%7B%22Effect%22%3A%22Allow%22%2C'
        '%22Principal%22%3A%7B%22Service%22%3A%22ec2.amazonaws.com%22%7D%2C%22Action%22%3A%22sts%3AAssumeRole%22%7D%5D%7D",'
        '"instanceProfileList":[{"path":"/","instanceProfileName":"SomeRole",'
        '"instanceProfileId":"AROAALSKDJFLAKSDJFKLJSDF",'
        '"arn":"arn:aws:iam::000000000001:instance-profile/SomeRole","createDate":"2023-11-12T18:41:33.000Z",'
        '"roles":[{"path":"/","roleName":"SomeRole","roleId":"AROAALSKDJFLAKSDJFKLJSDF",'
        '"arn":"arn:aws:iam::000000000001:role/SomeRole","createDate":"2023-11-12T18:41:33.000Z",'
        '"assumeRolePolicyDocument":"%7B%22Version%22%3A%222012-10-17%22%2C%22Statement%22%3A%5B%7B%22Effect%22%3A%22Allow%22%2C'
        '%22Principal%22%3A%7B%22Service%22%3A%22ec2.amazonaws.com%22%7D%2C%22Action%22%3A%22sts%3AAssumeRole%22%7D%5D%7D",'
        '"description":null,"maxSessionDuration":null,"permissionsBoundary":null,"tags":[],"roleLastUsed":null}]}],'
        '"rolePolicyList":[{"policyName":"Config",'
        '"policyDocument":"%7B%22Statement%22%3A%5B%7B%22Action%22%3A%5B%22config%3Aselectaggregateresourceconfig%22%5D%2C'
        '%22Effect%22%3A%22Allow%22%2C%22Resource%22%3A%5B%22%2A%22%5D%7D%5D%2C%22Version%22%3A%222012-10-17%22%7D"}],'
        '"attachedManagedPolicies":[{"policyName":"SomePolicy",'
        '"policyArn":"arn:aws:iam::000000000001:policy/SomePolicy"}],"permissionsBoundary":null,"tags":[],'
        '"roleLastUsed":null} '
    )
    should_equal = {
        "path": "/",
        "roleName": "SomeRole",
        "roleId": "AROAALSKDJFLAKSDJFKLJSDF",
        "arn": "arn:aws:iam::000000000001:role/SomeRole",
        "createDate": "2023-11-12T18:41:33.000Z",
        "assumeRolePolicyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}],
        },
        "instanceProfileList": [
            {
                "path": "/",
                "instanceProfileName": "SomeRole",
                "instanceProfileId": "AROAALSKDJFLAKSDJFKLJSDF",
                "arn": "arn:aws:iam::000000000001:instance-profile/SomeRole",
                "createDate": "2023-11-12T18:41:33.000Z",
                "roles": [
                    {
                        "path": "/",
                        "roleName": "SomeRole",
                        "roleId": "AROAALSKDJFLAKSDJFKLJSDF",
                        "arn": "arn:aws:iam::000000000001:role/SomeRole",
                        "createDate": "2023-11-12T18:41:33.000Z",
                        "assumeRolePolicyDocument": {
                            "Version": "2012-10-17",
                            "Statement": [{"Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole"}],
                        },
                        "description": None,
                        "maxSessionDuration": None,
                        "permissionsBoundary": None,
                        "tags": [],
                        "roleLastUsed": None,
                    }
                ],
            }
        ],
        "rolePolicyList": [
            {
                "policyName": "Config",
                "policyDocument": {
                    "Statement": [{"Action": ["config:selectaggregateresourceconfig"], "Effect": "Allow", "Resource": ["*"]}],
                    "Version": "2012-10-17",
                },
            }
        ],
        "attachedManagedPolicies": [{"policyName": "SomePolicy", "policyArn": "arn:aws:iam::000000000001:policy/SomePolicy"}],
        "permissionsBoundary": None,
        "tags": [],
        "roleLastUsed": None,
    }
    assert un_wrap_json(test_str_with_url_encoding) == should_equal

    # And again with some strange nesting:
    test_nested = {
        "how": [
            "nested",
            {
                "can": '{"we": "really", "really": "[\\"get\\", \\"{\\\\\\"into\\\\\\": \\\\\\"{\\\\\\\\\\\\\\"really\\\\\\\\\\\\\\": '
                '\\\\\\\\\\\\\\"deep\\\\\\\\\\\\\\"}\\\\\\"}\\"]"}'
            },
            94,
            3.14,
            {"more": '{"and again": "{\\"this and\\": \\"that\\"}"}'},
        ]
    }
    should_equal = {
        "how": ["nested", {"can": {"we": "really", "really": ["get", {"into": {"really": "deep"}}]}}, 94, 3.14, {"more": {"and again": {"this and": "that"}}}]
    }
    assert un_wrap_json(test_nested) == should_equal

    # And values that are non-JSON:
    now = datetime.datetime.utcnow()
    assert un_wrap_json(now) == str(now)
    assert un_wrap_json(19) == 19
    assert un_wrap_json(3.14) == 3.14
    assert un_wrap_json(True) is True

    # Try it with something bizarre, like a function:
    assert un_wrap_json(test_unwrap_json) == test_unwrap_json  # pylint: disable=comparison-with-callable

    # Test that we are sorting lists:
    test_sorted = {"a_list": [11, 5.2, 2, 0, 3], "b_list": ["a", "b", "c"], "with_nested_objs": [{"A": "Value"}, {"qwerty": "uiop[]"}]}
    assert un_wrap_json(test_sorted) == {"a_list": [0, 2, 3, 5.2, 11], "b_list": ["a", "b", "c"], "with_nested_objs": [{"A": "Value"}, {"qwerty": "uiop[]"}]}

#!/usr/local/autopkg/python

"""
Research/testing when and how to renew the oauth token.

Found out the token validity period (expiry_time) is not documented in API from VMWare, but is actually returned along
with the new token.
"""

import requests
import subprocess
import os
from datetime import datetime, timedelta, timezone
import time

def get_timestamp():
    timestamp = (datetime.now().astimezone() + timedelta(milliseconds=500)).replace(microsecond=0)
    return timestamp

"""
Fetch the secrets (passwords) from the dedicated macOS keychain used in the launcher tool used for development of
Autopkg processor
"""
def get_password_from_keychain(keychain, service, account):
    command = f"/usr/bin/security find-generic-password -w -s '{service}' -a '{account}' '{keychain}'"
    result = subprocess.run(command, shell=True, capture_output=True)
    if result.returncode == 0:
        password = result.stdout.decode().strip()
        return password
    else:
        return None


def set_password_in_keychain(keychain, service, account, password):
    command = f"/usr/bin/security add-generic-password -s '{service}' -a '{account}'  -w '{password}' '{keychain}'"
    result = subprocess.run(command, shell=True, capture_output=True)
    return result.returncode


def pretty_print_POST(req):
    """
    show what headers were added to POST request, thanks to https://stackoverflow.com/a/23816211

    At this point it is completely built and ready
    to be fired; it is "prepared".

    However pay attention at the formatting used in
    this function because it is programmed to be pretty
    printed and may differ from the actual request.
    """

    print(
        '-----------PREPPED REQUEST START-----------\n'
        f'Method: {req.method}\n' +
        f'url: {req.url}\n' +
        '-----------PREPPED REQUEST HEADERS-----------\n' +
        ''.join(f'{k}: {v}\n' for k, v in req.headers.items()) +
        '-----------PREPPED REQUEST BODY-----------\n' +
        f'{req.body}\n' +
        '-----------PREPPED REQUEST END-----------\n'
    )


def main():
    # oauth2 token is to be renewed when a specified percentage of the expiry time is left
    if "AUTOPKG_ws1_oauth_renew_margin" in os.environ:
        try:
            ws1_oauth_renew_margin = float(os.environ['AUTOPKG_ws1_oauth_renew_margin'])
            print(f'Found env var AUTOPKG_ws1_oauth_renew_margin: {ws1_oauth_renew_margin}')
        except ValueError:
            print('Found env var AUTOPKG_ws1_oauth_renew_margin is NOT a float: '
                  f"[{os.environ['AUTOPKG_ws1_oauth_renew_margin']}] - aborting!")
            exit(code=1)
    else:
        ws1_oauth_renew_margin = 10
        print(f'Using default for ws1_oauth_renew_margin: {ws1_oauth_renew_margin}')

    # keychain = "login.keychain"
    keychain = "Autopkg"
    service = "Autopkg_WS1"
    # service = "autopkg_tool_launcher"
    url = get_password_from_keychain(keychain, service, "WS1_OAUTH_TOKEN_URL")
    if url is None:
        print(f"Failed to get WS1_OAUTH_TOKEN_URL from keychain {keychain} - aborting")
        exit(code=1)
    client_id = get_password_from_keychain(keychain, service, "WS1_OAUTH_CLIENT_ID")
    if client_id is None:
        print(f"Failed to get WS1_OAUTH_CLIENT_ID from keychain {keychain} - aborting")
        exit(code=1)
    client_secret = get_password_from_keychain(keychain, service,"WS1_OAUTH_CLIENT_SECRET")
    if client_secret is None:
        print(f"Failed to get WS1_OAUTH_CLIENT_SECRET from keychain {keychain} - aborting")
        exit(code=1)
    payload = {'grant_type': 'client_credentials', 'client_id': client_id, 'client_secret': client_secret}

    # get timestamp, round to nearest whole second
    timestamp_start = get_timestamp()
    print(f"Test START Timestamp: {timestamp_start.isoformat()}")

    # init to test until a bit after the default 3600 seconds token validity period
    time_stop = timestamp_start + timedelta(seconds=4000)

    oauth_token = get_password_from_keychain(keychain, service,"oauth_token")
    if oauth_token is not None:
        print(f"Retrieved existing token from keychain: {oauth_token}")
    oauth_token_renew_timestamp_str = get_password_from_keychain(keychain, service,
                                                                 "oauth_token_renew_timestamp")
    if oauth_token_renew_timestamp_str is not None:
        oauth_token_renew_timestamp = datetime.fromisoformat(oauth_token_renew_timestamp_str)
        print(f"Retrieved timestamp to renew existing token from keychain: {oauth_token_renew_timestamp.isoformat()}")
    else:
        oauth_token_renew_timestamp = None
    while datetime.now().astimezone() < time_stop:
        timestamp = get_timestamp()
        if oauth_token is None or oauth_token_renew_timestamp is None or timestamp >= oauth_token_renew_timestamp:

            """
            response = requests.request("POST", url, data=payload)
            check what headers were added automatically to POST request, thanks to https://stackoverflow.com/a/23816211
            """
            req = requests.Request("POST", url, data=payload)
            prepared_req = req.prepare()
            pretty_print_POST(prepared_req)

            print("Calling API to renew OAuth token.")
            s = requests.Session()
            """
            # found out x-www-form-urlencoded is the default, tried making it explicit for clarity, but that causes a type-error
            prepared_req.headers = {"Content-Type": "application/x-www-form-urlencoded"}
            """
            response = s.send(prepared_req)

            print(f"Response status code: {response.status_code}")
            print(f"Response text: {response.text}")

            if response.status_code == 200:
                # get timestamp, round to nearest whole second
                oauth_token_issued_timestamp = get_timestamp()
                print(f"Oauth2 token issued at: {oauth_token_issued_timestamp.isoformat()}")

                result = response.json()
                oauth_token = result['access_token']
                print(f"Access token: {oauth_token}")
                print(f"Access token length: {len(result['access_token'])}")
                print(f"Access token validity is {result['expires_in']} seconds")

                renew_threshold = round(result['expires_in'] * (100 - ws1_oauth_renew_margin) / 100)
                print(f"Access token threshold for renewal set to {renew_threshold} seconds")
                oauth_token_renew_timestamp = oauth_token_issued_timestamp + timedelta(seconds=renew_threshold)
                print(f"Oauth2 token should be renewed after: {oauth_token_renew_timestamp.isoformat()}")

                # recalculate stop time until a bit after the actual token validity period from the API response
                test_runtime = round(result['expires_in'] * (100 + ws1_oauth_renew_margin) / 100)
                time_stop = timestamp_start + timedelta(seconds=test_runtime)
                print(f"Test stop scheduled for: {time_stop.isoformat()}")

            else:
                print(f"Got a bad response, status code: {response.status_code}")
                print(f"Error: {response.text}")
                exit(code=1)

        print(f"ToDo: test calling a program that can use the Oauth token")

        result = set_password_in_keychain(keychain, service,"oauth_token", oauth_token)
        result = set_password_in_keychain(keychain, service,
                                          "oauth_token_renew_timestamp",
                                          oauth_token_renew_timestamp.isoformat())

        timestamp = get_timestamp()
        print(f"Time: {timestamp.isoformat()}\tSleeping 5 minutes...")
        time.sleep(300)


if __name__ == "__main__":
    main()

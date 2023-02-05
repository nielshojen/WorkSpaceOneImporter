#!/usr/local/autopkg/python
#
# WorkSpaceOneImporter.py - a custom Autopkg processor
# Copyright 2022 Martinus Verburg https://github.com/codeskipper
# Adapted from https://github.com/jprichards/AirWatchImporter/blob/master/AirWatchImporter.py by
#     John Richards https://github.com/jprichards and
#     Jeremy Baker https://github.com/jbaker10
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Autopkg processor to upload files from a Munki repo to VMWare Workspace ONE using REST API"""

import base64
import os.path
import plistlib
import hashlib
import subprocess

import requests  # dependency
import json
import macsesh
import re

from autopkglib import Processor, ProcessorError, get_pref
from autopkglib.munkirepolibs.AutoPkgLib import AutoPkgLib

from requests_toolbelt import StreamingIterator  # dependency from requests

from urllib.parse import urlparse

__all__ = ["WorkSpaceOneImporter"]


def getsha256hash(filename):
    """
    Calculates the SHA-256 hash value of a file as a hex string. Nicked from Munki hash library munkihash.py

    Args:
        filename: The file name to calculate the hash value of.
    Returns:
        The hashvalue of the given file as hex string.
    """
    hasher = hashlib.sha256()
    if not os.path.isfile(filename):
        return 'NOT A FILE'
    try:
        fileref = open(filename, 'rb')
        while True:
            chunk = fileref.read(2 ** 16)
            if not chunk:
                break
            hasher.update(chunk)
        fileref.close()
        return hasher.hexdigest()
    except (OSError, IOError):
        return 'HASH_ERROR'


class WorkSpaceOneImporter(Processor):
    """Uploads apps from Munki repo to WorkSpace ONE"""
    input_variables = {
        "ws1_api_url": {
            "required": True,
            "description": "Base url of WorkSpace ONE UEM REST API server "
                           "(eg. https://myorg.awmdm.com)",
        },
        "ws1_console_url": {
            "required": False,
            "description": "Base url of WorkSpace ONE UEM Console server for easy result lookup "
                           "(eg. https://admin-mobile.myorg.com)",
        },
        "ws1_groupid": {
            "required": True,
            "description": "Group ID of WorkSpace ONE Organization Group "
                           "where files should be uploaded.",
        },
        "ws1_api_token": {
            "required": False,
            "description": "WorkSpace ONE REST API Token. Needed for Basic authentication.",
        },
        "ws1_api_username": {
            "required": False,
            "description": "WorkSpace ONE REST API Username. Either api_username and api_password or "
                           "b64encoded_api_credentials are required for Basic authentication.",
        },
        "ws1_api_password": {
            "required": False,
            "description": "WorkSpace ONE REST API User Password. Either api_username and api_password or "
                           "b64encoded_api_credentials are required for Basic authentication.",
        },
        "ws1_b64encoded_api_credentials": {
            "required": False,
            "description": "\"Basic \" + Base64 encoded username:password. Either api_username and api_password or "
                           "b64encoded_api_credentials are required for Basic authentication.",
        },
        "ws1_oauth_client_id": {
            "required": False,
            "description": "Client ID for Oauth 2.0 authorization - a more secure and recommended replacement for Basic "
                           "authentication.",
        },
        "ws1_oauth_client_secret": {
            "required": False,
            "description": "Client Secret for Oauth 2.0 authorization - a more secure and recommended replacement for "
                           "Basic authentication.",
        },
        "ws1_oauth_token_url": {
            "required": False,
            "description": "Access Token renewal service URL for Oauth 2.0 authorization.",
        },
        "ws1_force_import": {
            "required": False,
            "default": "False",
            "description":
                "If \"true\", force import into WS1 if version already exists. Default:false",
        },
        "ws1_import_new_only": {
            "required": False,
            "default": "True",
            "description":
                "If \"false\", in case no version was imported into Munki in this session, find latest version in "
                "munki_repo to import into WS1. Default: true, meaning only newly imported versions are imported to WS1.",
        },
        "ws1_smart_group_name": {
            "required": False,
            "description": "The name of the first smart group the app should be assigned to, typically testers / "
                           "early access.",
        },
        "ws1_push_mode": {
            "required": True,
            "description": "how to deploy the app, Auto or On-Demand.",
        },
        "ws1_deployment_date": {
            "required": False,
            "description": "Sets the date that the deployment of the app should begin. If not specified, current date "
                           "is chosen. Not implemented yet.",
        },
        "ws1_smart_group2_names": {
            "required": False,
            "default": "",
            "description": "The names of the secondary smart group(s) the app should be assigned to, typically for "
                           "production. Specify the group names as an array of strings. Under development.",
        },
        "ws1_deployment2_delay": {
            "required": False,
            "default": "14",
            "description": "Set the number of days to wait before deployment to the secondary smart group(s) should "
                           "begin. MUST specify as string value. Typically for production. Under development.",
        }
    }
    output_variables = {
        "makecatalogs_resultcode": {
            "description": "Result code from the makecatalogs operation.",
        },
        "makecatalogs_stderr": {
            "description": "Error output (if any) from makecatalogs.",
        },
        "ws1_resultcode": {
            "description": "Result code from the WorkSpace ONE Import.",
        },
        "ws1_stderr": {
            "description": "Error output (if any) from the WorkSpace ONE Import.",
        },
    }

    description = __doc__

    ### GIT FUNCTIONS
    def git_run(self, repo, cmd):
        """shell out a command to git in the Munki repo"""
        cmd = ["git"] + cmd
        self.output("Running " + " ".join(cmd), verbose_level=2)
        try:
            # result = subprocess.run(" ".join(cmd), shell=True, cwd=MUNKI_REPO, capture_output=hide_cmd_output)
            result = subprocess.run(" ".join(cmd), shell=True, cwd=repo, capture_output=True)
            self.output(result, verbose_level=2)
        except subprocess.CalledProcessError as e:
            print(e.stderr)
            raise e

    def git_lfs_pull(self, repo, filename):
        """pull specific LFS filename from git origin"""
        gitcmd = ["lfs", "pull", f"--include=\"{filename}\""]
        self.git_run(repo, gitcmd)

    def streamFile(self, filepath, url, headers):
        """expects headers w/ token, auth, and content-type"""
        streamer = StreamingIterator(os.path.getsize(filepath), open(filepath, 'rb'))
        r = requests.post(url, data=streamer, headers=headers)
        return r.json()

    # def convertTime(self, deployment_time):
    #     if int(deployment_time) <= 23:
    #         if int(deployment_time) is 24:
    #             self.output("deployment_time was set to 24, changing to 0")
    #             deployment_time = 0
    #         else:
    #             raise ProcessorError("Please enter a valid 24-hour time (i.e. between 0-23)")
    #
    #     today = datetime.date.today()
    #     timestamp = time.strftime('%H')
    #     utc_datetime = datetime.datetime.utcnow()
    #     utc_datetime_formatted = utc_datetime.strftime("%H")
    #     time_difference = ((int(utc_datetime_formatted) - int(timestamp)) * 60 * 60)
    #     # availability_time = datetime.timedelta(hours=int(time_difference))
    #     if int(utc_datetime_formatted) < int(deployment_time):
    #         sec_to_add = int(((int(deployment_time) - int(timestamp)) * 60 * 60) + int(time_difference))
    #     elif int(utc_datetime_formatted) > int(deployment_time):
    #         sec_to_add = int(((24 - int(timestamp) + int(deployment_time)) * 60 * 60) + int(time_difference))

    # validate if a URL was supplied (in input variable) - thanks https://stackoverflow.com/a/52455972
    def is_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def get_oauth_token(self, oauth_client_id, oauth_client_secret, oauth_token_url):
        request_body = {"grant_type": "client_credentials",
                        "client_id": oauth_client_id,
                        "client_secret": oauth_client_secret
                        }
        try:
            r = requests.post(oauth_token_url, data=request_body)
            r.raise_for_status()
        except requests.exceptions.HTTPError as err:
            raise ProcessorError(f'WorkSpaceOneImporter: Oauth token server response code: {err}')
        except requests.exceptions.RequestException as e:
            raise ProcessorError(f'WorkSpaceOneImporter: Something went wrong when getting Oauth token: {e}')
        result = r.json()
        return result['access_token']

    def get_oauth_headers(self, oauth_client_id, oauth_client_secret, oauth_token_url):
        oauth_token = self.get_oauth_token(oauth_client_id, oauth_client_secret, oauth_token_url)
        headers = {"Authorization": f"Bearer {oauth_token}",
                   "Accept": "application/json",
                   "Content-Type": "application/json"}
        return headers

    def get_smartgroup_id(self, base_url, smartgroup, headers):
        """Get Smart Group ID to assign the package to"""

        # we need to replace any spaces with '%20' for the API call
        condensed_sg = smartgroup.replace(" ", "%20")
        r = requests.get(base_url + "/api/mdm/smartgroups/search?name=%s" % condensed_sg, headers=headers)
        if not r.status_code == 200:
            raise ProcessorError(
                f'WorkSpaceOneImporter: No SmartGroup ID found for SmartGroup {smartgroup} - bailing out.')
        try:
            smart_group_results = r.json()
            for sg in smart_group_results["SmartGroups"]:
                if smartgroup in sg["Name"]:
                    sg_id = sg["SmartGroupID"]
                    self.output(f'Smart Group ID: {sg_id}')
                    break
        except:
            raise ProcessorError(f"failed to parse results from Smart Group search API call")
        return sg_id

    def ws1_import(self, pkg_path, pkg_info_path, icon_path):
        self.output(
            "Beginning the WorkSpace ONE import process for %s." % self.env["NAME"])  ## Add name of app being imported
        BASEURL = self.env.get("ws1_api_url")
        CONSOLEURL = self.env.get("ws1_console_url")
        GROUPID = self.env.get("ws1_groupid")
        APITOKEN = self.env.get("ws1_api_token")
        USERNAME = self.env.get("ws1_api_username")
        PASSWORD = self.env.get("ws1_api_password")
        SMARTGROUP = self.env.get("ws1_smart_group_name")
        PUSHMODE = self.env.get("ws1_push_mode")
        BASICAUTH = self.env.get("ws1_b64encoded_api_credentials")
        oauth_client_id = self.env.get("ws1_oauth_client_id")
        oauth_client_secret = self.env.get("ws1_oauth_client_secret")
        oauth_token_url = self.env.get("ws1_oauth_token_url")
        force_import = self.env.get("ws1_force_import").lower() in ('true', '1', 't')
        # force_import = self.env.get("ws1_force_import")
        deployment2_delay = self.env.get("ws1_deployment2_delay")

        # if placeholder value is set, ignore and set to None
        if BASICAUTH == 'B64ENCODED_API_CREDENTIALS_HERE':
            self.output('Ignoring standard placeholder value supplied for b64encoded_api_credentials, setting default '
                        'value of None', verbose_level=2)
            BASICAUTH = None

        if not self.is_url(CONSOLEURL):
            self.output('WS1 Console URL input value [{}] does not look like a valid URL, setting example value'
                        .format(CONSOLEURL), verbose_level=2)
            CONSOLEURL = 'https://my-mobile-admin-console.my-org.org'

        # if recipe writer gave us a single string instead of a list of strings,
        # convert it to a list of strings
        if isinstance(self.env["ws1_smart_group2_names"], str):
            self.env["ws1_smart_group2_names"] = [self.env["ws1_smart_group2_names"]]

        # Get some global variables for later use
        # app_version = self.env["munki_importer_summary_result"]["data"]["version"]
        # app_name = self.env["munki_importer_summary_result"]["data"]["name"]
        # get app name and version from pkginfo, don't rely on munki_importer_summary_result being filled in current session
        try:
            with open(pkg_info_path, 'rb') as fp:
                pkg_info = plistlib.load(fp)
        except IOError:
            raise ProcessorError(f"Could not read pkg_info file [{pkg_info_path}]")
        except:
            raise ProcessorError(f"Failed to parse pkg_info file [{pkg_info_path}] somehow.")
        if "version" not in pkg_info:
            raise ProcessorError(f"version not found in pkginfo [{pkg_info_path}]")
        app_version = pkg_info["version"]
        if "name" not in pkg_info:
            raise ProcessorError(f"name not found in pkginfo [{pkg_info_path}]")
        app_name = pkg_info["name"]

        # Init the MacSesh so we can use the trusted certs in macOS Keychains to verify SSL.
        # Needed especially in networks with local proxy and custom certificates.
        macsesh.inject_into_requests()

        # take care of headers for authorization
        if self.is_url(oauth_token_url) and oauth_client_id and oauth_client_secret:
            self.output('Oauth client credentials were supplied, proceeding to use these.')
            headers = self.get_oauth_headers(oauth_client_id, oauth_client_secret, oauth_token_url)
        else:
            # create baseline headers
            if BASICAUTH:  # if specified, take precedence over USERNAME and PASSWORD
                basicauth = BASICAUTH
                self.output('b64encoded_api_credentials found and used for Basic authorization header instead of '
                            'api_username and api_password', verbose_level=1)
            else:  # if NOT specified, use USERNAME and PASSWORD
                hashed_auth = base64.b64encode('{}:{}'.format(USERNAME, PASSWORD).encode("UTF-8"))
                basicauth = 'Basic {}'.format(hashed_auth.decode("utf-8"))
            self.output('Authorization header: {}'.format(basicauth), verbose_level=3)
            headers = {'aw-tenant-code': APITOKEN,
                       'Accept': 'application/json',
                       'Content-Type': 'application/json',
                       'authorization': basicauth}
        headers_v2 = dict(headers)
        headers_v2['Accept'] = headers['Accept'] + ';version=2'
        self.output(f'API v.2 call headers: {headers_v2}', verbose_level=3)

        # get OG ID from GROUPID
        try:
            r = requests.get(BASEURL + '/api/system/groups/search?groupid=' + GROUPID, headers=headers_v2)
            result = r.json()
            r.raise_for_status()
        except AttributeError:
            raise ProcessorError(
                f'WorkSpaceOneImporter: Unable to retrieve an ID for the Organizational GroupID specified: {GROUPID}')
        except requests.exceptions.HTTPError as err:
            raise ProcessorError(
                f'WorkSpaceOneImporter: Server responded with error when making the OG ID API call: {err}')
        except requests.exceptions.RequestException as e:
            ProcessorError(f'WorkSpaceOneImporter: Error making the OG ID API call: {e}')
        if GROUPID in result['OrganizationGroups'][0]['GroupId']:
            ogid = result['OrganizationGroups'][0]['Id']
        self.output('Organisation group ID: {}'.format(ogid), verbose_level=2)

        ## Check if app version is already present on WS1 server
        # TODO: maybe make SmartGroup assignment conditional on results
        try:
            condensed_app_name = app_name.replace(" ", "%20")
            r = requests.get(
                BASEURL + '/api/mam/apps/search?locationgroupid=%s&applicationname=%s' % (ogid, condensed_app_name),
                headers=headers)
            if r.status_code == 200:
                search_results = r.json()
                for app in search_results["Application"]:
                    if app["Platform"] == 10 and app["ActualFileVersion"] == str(app_version) and \
                            app['ApplicationName'] in app_name:
                        ws1_app_id = app["Id"]["Value"]
                        self.output('Pre-existing App ID: %s' % ws1_app_id, verbose_level=2)
                        self.output("Pre-existing App platform: {}".format(app["Platform"]), verbose_level=3)
                        # if not self.env.get("ws1_force_import").lower() == "true":
                        if not force_import:
                            self.output('App [{}] version [{}] is already present on server, '
                                        'and ws1_force_import is not set.'.format(app_name, app_version))
                            return "Nothing new to upload - completed."
                        else:
                            self.output(
                                'App [{}] version [{}] already present on server, and ws1_force_import==True, '
                                'attempting to delete on server first.'.format(app_name, app_version))
                            try:
                                r = requests.delete('{}/api/mam/apps/internal/{}'.format(BASEURL, ws1_app_id),
                                                    headers=headers)
                            except:
                                raise ProcessorError('ws1_force_import - delete of pre-existing app failed, aborting.')
                            if not r.status_code == 202 and not r.status_code == 204:
                                result = r.json()
                                self.output('App delete result: {}'.format(result), verbose_level=3)
                                raise ProcessorError('ws1_force_import - delete of pre-existing app failed, aborting.')
                            try:
                                r = requests.get('{}/api/mam/apps/internal/{}'.format(BASEURL, ws1_app_id),
                                                 headers=headers)
                                if not r.status_code == 401:
                                    result = r.json()
                                    self.output('App not deleted yet, status: {} - retrying'.format(result['Status']),
                                                verbose_level=2)
                                    r = requests.delete('{}/api/mam/apps/internal/{}'.format(BASEURL, ws1_app_id),
                                                        headers=headers)
                            except:
                                raise ProcessorError('ws1_force_import - delete of pre-existing app failed, aborting.')
                            self.output('Pre-existing App [ID: {}] now successfully deleted'.format(ws1_app_id))
                            break
            elif r.status_code == 204:
                # app not found on WS1 server, so we're fine to proceed with upload
                self.output('App [{}] version [{}] is not yet present on server, will attempt upload'
                            .format(app_name, app_version))
        except:
            raise ProcessorError('Something went wrong checking for pre-existing app version on server')

        ## proceed with upload
        if not pkg_path == None:
            self.output("Uploading pkg...")
            # upload pkg, dmg, mpkg file (application/json)
            headers['Content-Type'] = 'application/json'
            posturl = BASEURL + '/api/mam/blobs/uploadblob?filename=' + \
                      os.path.basename(pkg_path) + '&organizationGroupId=' + \
                      str(ogid)
            try:
                res = self.streamFile(pkg_path, posturl, headers)
                pkg_id = res['Value']
                self.output('Pkg ID: {}'.format(pkg_id))
            except KeyError:
                raise ProcessorError('WorkSpaceOneImporter: Something went wrong while uploading the pkg.')
        else:
            raise ProcessorError('WorkSpaceOneImporter: Did not receive a pkg_path from munkiimporter.')

        if not pkg_info_path == None:
            self.output("Uploading pkg_info...")
            # upload pkginfo plist (application/json)
            headers['Content-Type'] = 'application/json'
            posturl = BASEURL + '/api/mam/blobs/uploadblob?filename=' + \
                      os.path.basename(pkg_info_path) + '&organizationGroupId=' + \
                      str(ogid)
            try:
                res = self.streamFile(pkg_info_path, posturl, headers)
                pkginfo_id = res['Value']
                self.output('PkgInfo ID: {}'.format(pkginfo_id))
            except KeyError:
                raise ProcessorError('WorkSpaceOneImporter: Something went wrong while uploading the pkginfo.')
        else:
            raise ProcessorError('WorkSpaceOneImporter: Did not receive a pkg_info_path from munkiimporter.')

        if not icon_path == None:
            self.output("Uploading icon...")
            # upload icon file (application/json)
            headers['Content-Type'] = 'application/json'
            posturl = BASEURL + '/api/mam/blobs/uploadblob?filename=' + \
                      os.path.basename(icon_path) + '&organizationGroupId=' + \
                      str(ogid)
            try:
                res = self.streamFile(icon_path, posturl, headers)
                icon_id = res['Value']
                self.output('Icon ID: {}'.format(icon_id))
            except KeyError:
                self.output('Something went wrong while uploading the icon.')
                self.output('Continuing app object creation...')
                pass
        else:
            icon_id = ''

        ## Create a dict with the app details to be passed to WS1
        ## to create the App object
        ## include applicationIconId only if we have one
        if icon_id:

            app_details = {"pkgInfoBlobId": str(pkginfo_id),
                           "applicationBlobId": str(pkg_id),
                           "applicationIconId": str(icon_id),
                           "version": str(app_version)}
        else:
            app_details = {"pkgInfoBlobId": str(pkginfo_id),
                           "applicationBlobId": str(pkg_id),
                           "version": str(app_version)}

        ## Make the API call to create the App object
        self.output("Creating App Object in WorkSpaceOne...")
        self.output('app_details: {}'.format(app_details), verbose_level=3)
        r = requests.post(BASEURL + '/api/mam/groups/%s/macos/apps' % ogid, headers=headers, json=app_details)
        if not r.status_code == 201:
            result = r.json()
            self.output('App create result: {}'.format(result), verbose_level=3)
            raise ProcessorError('WorkSpaceOneImporter: Unable to create the App Object.')

        ## Now get the new App ID from the server
        # When status_code is 201, the response header "Location" URL holds the ApplicationId after last slash
        self.output("App create response headers: {}".format(r.headers), verbose_level=4)
        ws1_app_id = r.headers["Location"].rsplit('/', 1)[-1]
        self.output("App create ApplicationId: {}".format(ws1_app_id), verbose_level=3)
        app_ws1console_loc = "{}/AirWatch/#/AirWatch/Apps/Details/Internal/{}".format(CONSOLEURL, ws1_app_id)
        self.output("App created, see in WS1 console at: {}".format(app_ws1console_loc))

        # get WS1 Smart Group ID from its name
        sg_id = self.get_smartgroup_id(BASEURL, SMARTGROUP, headers)

        ## Create the app assignment details
        if PUSHMODE == 'Auto':
            setMacOsDesiredStateManagement = True
        else:
            setMacOsDesiredStateManagement = False
        app_assignment = {
            "SmartGroupIds": [
                sg_id
            ],
            "DeploymentParameters": {
                "PushMode": PUSHMODE,
                "AssignmentId": 1,
                "MacOsDesiredStateManagement": setMacOsDesiredStateManagement,  # TODO: maybe expose as input var
                "RemoveOnUnEnroll": False,  # TODO: maybe expose as input var
                "AutoUpdateDevicesWithPreviousVersion": True,  # TODO: maybe expose as input var
                "VisibleInAppCatalog": True  # TODO: maybe expose as input var
            }
        }
        self.ws1_app_assign(BASEURL, SMARTGROUP, app_assignment, headers, ws1_app_id)

        smart_group2_names = self.env.get("ws1_smart_group2_names")
        if smart_group2_names:
            self.output(f"Secondary smart groups are type: [{type(smart_group2_names)}]", verbose_level=2)
            self.output(f"Secondary smart groups are: [{smart_group2_names}]", verbose_level=2)
            sg_ids = []
            for sg in self.env["ws1_smart_group2_names"]:
                # get WS1 Smart Group ID from its name
                sg_id = self.get_smartgroup_id(BASEURL, sg, headers)
                sg_ids.append(f"{sg_id}")
            app_assignment["SmartGroupIds"] = sg_ids

            self.output(f"Secondary smart group deployment delay is: [{deployment2_delay}]", verbose_level=2)

            self.output(f"App assignments data to send: {app_assignment}", verbose_level=2)
            raise ProcessorError("code to make second app assignment with delay not ready yet, bailing out.")
            #self.ws1_app_assign(BASEURL, smart_group2_names[0], app_assignment, headers, ws1_app_id)

        return "Application was successfully uploaded to WorkSpaceOne."

    def ws1_app_assign(self, base_url, smart_group, app_assignment, headers, ws1_app_id):
        """ Call WS1 API to assign app to smart group(s) with the deployment settings """
        try:
            payload = json.dumps(app_assignment)
            self.output(f"App assignments data to send: {app_assignment}", verbose_level=2)
        except:
            raise ProcessorError(f"failed to parse App assignment as json")

        try:
            # Make the WS1 API call to assign the App
            r = requests.post(f"{base_url}/api/mam/apps/internal/{ws1_app_id}/assignments", headers=headers,
                              data=payload)
        except:
            raise ProcessorError(
                f"Something went wrong attempting to assign the app [{self.env['NAME']}] to group [{smart_group}]")
        if not r.status_code == 201:
            result = r.json()
            self.output(f"App assignments failed: {result['errorCode']} - {result['message']}", verbose_level=2)
            raise ProcessorError(
                f"Unable to successfully assign the app [{self.env['NAME']}] to the group [{smart_group}]")
        self.output(f"Successfully assigned the app [{self.env['NAME']}] to the group [{smart_group}]")

    def main(self):
        """Rebuild Munki catalogs in repo_path"""

        cache_dir = get_pref("CACHE_DIR") or os.path.expanduser(
            "~/Library/AutoPkg/Cache")
        current_run_results_plist = os.path.join(
            cache_dir, "autopkg_results.plist")
        try:
            with open(current_run_results_plist, 'rb') as f:
                run_results = plistlib.load(f)
        except IOError:
            run_results = []

        munkiimported_new = False

        # get ws1_import_new_only, defaults to True
        import_new_only = self.env.get("ws1_import_new_only", "True").lower() in ("true", "1", "t")

        try:
            pkginfo_path = self.env["munki_importer_summary_result"]["data"]["pkginfo_path"]
        except:
            pkginfo_path = None

        if pkginfo_path:
            munkiimported_new = True

        if not munkiimported_new and import_new_only:
            self.output(run_results)
            self.output("No updates so nothing to import to WorkSpaceOne")
            self.env["ws1_resultcode"] = 0
            self.env["ws1_stderr"] = ""
            return
        elif not munkiimported_new and not import_new_only:
            self.output("Nothing new imported into Munki repo, but ws1_import_new_only==False so will try to find "
                        "existing matching version in Munki repo.")
            # get cached installer path that was set by MunkiImporter processor in previous recipe step because the one
            # in the Munki repo might be a Git LFS shortcut
            ci = self.env["pkg_path"]
            self.output(f"comparing hash of cached installer [{ci}] to find pkginfo file", verbose_level=2)
            # hash code copied from Munki's pkginfolib.py and function from hash lib munkihash.py
            # get size of installer item
            citemsize = 0
            citemhash = "N/A"
            if os.path.isfile(ci):
                citemsize = int(os.path.getsize(ci))
                try:
                    citemhash = getsha256hash(ci)
                except OSError as err:
                    raise ProcessorError(err)

            # use pkg_repo_path env var set by MunkiImporter to find an existing installer in repo
            pkg = self.env["pkg_repo_path"]
            self.output(f"matching installer already exists in repo [{pkg}]", verbose_level=2)

            munki_repo = self.env["MUNKI_REPO"]
            self.output(f"MUNKI_REPO: {munki_repo}", verbose_level=2)
            if os.path.isfile(pkg):
                itemsize = int(os.path.getsize(pkg))
                installer_item_path = pkg[len(munki_repo) + 1:]  # get path relative from repo
                if not itemsize == citemsize:
                    # item in repo must then be a Git LFS shortcut, pull the real file
                    self.git_lfs_pull(munki_repo, installer_item_path)
                try:
                    itemhash = getsha256hash(pkg)
                    if not itemhash == citemhash:
                        # if your recipe has a DmgCreator step, a different checksum is expected, if DMG, check its checksums
                        if os.path.splitext(pkg)[1][1:].lower() == "dmg":
                            result = subprocess.run( ["hdiutil", "verify", "-quiet", pkg], check=True )
                            if not result.returncode:
                                raise ProcessorError(f"Verify installer failed [{pkg}]")
                        else:
                            raise ProcessorError(
                                    "Installer item in Munki repo differs from cached installer, please check.")
                except OSError as err:
                    raise ProcessorError(err)

                # look in same dir from pkgsinfo/ for matching pkginfo file
                installer_item_dir = os.path.dirname(pkg)
                installer_info_dir = re.sub(r'/pkgs', '/pkgsinfo', installer_item_dir)
                # walk the dir to check each pkginfo file for matching hash
                self.output(f"scanning [{installer_info_dir}] to find matching pkginfo file with installer_item_hash "
                            f"value: [{itemhash}]", verbose_level=2)
                found_match = False
                for (path, dummy_dirs, files) in os.walk(installer_info_dir):
                    for name in files:
                        if name == ".DS_Store":
                            continue
                        pi = os.path.join(path, name)
                        self.output(f"checking [{name}] to find matching installer_item_hash", verbose_level=2)
                        try:
                            with open(pi, 'rb') as fp:
                                pkg_info = plistlib.load(fp)
                        except IOError:
                            raise ProcessorError(f"Could not read pkg_info file [{pi}]")
                        except:
                            raise ProcessorError(f"Could not parse pkg_info file [{pi}]")
                        if "installer_item_hash" in pkg_info and pkg_info["installer_item_hash"] == itemhash:
                            found_match = True
                            iih = pkg_info["installer_item_hash"]
                            self.output(f"installer_item_hash match found: [{iih}]", verbose_level=4)
                            break
                    if found_match:
                        self.output(
                            f"Found matching installer info file in munki repo [{pi}]", verbose_level=2)
                        break
                if not found_match:
                    raise ProcessorError(f"Failed to find matching pkginfo in [{installer_info_dir}]")
            else:
                #
                raise ProcessorError(f"Failed to read installer [{pkg}]")
        else:
            # use paths for newly imported items set by MunkiImporter
            pi = self.env["pkginfo_repo_path"]
            pkg = self.env["pkg_repo_path"]

        # Get icon file settings. Read pkginfo plist file to find if specific icon_path key is present, if so
        # use that. If not, check for common icon file. Proceed to WS1 with what we have regardless.
        try:
            with open(pi, 'rb') as fp:
                pkg_info = plistlib.load(fp)
        except IOError:
            raise ProcessorError("Could not read pkg_info file [{}] to check icon_name ".format(pi))
        except:
            raise ProcessorError("Failed to parse pkg_info file [{}] somehow.".format(pi))
        if "icon_name" not in pkg_info:
            # if key isn't present, look for common icon file with same 'first' name as installer item
            icon_path = self.env["MUNKI_REPO"] + "/icons/" + self.env["NAME"] + ".png"
            self.output("Looking for icon file [{}]".format(icon_path), verbose_level=1)
        else:
            # when icon was specified for this installer version
            icon_path = self.env["MUNKI_REPO"] + "/icons/" + pkg_info["icon_name"]
            self.output("Icon file for this installer version was specified as [{}]".format(icon_path),
                        verbose_level=1)
        # if we can't read or find any icon, proceed with upload regardless
        if not os.path.exists(icon_path):
            self.output("Could not read icon file [{}] - skipping.".format(icon_path))
            icon_path = None
        elif icon_path is None:
            self.output("Could not find any icon file - skipping.")
        self.output(self.ws1_import(pkg, pi, icon_path))


if __name__ == "__main__":
    PROCESSOR = MakeCatalogsProcessor()
    PROCESSOR.execute_shell()

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
import requests  # dependency
import datetime

from autopkglib import Processor, ProcessorError, get_pref
from requests_toolbelt import StreamingIterator  # dependency from requests

from urllib.parse import urlparse

__all__ = ["WorkSpaceOneImporter"]


class WorkSpaceOneImporter(Processor):
    """Uploads apps from Munki repo to WorkSpace ONE"""
    input_variables = {
        "munki_repo_path": {
            "required": True,
            "description": "Path to Munki repo.",
        },
        "force_import": {
            "required": False,
            "description":
                "If \"true\", force import into WS1 if version already exists. Default:false",
        },
        "import_new_only": {
            "required": False,
            "description":
                "If \"false\", in case no version was imported into Munki in this session, find latest version in "
                "munki_repo and import into WS1. Default: true",
        },
        "ws1_api_url": {
            "required": True,
            "description": "Base url of WorkSpace ONE UEM REST API server \
                            (eg. https://myorg.awmdm.com)"
        },
        "ws1_console_url": {
            "required": False,
            "description": "Base url of WorkSpace ONE UEM Console server for easy result lookup \
                            (eg. https://admin-mobile.myorg.com)"
        },
        "ws1_groupid": {
            "required": True,
            "description": "Group ID of WorkSpace ONE Organization Group \
                            where files should be uploaded."
        },
        "api_token": {
            "required": True,
            "description": "WorkSpace ONE REST API Token.",
        },
        "api_username": {
            "required": True,
            "description": "WorkSpace ONE REST API Username.",
        },
        "api_password": {
            "required": True,
            "description": "WorkSpace ONE REST API User Password.",
        },
        "smart_group_name": {
            "required": False,
            "description": "The name of the group that the app should \
                            be assigned to."
        },
        "push_mode": {
            "required": False,
            "description": "Tells WorkSpace ONE how to deploy the app, Auto \
                            or On-Demand."
        },
        "deployment_date": {
            "required": False,
            "description": "This sets the date that the deployment of \
                            the app should begin."
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

    def streamFile(self, filepath, url, headers):
        """expects headers w/ token, auth, and content-type"""
        streamer = StreamingIterator(os.path.getsize(filepath), open(filepath, 'rb'))
        r = requests.post(url, data=streamer, headers=headers)
        return r.json()

    def convertTime(self, deployment_time):
        if int(deployment_time) <= 23:
            if int(deployment_time) is 24:
                self.output("deployment_time was set to 24, changing to 0")
                deployment_time = 0
            else:
                raise ProcessorError("Please enter a valid 24-hour time (i.e. between 0-23)")

        today = datetime.date.today()
        timestamp = time.strftime('%H')
        utc_datetime = datetime.datetime.utcnow()
        utc_datetime_formatted = utc_datetime.strftime("%H")
        time_difference = ((int(utc_datetime_formatted) - int(timestamp)) * 60 * 60)
        # availability_time = datetime.timedelta(hours=int(time_difference))
        if int(utc_datetime_formatted) < int(deployment_time):
            sec_to_add = int(((int(deployment_time) - int(timestamp)) * 60 * 60) + int(time_difference))
        elif int(utc_datetime_formatted) > int(deployment_time):
            sec_to_add = int(((24 - int(timestamp) + int(deployment_time)) * 60 * 60) + int(time_difference))

    # validate if a URL was supplied (in input variable) - thanks https://stackoverflow.com/a/52455972
    def is_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except ValueError:
            return False

    def ws1_import(self, pkg, pkg_path, pkg_info, pkg_info_path, icon, icon_path):
        self.output(
            "Beginning the WorkSpace ONE import process for %s." % self.env["NAME"])  ## Add name of app being imported
        BASEURL = self.env.get("ws1_api_url")
        CONSOLEURL = self.env.get("ws1_console_url")
        GROUPID = self.env.get("ws1_groupid")
        APITOKEN = self.env.get("api_token")
        USERNAME = self.env.get("api_username")
        PASSWORD = self.env.get("api_password")
        SMARTGROUP = self.env.get("smart_group_name")
        PUSHMODE = self.env.get("push_mode")

        if not self.is_url(CONSOLEURL):
            self.output('WS1 Console URL input value [{}] does not look like a valid URL, setting example value'
                        .format(CONSOLEURL), verbose_level=4)
            CONSOLEURL = 'https://my-mobile-admin-console.my-org.org'

        ## get import_new_only, defaults to True
        if self.env.get("import_new_only") is None:
            self.output('No value supplied for import_new_only, setting default value of'
                        ': true', verbose_level=3)
            IMPORTNEWONLY = True
        else:
            if self.env.get("import_new_only").lower() == 'false':
                IMPORTNEWONLY = False
            else:
                IMPORTNEWONLY = True

        ## Get some global variables for later use
        app_version = self.env["munki_importer_summary_result"]["data"]["version"]
        app_name = self.env["munki_importer_summary_result"]["data"]["name"]

        # create baseline headers
        hashed_auth = base64.b64encode('{}:{}'.format(USERNAME, PASSWORD).encode("UTF-8"))
        basicauth = 'Basic {}'.format(hashed_auth.decode("utf-8"))
        self.output('Authorization header: {}'.format(basicauth), verbose_level=4)
        headers = {'aw-tenant-code': APITOKEN,
                   'Accept': 'octet-stream',
                   'Content-Type': 'application/json',
                   'authorization': basicauth}

        # get OG ID from GROUPID
        try:
            r = requests.get(BASEURL + '/api/system/groups/search?name=' + GROUPID, headers=headers)
            result = r.json()
        except AttributeError:
            raise ProcessorError(
                'WorkSpaceOneImporter: Unable to retrieve an ID for the Organizational Group specified: %s' % GROUPID)
        except:
            raise ProcessorError('WorkSpaceOneImporter: Something went wrong when making the OG ID API call.')

        if not r.status_code == 200:
            self.output('Organisation group ID Search result: {}'.format(result), verbose_level=3)
            raise ProcessorError('WorkSpaceOneImporter: Something went wrong when making the OG ID API call.')

        if GROUPID in result['LocationGroups'][0]['GroupId']:
            ogid = result['LocationGroups'][0]['Id']['Value']
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
                    if app["ActualFileVersion"] == str(app_version) and app['ApplicationName'] in app_name:
                        ws1_app_id = app["Id"]["Value"]
                        self.output('Pre-existing App ID: %s' % ws1_app_id, verbose_level=2)
                        self.output("Pre-existing App platform: {}".format(app["Platform"]), verbose_level=3)
                        if not self.env.get("force_import").lower() == "true":
                            raise ProcessorError('App [{}] version [{}] is already present on server, '
                                                 'and force_import is not set.'.format(app_name, app_version))
                        else:
                            self.output(
                                'App [{}] version [{}] already present on server, and force_import==true, attempting to '
                                'delete on server first.'.format(app_name, app_version))
                            try:
                                r = requests.delete('{}/api/mam/apps/internal/{}'.format(BASEURL, ws1_app_id), headers=headers)
                            except:
                                raise ProcessorError('force_import - delete of pre-existing app failed, aborting.')
                            if not r.status_code == 202 and not r.status_code == 204:
                                result = r.json()
                                self.output('App delete result: {}'.format(result), verbose_level=3)
                                raise ProcessorError('force_import - delete of pre-existing app failed, aborting.')
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
                      os.path.basename(pkg_path) + '&organizationgroup=' + \
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
                      os.path.basename(pkg_info_path) + '&organizationgroup=' + \
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
                      os.path.basename(icon_path) + '&organizationgroup=' + \
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

        ## We need to reset the headers back to JSON
        headers = {'aw-tenant-code': APITOKEN,
                   'authorization': basicauth,
                   'Content-Type': 'application/json'}

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
            raise ProcessorError('WorkSpaceOneImporter: Unable to successfully create the App Object.')

        ## Now get the new App ID from the server
        # When status_code is 201, the response header "Location" URL holds the ApplicationId after last slash
        self.output("App create response headers: {}".format(r.headers), verbose_level=4)
        ws1_app_id = r.headers["Location"].rsplit('/', 1)[-1]
        self.output("App create ApplicationId: {}".format(ws1_app_id), verbose_level=3)
        app_ws1console_loc = "{}/AirWatch/#/AirWatch/Apps/Details/Internal/{}".format(CONSOLEURL, ws1_app_id)
        self.output("App created, see in WS1 console at: {}".format(app_ws1console_loc))

        ## Get the Smart Group ID to assign the package to
        ## we need to replace any spaces with '%20' for the API call
        condensed_sg = SMARTGROUP.replace(" ", "%20")
        r = requests.get(BASEURL + "/api/mdm/smartgroups/search?name=%s" % condensed_sg, headers=headers)
        smart_group_results = r.json()
        for sg in smart_group_results["SmartGroups"]:
            if SMARTGROUP in sg["Name"]:
                sg_id = sg["SmartGroupID"]
                self.output('Smart Group ID: %s' % sg_id)

        ## Create the app assignment details
        if PUSHMODE == 'Auto':
            setMacOsDesiredStateManagement = "true"
        else:
            setMacOsDesiredStateManagement = "false"
        app_assignment = {
            "SmartGroupIds": [
                sg_id
            ],
            "DeploymentParameters": {
                "PushMode": PUSHMODE
            },
            "MacOsDesiredStateManagement": setMacOsDesiredStateManagement,  # TODO: maybe expose as input var
            "RemoveOnUnEnroll": "false",  # TODO: maybe expose as input var
            "AutoUpdateDevicesWithPreviousVersion": "true",  # TODO: maybe expose as input var
            "VisibleInAppCatalog": "true"  # TODO: maybe expose as input var
        }
        self.output("App assignments data to send: {}".format(app_assignment), verbose_level=4)

        ## Make the API call to assign the App
        try:
            r = requests.post(BASEURL + '/api/mam/apps/internal/%s/assignments' % ws1_app_id, headers=headers,
                              json=app_assignment)
        except:
            raise ProcessorError('Something went wrong attempting to assign the app [%s] to the group [%s]' % (
                self.env['NAME'], SMARTGROUP))
        if not r.status_code == 201:
            result = r.json()
            self.output("App assignments failed, result errorCode: {} - {} ".format(result['errorCode'],
                                                                                    result['message']),
                        verbose_level=2)
            raise ProcessorError('Unable to successfully assign the app [%s] to the group [%s]' % (
                self.env['NAME'], SMARTGROUP))
        self.output('Successfully assigned the app [%s] to the group [%s]' % (self.env['NAME'], SMARTGROUP))

        ## Workaround - make extra API call PUT in attempt to modify the App assignment details
        # TODO: troubleshoot API to work consistently, even extra PUT API call to change app Flexible app assignment
        #  details from previous assignments doesn't work reliably for all the Flexible app assignment details like
        #  RemoveOnUnEnroll, even if app was deleted first...
        try:
            r = requests.put(BASEURL + '/api/mam/apps/internal/%s/assignments' % ws1_app_id, headers=headers,
                             json=app_assignment)
        except:
            raise ProcessorError('Something went wrong attempting to modify app [%s] assignment to group [%s]' % (
                self.env['NAME'], SMARTGROUP))
        if not r.status_code == 204:
            result = r.json()
            self.output("App assignment mods failed, result errorCode: {} - {} ".format(result['errorCode'],
                                                                                        result['message']),
                        verbose_level=2)
            raise ProcessorError('Unable to successfully modify the app [%s] assignment details for group [%s]' % (
                self.env['NAME'], SMARTGROUP))
        self.output('Successfully modified the app [%s] assignment to the group [%s]' % (self.env['NAME'], SMARTGROUP))

        return "Application was successfully uploaded to WorkSpaceOne."


    def main(self):
        """Rebuild Munki catalogs in repo_path"""

        cache_dir = get_pref("CACHE_DIR") or os.path.expanduser(
            "~/Library/AutoPkg/Cache")
        current_run_results_plist = os.path.join(
            cache_dir, "autopkg_results.plist")
        try:
            run_results = plistlib.readPlist(current_run_results_plist)
        except IOError:
            run_results = []

        munkiimported_new = False

        IMPORTNEWONLY = True

        try:
            pkginfo_path = self.env["munki_importer_summary_result"]["data"]["pkginfo_path"]
        except:
            pkginfo_path = None

        if pkginfo_path:
            munkiimported_new = True

        if not munkiimported_new and IMPORTNEWONLY:
            self.output(run_results)
            self.output("No updates so nothing to import to WorkSpaceOne")
            self.env["ws1_resultcode"] = 0
            self.env["ws1_stderr"] = ""
        elif not munkiimported_new and not IMPORTNEWONLY:
            # TODO: Find (latest) pkgs/pkginfos version and icon to upload to WS1 from Munki repo
            # Look for Munki code where it finds latest pkg, pkginfo, icon in the repo
            self.output("Nothing new imported into Munki, and processor can\'t find existing version(s) for "
                        "import_new_only==False yet")
            pass
        else:
            pi = self.env["pkginfo_repo_path"]
            pkg = self.env["pkg_repo_path"]

            # TODO: test code to find icon and to upload to WS1 from Munki repo
            # read pkginfo file to find location, if not check if file exists, and if not see if file with app Name
            # exists in icon folder in Munki repo, pass first hit to ws1_import()
            icon_path = None
            try:
                with open(pi, 'rb') as fp:
                    pkg_info = plistlib.load(fp)
            except IOError:
                raise ProcessorError("Could not read pkg_info file [{}] to check icon_name ".format(pkg_info))
            except:
                raise ProcessorError("Failed to parse pkg_info file [{}] somehow.".format(pkg_info))
            if pkg_info["icon_name"] is None:
                # if empty, look for common icon file with same 'first' name as installer item
                icon_path = self.env["munki_repo_path"] + "/icons/" + self.env["NAME"] + ".png"
                self.output("Looking for icon file [{}]".format(icon_path), verbose_level=2)
            else:
                # when icon was specified for this installer version
                icon_path = self.env["munki_repo_path"] + "/icons/" + pkginfo_path["icon_name"]
                self.output("Icon file for this installer version was specified as [{}]".format(icon_path), verbose_level=2)
            if icon_path is None or not path.exists(icon_path):
                self.output("Could not read icon file [{}] - skipping.".format(icon_path))
                icon_path = None
            # if we can't find any icon, proceed with upload regardless
            self.output("Could not find any icon file - skipping.")
            self.output(self.ws1_import('pkg', pkg, 'pkginfo', pi, 'icon', icon_path))


if __name__ == "__main__":
    PROCESSOR = MakeCatalogsProcessor()
    PROCESSOR.execute_shell()

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
import subprocess
import datetime

from autopkglib import Processor, ProcessorError, get_pref
from requests_toolbelt import StreamingIterator  # dependency from requests

__all__ = ["WorkSpaceOneImporter"]


class WorkSpaceOneImporter(Processor):
    """Uploads apps from Munki repo to WorkSpace ONE"""
    input_variables = {
        "munki_repo_path": {
            "required": True,
            "description": "Path to the munki repo.",
        },
        "force_import": {
            "required": False,
            "description":
                "If not false or empty or undefined, force a WS1 import",
        },
        "ws1_api_url": {
            "required": True,
            "description": "Base url of your WorkSpace ONE UEM REST API server \
                            (eg. https://myorg.awmdm.com)"
        },
        "ws1_console_url": {
            "required": False,
            "description": "Base url of your WorkSpace ONE UEM Console server for easy result lookup \
                            (eg. https://admin-mobile.myorg.com)"
        },
        "ws1_groupid": {
            "required": True,
            "description": "Group ID of WorkSpace ONE Organization Group \
                            where files will be uploaded"
        },
        "api_token": {
            "required": True,
            "description": "WorkSpace ONE REST API Token",
        },
        "api_username": {
            "required": True,
            "description": "WorkSpace ONE API Username",
        },
        "api_password": {
            "required": True,
            "description": "WorkSpace ONE API User Password",
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

        ## Get some global variables for later use
        app_version = self.env["munki_importer_summary_result"]["data"]["version"]
        app_name = self.env["munki_importer_summary_result"]["data"]["name"]

        # create baseline headers
        #USERNAME = USERNAME.replace("\\\\", "\\")   # lose extra backslashes in case username holds quotes ones from old AD-style usernames
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

        self.output("App create Location header: ".format(r.headers["Location"]), verbose_level=4)
        # When status_code is 201, the response header "Location" URL holds the ApplicationId after last slash
        application_id = r.headers["Location"].rsplit('/', 1)[-1]
        self.output("App create ApplicationId: ".format(application_id), verbose_level=3)
        if CONSOLEURL:
            app_ws1console_loc = CONSOLEURL + r.headers["Location"].rsplit("//", 1)[-1]
            self.output("Application published, lookup in WS1 console at: ".format(app_ws1console_loc))

        ## Now get the new App ID from the server
        # TODO: move lookup to precede upload sections and make upload and smartgroup assignment conditional on results
        try:
            condensed_app_name = app_name.replace(" ", "%20")
            r = requests.get(BASEURL + '/api/mam/apps/search?locationgroupid=%s&applicationname=%s' % (ogid, condensed_app_name),
                             headers=headers)
            search_results = r.json()
            for app in search_results["Application"]:
                if app["ActualFileVersion"] == str(app_version) and app['ApplicationName'] in app_name:
                    ws1_app_id = app["Id"]["Value"]
                    self.output('App ID: %s' % ws1_app_id, verbose_level=2)
                    self.output("App platform: ".format(app["Platform"]), verbose_level=3)
                    break
        except AttributeError:
            raise ProcessorError('WorkSpaceOneImporter: Unable to retrieve the App ID for the newly created app')

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
        app_assignment = {
            "SmartGroupIds": [
                sg_id
            ],
            "DeploymentParameters": {
                "PushMode": PUSHMODE
            },
            "RemoveOnUnEnroll": "false",                     # TODO: maybe expose as input var
            "MacOsDesiredStateManagement": "false",          # TODO: maybe expose as input var
            "AutoUpdateDevicesWithPreviousVersion": "true",  # TODO: maybe expose as input var
            "VisibleInAppCatalog": "true"                    # TODO: maybe expose as input var
        }
        self.output("App assignments data to send: ".format(app_assignment), verbose_level=4)

        ## Make the API call to assign the App
        r = requests.post(BASEURL + '/api/mam/apps/internal/%s/assignments' % ws1_app_id, headers=headers,
                          json=app_assignment)
        if not r.status_code == 201:
            result = r.json()
            self.output("App assignments failed, result errorCode: {} - {} ".format(result['errorCode'],
                                                                                    result['message']),
                        verbose_level=4)
            self.output('Unable to successfully assign the app [%s] to the group [%s]' % (self.env['NAME'], SMARTGROUP))
        self.output('Successfully assigned the app [%s] to the group [%s]' % (self.env['NAME'], SMARTGROUP))
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

        something_imported = False

        try:
            pkginfo_path = self.env["munki_importer_summary_result"]["data"]["pkginfo_path"]
        except:
            pkginfo_path = None

        # run_results is an array of autopackager.results,
        # which is itself an array.
        # look through all the results for evidence that
        # something was imported
        # this could probably be done as an array comprehension
        # but might be harder to grasp...
        #        for result in run_results:
        #            self.output(result)
        #            for item in result:
        #                if "MunkiImporter" in item.get("Processor"):
        #                    self.output("We found MunkiImporter")
        #                    if item["Output"]["pkginfo_repo_path"]:
        #                        something_imported = True
        #                        break
        if pkginfo_path:
            something_imported = True

        if not something_imported and not self.env.get("force_import"):
            self.output(run_results)
            self.output("No updates so nothing to import to WorkSpaceOne")
            self.env["ws1_resultcode"] = 0
            self.env["ws1_stderr"] = ""
        elif self.env.get("force_import") and not something_imported:
            # TODO: Find latest pkgs/pkginfos version and icon to upload to WS1 from Munki repo
            # Look for Munki code where it finds latest pkg, pkginfo
            # Look for Munki code where it tries to find the icon in the repo
            # need to delete app from WS1 before upload attempt
            pass
        else:
            # TODO: Find icon to upload to WS1 from Munki repo
            # Look for Munki code where it tries to find the icon in the repo
            pi = self.env["pkginfo_repo_path"]
            pkg = self.env["pkg_repo_path"]
            icon_path = None
            # self.output(self.ws1_import('pkginfo', pi))
            # self.output(self.ws1_import('pkg', pkg))

            self.output(self.ws1_import('pkg', pkg, 'pkginfo', pi, 'icon', icon_path))


if __name__ == "__main__":
    PROCESSOR = MakeCatalogsProcessor()
    PROCESSOR.execute_shell()

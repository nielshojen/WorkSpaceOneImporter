# WorkSpaceOneImporter
WorkSpaceOneImporter is an AutoPkg Processor that can automatically import packages into VMWare WorkSpace ONE, as well as assign them to one or multiple smart groups, and set certain deployment options such as Push Mode.
Being adapted from [jprichards/AirWatchImporter](https://github.com/jprichards/AirWatchImporter).

## WORK IN PROGRESS

Done:
 * testing API calls involved for WS1 using Postman -> success
 * forked this repo from [jprichards/AirWatchImporter](https://github.com/jprichards/AirWatchImporter)
 * add roadmap to Readme.md
 * rename files, classes, functions, variable names, and comments to reflect update to WS1 from Airwatch, update license, copyright
 * added stub recipe so shared processor can be found in recipes from other repos
 * get call as Autopkg Shared Processor stub to work from other repo
 * try library dependency install for Autopkg as suggested [here](https://blog.eisenschmiede.com/posts/install-python-modules-in-autopkg-context/) -> working
 * update for Python3
 * update API calls for WS1 as tested with Postman

ToDo:
 * **milestone: get POC working**
 * add code to find icon file
 * implement Force Install
 * maybe expose more app assignment settings as input vars than just PushMode
 * maybe add (optimization) ability to update WS1 metadata and assignment settings
 * maybe add ability to use keychain - [something like this](https://stackoverflow.com/questions/57838889/manage-keychain-to-codesign-macos-ios-app-with-xcodebuild-unattended)
 * maybe remove request dependency by porting to cURL calls [as suggested by Nick McSpadden in MacAdmins Slack](https://macadmins.slack.com/archives/C056155B4/p1577123804089700) - possibly using using URLGetter and pass it to download_with_curl()


## Dependencies

### Server Side
You _must_ be running AirWatch Console 9.3.0.0 or higher.

### Client/AutoPkg Side

Currently, in order to run AirWatchImporter, you must first install two Python libraries:

* The `requests` library
* The `requests_toolbelt` library

These can be installed by running: [(Thanks)](https://blog.eisenschmiede.com/posts/install-python-modules-in-autopkg-context/)

```
sudo -H /Library/AutoPkg/Python3/Python.framework/Versions/Current/bin/pip3 install requests
sudo -H /Library/AutoPkg/Python3/Python.framework/Versions/Current/bin/pip3 install requests_toolbelt
```

## AutoPkg Shared Processor

As of AutoPkg 0.4.0 you can use this processor as a shared processor.

Add the processor repo:

```
autopkg repo-add https://github.com/codeskipper/WorkSpaceOneImporter.git
```

Then use this as the processor in your recipes:

```
com.github.codeskipper.WorkSpaceOneImporter/WorkSpaceOneImporter
```

See this wiki for more information on shared processor:
https://github.com/autopkg/autopkg/wiki/Processor-Locations


## Sensitive input variables
The processor requires the following sensitive keys to be populated in your recipe (override) Input variables, or by command line keys. I'm told you can use a CI/CD tool like Github actions to wrap credentials securely as secrets and inject to your Autopkg action(script).

ws1_api_url

api_username

api_password


## Available Input Variables
** ToDo: update WiKi **
* [`munki_repo_path`](https://github.com/jprichards/AirWatchImporter/wiki/munki_repo_path)
* [`force_import`](https://github.com/jprichards/AirWatchImporter/wiki/force_import)
* [`ws1_api_url`](https://github.com/jprichards/AirWatchImporter/wiki/airwatch_url)
* [`ws1_groupid`](https://github.com/jprichards/AirWatchImporter/wiki/airwatch_groupid)
* [`api_token`](https://github.com/jprichards/AirWatchImporter/wiki/api_token)
* [`api_username`](https://github.com/jprichards/AirWatchImporter/wiki/api_username)
* [`api_password`](https://github.com/jprichards/AirWatchImporter/wiki/api_password)
* [`smart_group_name`](https://github.com/jprichards/AirWatchImporter/wiki/smart_group_name)
* [`push_mode`](https://github.com/jprichards/AirWatchImporter/wiki/push_mode)

* ** ToDo: update WiKi **

## Sample Processor

```
<key>Process</key>
<array>
	<dict>
		<key>Processor</key>
		<string>com.github.codeskipper.WorkSpaceOneImporter/WorkSpaceOneImporter</string>
		<key>Arguments</key>
		<dict>
			<key>munki_repo_path</key>
			<string>MUNKI_REPO_PATH_HERE</string>
			<key>ws1_api_url</key>
			<string>WORKSPACEONE_API_URL_HERE</string>
			<key>ws1_groupid</key>
			<string>GROUP_ID_HERE</string>
			<key>api_token</key>
			<string>API_TOKEN_HERE</string>
			<key>api_username</key>
			<string>API_USERNAME_HERE</string>
			<key>api_password</key>
			<string>API_PASSWORD_HERE</string>
			<key>smart_group_name</key>
			<string>SMART_GROUP_NAME</string>
			<key>push_mode</key>
			<string>PUSH_MODE, Auto or On-Demand</string>
		</dict>
	</dict>
</array>
```

## Example AutoPkg Recipe

Example recipe below for Suspicious Package.ws1.recipe  is from:
https://github.com/codeskipper/autopkg-recipes/blob/main/Suspicious%20Package/SuspiciousPackage.ws1.recipe

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Description</key>
	<string>Creates a munki package for Suspicious Package, imports it into WorkSpace ONE.</string>
	<key>Identifier</key>
	<string>com.github.codeskipper.ws1.SuspiciousPackage</string>
	<key>Input</key>
	<dict>
		<key>MUNKI_REPO_PATH</key>
		<string>MUNKI_REPO_PATH_HERE</string>
		<key>WS1_API_URL</key>
		<string>WORKSPACEONE_API_URL_HERE</string>
		<key>WS1_GROUPID</key>
		<string>GROUP_ID_HERE</string>
		<key>API_TOKEN</key>
		<string>API_TOKEN_HERE</string>
		<key>API_USERNAME</key>
		<string>API_USERNAME_HERE</string>
		<key>API_PASSWORD</key>
		<string>API_PASSWORD_HERE</string>
		<key>SMART_GROUP_NAME</key>
		<string>SMART_GROUP_NAME</string>
		<key>PUSH_MODE</key>
		<string>PUSH_MODE</string>
	</dict>
	<key>ParentRecipe</key>
	<string>com.github.codeskipper.munki.SuspiciousPackage</string>
	<key>MinimumVersion</key>
	<string>0.4.0</string>
	<key>Process</key>
	<array>
		<dict>
			<key>Processor</key>
			<string>com.github.codeskipper.WorkSpaceOneImporter/WorkSpaceOneImporter</string>
			<key>Arguments</key>
			<dict>
				<key>munki_repo_path</key>
				<string>%MUNKI_REPO_PATH%</string>
				<key>ws1_api_url</key>
				<string>%WS1_API_URL%</string>
				<key>ws1_groupid</key>
				<string>%WS1_GROUPID%</string>
				<key>api_token</key>
				<string>%API_TOKEN%</string>
				<key>api_username</key>
				<string>%API_USERNAME%</string>
				<key>api_password</key>
				<string>%API_PASSWORD%</string>
				<key>smart_group_name</key>
				<string>%SMART_GROUP_NAME%</string>
				<key>push_mode</key>
				<string>%PUSH_MODE%</string>
			</dict>
		</dict>
	</array>
</dict>
</plist>
```

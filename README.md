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
 * **milestone: get POC working**
 * test new input "ws1_console_url" and code that produces link to imported app
 * get force_import working

ToDo:
 * add code to find icon file to upload
 * cleanup code
 * maybe expose more app assignment settings as input vars
 * maybe add ability to update WS1 metadata and assignment settings
 * maybe add ability to use keychain
 * maybe remove request dependency by porting to cURL calls [as suggested by Nick McSpadden in MacAdmins Slack](https://macadmins.slack.com/archives/C056155B4/p1577123804089700) - possibly using using URLGetter and pass it to download_with_curl()
 * maybe add ability and input setting whether to upload all versions of a software title


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

## Sensitive input variables
The processor currently requires sensitive keys like password and API token to be populated in your recipe (override) Input variables, or by command line keys.

It might be feasible for standalone use to create the ability to use the Keychain to improve security for standalone use.  I took a peek at - [something like this](https://stackoverflow.com/questions/57838889/manage-keychain-to-codesign-macos-ios-app-with-xcodebuild-unattended)

I'm told you can use a CI/CD tool like Github actions to wrap credentials securely as secrets and inject to your Autopkg action(script).



## Available Input Variables
* [`munki_repo_path`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/munki_repo_path)
* [`api_token`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/api_token)
* [`api_username`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/api_username)
* [`api_password`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/api_password)
* [`ws1_api_url`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_api_url)
* [`ws1_console_url`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_console_url)
* [`ws1_groupid`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_groupid)
* [`force_import`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/force_import)
* [`import_new_only`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/import_new_only)
* [`smart_group_name`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/smart_group_name)
* [`push_mode`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/push_mode)

## Sample Processor
```
<key>Process</key>
<array>
	<dict>
		<key>Processor</key>
		<string>com.github.codeskipper.WorkSpaceOneImporter/WorkSpaceOneImporter</string>
		<key>Arguments</key>
		<dict>
			<key>api_token</key>
			<string>API_TOKEN_HERE</string>
			<key>api_username</key>
			<string>API_USERNAME_HERE</string>
			<key>api_password</key>
			<string>API_PASSWORD_HERE</string>
			<key>munki_repo_path</key>
			<string>MUNKI_REPO_PATH_HERE</string>
			<key>ws1_api_url</key>
			<string>WORKSPACEONE_API_URL_HERE</string>
			<key>ws1_console_url</key>
			<string>WORKSPACEONE_CONSOLE_URL_HERE</string>
			<key>ws1_groupid</key>
			<string>GROUP_ID_HERE</string>
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
		<key>API_TOKEN</key>
		<string>API_TOKEN_HERE</string>
		<key>API_USERNAME</key>
		<string>API_USERNAME_HERE</string>
		<key>API_PASSWORD</key>
		<string>API_PASSWORD_HERE</string>
		<key>MUNKI_REPO_PATH</key>
		<string>MUNKI_REPO_PATH_HERE</string>
		<key>WS1_API_URL</key>
		<string>WORKSPACEONE_API_URL_HERE</string>
		<key>WS1_CONSOLE_URL</key>
		<string>WORKSPACEONE_CONSOLE_URL_HERE</string>
		<key>WS1_GROUPID</key>
		<string>GROUP_ID_HERE</string>
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
				<key>api_token</key>
				<string>%API_TOKEN%</string>
				<key>api_username</key>
				<string>%API_USERNAME%</string>
				<key>api_password</key>
				<string>%API_PASSWORD%</string>
				<key>ws1_api_url</key>
				<string>%WS1_API_URL%</string>
				<key>ws1_groupid</key>
				<string>%WS1_GROUPID%</string>
				<key>ws1_console_url</key>
				<string>%WS1_CONSOLE_URL%</string>
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
___
<br/>Create a recipe override first:<br/>
```autopkg make-override SuspiciousPackage.ws1.recipe```

<br/>Edit it for settings to fit your environment<br/>
```open -a bbedit SuspiciousPackage.ws1.recipe```

<br/>Test like this, and beware: verbose level 4 will show your password etc in plaintext on screen
````
autopkg run -vvvv --key force_munkiimport=true --key force_import=false SuspiciousPackage.ws1.recipe
````

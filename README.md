# WorkSpaceOneImporter
WorkSpaceOneImporter is an AutoPkg Processor that can automatically import packages into VMWare WorkSpace ONE, as well as assign them to one or multiple smart groups, and set certain deployment options such as Push Mode.
Being adapted from [jprichards/AirWatchImporter](https://github.com/jprichards/AirWatchImporter).

## WORKING
Project is working stable in production. You can reach me as @mart in MacAdmins Slack. Issues and PRs welcome in GitHub.

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
 * add code to find icon file to upload
 * merged PR#1 from @SoxIn4 - ability to supply base64 pre-encoded api username and password
 * added support for Oauth
 * added support to specify advanced app assignment (API v.2) settings and update on schedule
 * added production ready example recipes (moved from my autopkg-recipe repo)

ToDo:
 * cleanup code, confirm to Autopkg standards
 * maybe move to Autopkg repo recipe subfolder
 * document usage in wiki
 * maybe establish separate demo repo
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

## Sensitive input variables
The processor currently requires sensitive keys like password and API token to be populated in your recipe (override) Input variables, or by command line keys.

Instead of keeping secrets in plain text recipe override files, they can be added to a macOS keychain. I took a peek at - [this](https://stackoverflow.com/questions/57838889/manage-keychain-to-codesign-macos-ios-app-with-xcodebuild-unattended) and now have a working launcher shell script for a Python wrapper, and I'll share when I can  - it's currently in a private repo for GitHub CI as described below. This is useful for testing, in production I use a CI/CD pipeline on a self-hosted GitHub runner.


### best with CI/CD
You can use a CI/CD tool like Github actions to wrap credentials securely as secrets and inject to your Autopkg action(script). I'm in the process of setting this up and adapting from [the example provided by Gusto](https://engineering.gusto.com/running-autopkg-in-github-actions/). I intend to share the setup when I've got it stable enough for production.



## Available Input Variables

### All start with "ws1_" now
When working to set up GitHub CI with this processor, it became clear consistent naming for input variables will make reading logs etc. much easier. Sorry if this breaks anybodies recipes, it should be easy to fix by adding the new prefix to the variables that don't have it yet.

### Choose your input vars
You'll need to specify credentials for either Oauth or Basic authentication.
<br><br>`ws1_force_import` and `ws1_import_new_only` are intended for troubleshooting (new) recipes.

`ws1_console_url` is there as a convenience, so you can get a direct link to a newly imported package in the WS1 console.

`ws1_smart_group_name` and `ws1_push_mode` let you make simple App Assignments to Assignment Groups, while `ws1_app_assignments` gives you complete control over the App Assignment settings, but needs more settings in the recipe override.

* [`ws1_api_url`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_api_url)
* [`ws1_console_url`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_console_url)
* [`ws1_oauth_client_id`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_oauth_client_id)
* [`ws1_oauth_client_secret`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_oauth_client_secret)
* [`ws1_oauth_token_url`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_oauth_token_url)
* [`ws1_api_token`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_api_token)
* [`ws1_api_username`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_api_username)
* [`ws1_api_password`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_api_password)
* [`ws1_b64encoded_api_credentials`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_b64encoded_api_credentials)
* [`ws1_force_import`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_force_import)
* [`ws1_import_new_only`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_import_new_only)
* [`ws1_groupid`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_groupid)
* [`ws1_smart_group_name`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_smart_group_name)
* [`ws1_push_mode`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_push_mode)
* [`ws1_app_assignments`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_app_assignments)

### Input variables being deprecated
* [`ws1_munki_repo_path`](https://github.com/codeskipper/WorkSpaceOneImporter/wiki/ws1_munki_repo_path)
MUNKI_REPO setting from Autopkg can be used, no need for separate input variable.

### List available input variables
You can list the custom processor info, including input variables from cli like so:

````
autopkg processor-info WorkSpaceOneImporter --recipe com.github.codeskipper.WorkSpaceOneImporter
````

## Sample Processor
```
<key>Process</key>
<array>
	<dict>
		<key>Processor</key>
		<string>com.github.codeskipper.WorkSpaceOneImporter/WorkSpaceOneImporter</string>
		<key>Arguments</key>
		<dict>
			<key>ws1_munki_repo_path</key>
			<string>MUNKI_REPO_PATH_HERE</string>
			<key>ws1_api_token</key>
			<string>API_TOKEN_HERE</string>
			<key>ws1_api_url</key>
			<string>WORKSPACEONE_API_URL_HERE</string>
			<key>ws1_console_url</key>
			<string>WORKSPACEONE_CONSOLE_URL_HERE</string>
			<key>ws1_api_username</key>
			<string>API_USERNAME_HERE</string>
			<key>ws1_api_password</key>
			<string>API_PASSWORD_HERE</string>
			<key>ws1_b64encoded_api_credentials</key>
		    <string>Basic QVBJX1VTRVJOQU1FX0hFUkU6QVBJX1BBU1NXT1JEX0hFUkU=</string>
			<key>ws1_groupid</key>
			<string>GROUP_ID_HERE</string>
			<key>ws1_smart_group_name</key>
			<string>SMART_GROUP_NAME</string>
			<key>ws1_push_mode</key>
			<string>PUSH_MODE, Auto or On-Demand</string>
		</dict>
	</dict>
</array>
```

## Example AutoPkg Recipe

Example recipe below for Suspicious Package.ws1.recipe  is from:
https://github.com/codeskipper/WorkSpaceOneImporter/blob/main/ws1-plist/SuspiciousPackage.ws1-plist.recipe

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
		<key>WS1_API_TOKEN</key>
		<string>API_TOKEN_HERE</string>
		<key>WS1_API_USERNAME</key>
		<string>API_USERNAME_HERE</string>
		<key>WS1_API_PASSWORD</key>
		<string>API_PASSWORD_HERE</string>
		<key>WS1_MUNKI_REPO_PATH</key>
		<string>MUNKI_REPO_PATH_HERE</string>
		<key>WS1_API_URL</key>
		<string>WORKSPACEONE_API_URL_HERE</string>
		<key>WS1_CONSOLE_URL</key>
		<string>WORKSPACEONE_CONSOLE_URL_HERE</string>
		<key>WS1_GROUPID</key>
		<string>GROUP_ID_HERE</string>
		<key>WS1_SMART_GROUP_NAME</key>
		<string>SMART_GROUP_NAME_HERE</string>
		<key>WS1_PUSH_MODE</key>
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
				<key>ws1_munki_repo_path</key>
				<string>%WS1_MUNKI_REPO_PATH%</string>
				<key>ws1_api_token</key>
				<string>%WS1_API_TOKEN%</string>
				<key>ws1_api_username</key>
				<string>%WS1_API_USERNAME%</string>
				<key>ws1_api_password</key>
				<string>%WS1_API_PASSWORD%</string>
				<key>ws1_api_url</key>
				<string>%WS1_API_URL%</string>
				<key>ws1_groupid</key>
				<string>%WS1_GROUPID%</string>
				<key>ws1_console_url</key>
				<string>%WS1_CONSOLE_URL%</string>
				<key>ws1_smart_group_name</key>
				<string>%WS1_SMART_GROUP_NAME%</string>
				<key>ws1_push_mode</key>
				<string>%WS1_PUSH_MODE%</string>
			</dict>
		</dict>
	</array>
</dict>
</plist>
```

### yaml format preferred
More recipes for this processor are available in [my recipe repo](ws1) and those are in yaml format as that is easier to use.
___
Create a recipe override first (if you prefer plist format):
```autopkg make-override SuspiciousPackage.ws1.recipe```

Again yaml format is easier to deal with, especially if you leave only the input variables you need to override and strip away the rest.
```autopkg make-override --format=yaml SuspiciousPackage.ws1.recipe.yaml```

<br/>Edit it for settings to fit your environment<br/>
```open -a bbedit SuspiciousPackage.ws1.recipe.yaml```

<br/>Test like this, but be aware: verbose level > 2 will show your password etc. in plaintext on screen
````
autopkg run -vvvv --key force_munkiimport=true --key force_import=false SuspiciousPackage.ws1.recipe
````

#!/usr/bin/env python

import sys
import json
from base64 import b64encode
import time
import requests
import yaml

# To be run by `setup_client.sh`.

auth = b64encode("admin:password")
url, info_file, config_file, user_file = sys.argv[1:5]
info_file = sys.argv[2]
api_url = url + "/api/v1"
token = None

def action(endpoint, params={}, headers=None, method="get", **kwargs):
    def json_value(value):
        if isinstance(value, str):
            return value
        else:
            return json.dumps(value)
    if headers is None:
        headers = {}
    if token:
        headers.update({"Girder-Token": token})
    params = {key: json_value(value) for key, value in params.iteritems()}
    func = getattr(requests, method)
    r = func(api_url + endpoint, params=params, headers=headers)
    r.raise_for_status()
    return r.json()

response = action("/user/authentication", headers = {"Authorization": "Basic {}".format(auth)})
token = response['authToken']['token']

api_key = action("/api_key", params={"active": True}, method="post")['key']

info = {
    "url": url,
    "api_key": str(api_key),
}
txt = yaml.dump(info, default_flow_style=False)
print(txt)
with open(info_file, 'w') as f:
    f.write(txt)
print("Wrote: {}".format(info_file))

# Merge configuration.
config = yaml.load(open(config_file))

# Write updated config
remotes = config["remotes"]
remotes["master"]["folder_path"] = "/collection/master/files"
remotes["master"]["url"] = url
remotes["devel"]["folder_path"] = "/collection/devel/files"
remotes["devel"]["url"] = url
remotes["devel"]["overlay"] = "master"
config["remote"] = "devel"
with open(config_file, 'w') as f:
    yaml.dump(config, f, default_flow_style=False)

# Generate the user config.
user_config = {
    "girder": {
        "url": {
            url: {
                "api_key": info["api_key"]
            },
        },
    },
}
with open(user_file, 'w') as f:
    yaml.dump(user_config, f, default_flow_style=False)

# Check plugins on the server.
plugins = action("/system/plugins")
my_plugin = "hashsum_download"
if my_plugin not in plugins["all"]:
    raise RuntimeError("Plugin must be installed: {}".format(my_plugin))
enabled = plugins["enabled"]
if my_plugin not in enabled:
    enabled.append(my_plugin)
    print("Enable: {}".format(enabled))
    response = action("/system/plugins", {"plugins": json.dumps(enabled)}, method="put")
    print("Rebuilding...")
    action("/system/web_build", method="post")
    print("Restarting...")
    action("/system/restart", method = "put")
    time.sleep(1)
    print("[ Done ]")

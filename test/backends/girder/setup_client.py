#!/usr/bin/env python

import sys
import json
from base64 import b64encode
import subprocess
import time
from urllib import urlencode
import yaml

def subshell(cmd, strip=True):
    output = subprocess.check_output(cmd, shell=isinstance(cmd, str))
    if strip:
        return output.strip()
    else:
        return output

auth = b64encode("admin:password")
url, info_file, config_file, user_file = sys.argv[1:5]
info_file = sys.argv[2]
api_url = url + "/api/v1"

response = subshell([
    "curl", "-X", "GET", "-s",
        "--header", "Accept: application/json",
        "--header", "Authorization: Basic {}".format(auth),
    "{}/user/authentication".format(api_url)])

token = json.loads(response)['authToken']['token']

def action(endpoint, args = [], method = "GET"):
    extra_args = []
    if method != "GET":
        # https://serverfault.com/a/315852/443276
        extra_args += ["-d", ""]
    response_full = subshell([
        "curl", "-X", method, "-s",
            "--write-out", "\n%{http_code}",
            "--header", "Accept: application/json",
            "--header", "Girder-Token: {}".format(token)] + args + extra_args +
        ["{}{}".format(api_url, endpoint)])
    lines = response_full.splitlines()
    response = "\n".join(lines[0:-1])
    code = int(lines[-1])
    if code >= 400:
        raise RuntimeError("Bad response for: {}\n  {}".format(endpoint, response))
    return json.loads(response)

api_key = action('/api_key?active=true', method = "POST")['key']

def get_folder_id(collection_name):
    parent_id = action('/collection?text={}'.format(collection_name))[0]["_id"]
    folder_id = action('/folder?parentType=collection&parentId={}'.format(parent_id))[0]["_id"]
    return folder_id

# Get folder ids.
devel_id = get_folder_id('devel')
master_id = get_folder_id('master')
private_id = get_folder_id('private')

info = {
    "url": url,
    "api_key": str(api_key),
    "folders": {
        "master": str(master_id),
        "devel": str(devel_id),
        "private": str(private_id),
    },
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
remotes["master"]["folder_id"] = info["folders"]["master"]
remotes["master"]["url"] = url
remotes["devel"]["folder_id"] = info["folders"]["devel"]
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
    qs = urlencode({"plugins": json.dumps(enabled)})
    print("Enable: {}".format(enabled))
    response = action("/system/plugins?{}".format(qs), method = "PUT")
    print("Rebuilding...")
    action("/system/web_build", method = "POST")
    print("Restarting...")
    action("/system/restart", method = "PUT")
    time.sleep(1)
    print("[ Done ]")

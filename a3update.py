#!/usr/bin/python3

# MIT License
#
# Copyright (c) 2017 Marcel de Vries
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import os.path
import re
import shutil
import subprocess

from datetime import datetime
from urllib import request

def env_defined(key: str):
    return key in os.environ and len(os.environ[key]) > 0

def debug(message: str):
    if env_defined('DEBUG') and os.environ['DEBUG'] == '1':
        print(message)

# Print all environment variables.
debug(os.environ)


#region Configuration
STEAM_CMD_DOWNLOAD = 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz'
STEAM_CMD_FOLDER = '/steamcmd'
STEAM_CMD = "{}/steamcmd.sh".format(STEAM_CMD_FOLDER)
STEAM_USER = os.environ["STEAM_USERNAME"]
STEAM_PASS = os.environ["STEAM_PASSWORD"]

A3_SERVER_DIR = "/arma3"
A3_SERVER_ID = "233780"
A3_WORKSHOP_ID = "107410"

A3_STEAM_WORKSHOP_DIR = "{}/steamapps/workshop/content/{}".format(A3_SERVER_DIR, A3_WORKSHOP_ID)
A3_LOCAL_MODS_DIR = "{}/mods".format(A3_SERVER_DIR) # Local mod folder
A3_SERVER_MODS_DIR = "{}/servermods".format(A3_SERVER_DIR) # Server mod folder
A3_KEYS_DIR = "{}/keys".format(A3_SERVER_DIR)
WORKSHOP_MODS = {} # Loaded names and ids from workshop, WORKSHOP_MODS[mod_name] = mod_id
WORKSHOP_UPDATE_MODS = [] # List of workshop mod ids that need a update

CONFIG_KEYS_REGEX = re.compile(r"(.+?)(?:\s+)?=(?:\s+)?(.+?)(?:$|\/|;)", re.MULTILINE)

WORKSHOP_ID_REGEX = re.compile(r"filedetails\/\?id=(\d+)\"", re.MULTILINE)
LAST_UPDATED_REGEX = re.compile(r"workshopAnnouncement.*?<p id=\"(\d+)\">", re.DOTALL)
MOD_NAME_REGEX = re.compile(r"workshopItemTitle\">(.*?)<\/div", re.DOTALL)
WORKSHOP_CHANGELOG_URL = "https://steamcommunity.com/sharedfiles/filedetails/changelog"
#endregion


def log(msg: str):
    print("")
    print("{{0:=<{}}}".format(len(msg)).format(""))
    print(msg)
    print("{{0:=<{}}}".format(len(msg)).format(""))


def call_steamcmd(params: str):
    debug('steamcmd {}'.format(params))
    os.system("{} {}".format(STEAM_CMD, params))
    print("")


def read_config_values(config_path):
    config_values = {}
    with open(config_path) as data:
        config_data = data.read()
        matches = re.finditer(CONFIG_KEYS_REGEX, config_data)
        for _, match in enumerate(matches, start=1):
            config_values[match.group(1).lower()] = match.group(2)
    return config_values


def update_server():
    steam_cmd_params = " +force_install_dir {}".format(A3_SERVER_DIR)
    steam_cmd_params += " +login {} {}".format(STEAM_USER, STEAM_PASS)
    steam_cmd_params += " +app_update {}".format(A3_SERVER_ID)
    if env_defined("STEAM_BRANCH"):
        steam_cmd_params += " -beta {}".format(os.environ["STEAM_BRANCH"])
    if env_defined("STEAM_BRANCH_PASSWORD"):
        steam_cmd_params += " -betapassword {}".format(os.environ["STEAM_BRANCH_PASSWORD"])
    if os.environ["STEAM_VALIDATE"] == '1':
        steam_cmd_params += " validate"
    steam_cmd_params += " +quit"
    call_steamcmd(steam_cmd_params)


def copy_mod_keys(mod_directory: str):
    mod_keys_directory = os.path.join(mod_directory, "keys")
    if os.path.exists(mod_keys_directory):
        for mod_key_file_name in os.listdir(mod_keys_directory):
            mod_key_file_path = os.path.join(mod_keys_directory, mod_key_file_name)
            if not os.path.isdir(mod_key_file_path):
                shutil.copy2(mod_key_file_path, A3_KEYS_DIR)
    else:
        print("Missing keys:", mod_keys_directory)


def lowercase_workshop_dir(path: str):
    os.system("(cd {} && find . -depth -exec rename -v 's/(.*)\/([^\/]*)/$1\/\L$2/' {{}} \;)".format(path))


def check_workshop_mod(mod_id: str):
    response = request.urlopen("{}/{}".format(WORKSHOP_CHANGELOG_URL, mod_id)).read().decode("utf-8")
    varTest = MOD_NAME_REGEX.search(response)
    if varTest != None:
        mod_name = varTest.group(1)

        mod_last_updated = LAST_UPDATED_REGEX.search(response)
        path = "{}/{}".format(A3_STEAM_WORKSHOP_DIR, mod_id)
        WORKSHOP_MODS[mod_name] = mod_id

        if os.path.isdir(path) and mod_last_updated:
            updated_at = datetime.fromtimestamp(int(mod_last_updated.group(1)))
            created_at = datetime.fromtimestamp(os.path.getctime(path))
            if (updated_at >= created_at or os.environ["FORCE_DOWNLOAD_WORKSHOP"] == '1'):
                # Delete mod directory for re download
                shutil.rmtree(path)
        
        if not os.path.isdir(path):
            print("Update required for \"{}\" ({})".format(mod_name, mod_id))
            WORKSHOP_UPDATE_MODS.append(mod_id)
        else:
            print("No update required for \"{}\" ({})... SKIPPING".format(mod_name, mod_id))
        # Copy keys here so it's easier to see the workshop mod that has missing keys
        copy_mod_keys(path)


# builds the steam cli command to download multiple workshop mods at once and fixes the file paths after
def download_updated_workshop_mods():
    if len(WORKSHOP_UPDATE_MODS) == 0:
        debug("No workshop mods needed to be downloaded!")
        return
    debug("Starting download of updated workshop mods...")
    steam_cmd_params = " +force_install_dir {}".format(A3_SERVER_DIR)
    steam_cmd_params += " +login {} {}".format(STEAM_USER, STEAM_PASS)
    for mod_id in WORKSHOP_UPDATE_MODS:
        steam_cmd_params += " +workshop_download_item {} {}".format(
            A3_WORKSHOP_ID,
            mod_id
        )
    if os.environ["STEAM_VALIDATE"] == '1':
        steam_cmd_params += " validate"
    steam_cmd_params += " +quit"
    call_steamcmd(steam_cmd_params)
    # Fix paths to lowercase after downloading
    debug("Fixing any filepaths of workshop mods...")
    for mod_id in WORKSHOP_UPDATE_MODS:
        path = "{}/{}".format(A3_STEAM_WORKSHOP_DIR, mod_id)
        lowercase_workshop_dir(path)


def check_workshop_mods():
    mod_file = os.environ["WORKSHOP_MODS"]
    if (mod_file == ''):
        debug("WORKSHOP_MODS env variable not set, nothing to do.")
        return
    if (mod_file.startswith("http")):
        with open("preset.html", "wb") as f:
            f.write(request.urlopen(mod_file).read())
        mod_file = "preset.html"
    if not os.path.isfile(mod_file):
        raise Exception('\n'.join([
            'Unable to load WORKSHOP_MODS file!',
            'The WORKSHOP_MODS file should be added to the volume in the arma directory'
        ]))
    with open(mod_file) as f:
        html = f.read()
        matches = re.finditer(WORKSHOP_ID_REGEX, html)
        for _, match in enumerate(matches, start=1):
            mod_id = match.group(1)
            check_workshop_mod(mod_id)
    download_updated_workshop_mods()
    debug("Workshop mods ready\n{}".format(WORKSHOP_MODS))


def load_mods_from_dir(directory: str, copyKeys: bool, mod_type = 'mod'): # Loads both local and workshop mods
    load_mods_paths = ''
    for mod_folder_name in os.listdir(directory):
        mod_folder = os.path.join(directory, mod_folder_name)
        if os.path.isdir(mod_folder):
            debug("Found mod \"{}\"".format(mod_folder_name))
            # Mods use relative paths from the arma install directory
            load_mods_paths += " -{}=\"{}\"".format(mod_type, mod_folder.replace('{}/'.format(A3_SERVER_DIR), ''))
            if copyKeys:
                copy_mod_keys(mod_folder)
    return load_mods_paths
#endregion

# Startup checks
if not os.path.isfile(STEAM_CMD):
    log("Downloading steamcmd...")
    os.system("wget -qO- '{}' | tar zxf - -C {}".format(STEAM_CMD_DOWNLOAD, STEAM_CMD_FOLDER))
if os.path.isdir(A3_KEYS_DIR):
    shutil.rmtree(A3_KEYS_DIR)
    os.makedirs(A3_KEYS_DIR)

log("Updating A3 server ({})".format(A3_SERVER_ID))
update_server()

log("Checking for updates for workshop mods...")
check_workshop_mods()

log("Launching Arma3-server...")
config_path = '{}/configs/{}'.format(A3_SERVER_DIR, os.environ["ARMA_CONFIG"])
launch = '{} -limitFPS={} -world={} -config="{}"'.format(
    os.environ["ARMA_BINARY"],
    os.environ["ARMA_LIMITFPS"],
    os.environ["ARMA_WORLD"],
    config_path
)

if os.path.isdir(A3_STEAM_WORKSHOP_DIR):
    debug('Loading Workshop mods:')
    launch += load_mods_from_dir(A3_STEAM_WORKSHOP_DIR, False)

if os.path.isdir(A3_LOCAL_MODS_DIR):
    debug('Loading Local mods:')
    launch += load_mods_from_dir(A3_LOCAL_MODS_DIR, True)

if env_defined("ARMA_CDLC"):
    for cdlc in os.environ["ARMA_CDLC"].split(";"):
        launch += " -mod={}".format(cdlc)

if env_defined("ARMA_PARAMS"):
    launch += " {}".format(os.environ["ARMA_PARAMS"])

headless_client_count = int(os.environ["HEADLESS_CLIENTS"])
if headless_client_count > 0:
    base_client_launch_config = launch
    config_values = read_config_values(config_path)
    if "headlessclients[]" not in config_values or "localclient[]" not in config_values:
        raise Exception('\n'.join([
            'headlessclients or localclient not found in config!',
            'Be sure to add both of the following to your config file.',
            'headlessclients[] = {"127.0.0.1"};',
            'localclient[] = {"127.0.0.1"};'
        ]))
    if "password" in config_values:
        base_client_launch_config += " -client -connect=127.0.0.1 -password={}".format(config_values["password"])
    for i in range(0, headless_client_count):
        client_config = base_client_launch_config + ' -name="{}-hc-{}"'.format(os.environ["ARMA_PROFILE"], i)
        print(client_config)
        subprocess.Popen(client_config, shell=True)

launch += ' -port={} -name="{}" -profiles="{}"'.format(
    os.environ["PORT"],
    os.environ["ARMA_PROFILE"], # profile name
    '{}/configs/profiles'.format(A3_SERVER_DIR) # Broken in linux per wiki, required to be this
)

if os.path.isdir(A3_SERVER_MODS_DIR):
    debug('Loading Server mods:')
    launch += load_mods_from_dir(A3_SERVER_MODS_DIR, True, 'servermod')

print(launch)
os.system(launch)

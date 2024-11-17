#!/usr/bin/env python3
# Python3 script that installs Puppet Agent, Puppetserver and Puppet Bolt on Linux.
# For now this script is designed for use on Ubuntu/Debian systems alongside CentOS/RHEL systems.
# Usage: python3 install_puppet.py <applications> <options>
# Applications:
# - agent: Install Puppet Agent
# - server: Install Puppet Server
# - bolt: Install Puppet Bolt
# Options:
# -h, --help: Show help message and exit
# -a, --agent-version: The version of Puppet agent to install (default is 7)
# -s, --server-version: The version of Puppet server to install (default is 7)
# -b, --bolt-version: The version of Puppet Bolt to install (default is latest)
# -l, --loglevel: Set the log level, options are INFO and VERBOSE (default is INFO)
# Where versions are not specified the latest version will be installed.
# Versions can be specified as a full version number (e.g. 7.25.0) or as a major version number (e.g. 7 for 7.x.x)
# Example: python3 install_puppet.py agent server bolt -a 7 -s 7.25.0 -l VERBOSE

import os
import sys
import subprocess
import logging as log
import argparse
from urllib.request import urlretrieve
import re

# First work out which OS we are running on by checking the /etc/os-release file
# If we're not on a supported release then raise an error and exit
def get_os_id():
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('ID='):
                    os_id = line.split('=')[1].strip()
                    return os_id
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function to extract the version relevant version from the /etc/os-release file
# On CentOS/RHEL this is the VERSION_ID field
# On Ubuntu/Debian it's the VERSION_CODENAME field
def get_os_version(os_id):
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if os_id == 'centos' or os_id == 'rhel':
                    if line.startswith('VERSION_ID='):
                        os_version = line.split('=')[1].strip()
                        return os_version
                elif os_id == 'ubuntu' or os_id == 'debian':
                    if line.startswith('VERSION_CODENAME='):
                        os_version = line.split('=')[1].strip()
                        return os_version
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function to check if the OS is supported
def check_supported_os(os_id):
    log.info("Checking if the OS is supported")
    supported_os = ['ubuntu', 'debian', 'centos', 'rhel']
    if os_id.lower() not in supported_os:
        print(f"Error: Unsupported OS {os_id}")
        sys.exit(1)

# Ensure the script is run as root
def check_root():
    log.info("Checking if the script is run as root")
    if os.geteuid() != 0:
        print("Error: This script must be run as root")
        sys.exit(1)

# This functions checks to see if the requested application is already installed
# Unfortunately these tools often don't appear in the PATH so we need to query the package manager
def check_installed(app):
    log.info(f"Checking if {app} is already installed")
    # Both Puppet Agent and Puppet Bolt has a - in the package name whereas Puppet Server does not :cry:
    if app == 'agent' or app == 'bolt':
        app = f"-{app}"
    app_name = f"puppet{app}"
    # I'm not sure if this is the best way to check for the package manager or not
    if os.path.exists('/usr/bin/apt'):
        cmd = f"dpkg -l | grep {app_name}"
    elif os.path.exists('/usr/bin/yum'):
        cmd = f"rpm -qa | grep {app_name}"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        output = subprocess.check_output(cmd, shell=True)
        if output:
            return True
    except subprocess.CalledProcessError:
        return False

# Function to download the relevant rpm/deb package to /tmp
def download_package(app, major_version, os_version):
    log.info(f"Downloading {app} package")
    if os.path.exists('/usr/bin/apt'):
        # Both puppet-agent and puppetserver use the same deb package whereas puppet-bolt uses a different one
        if app == 'agent' or app == 'server':
            url = f"https://apt.puppet.com/puppet{major_version}-release-{os_version}.deb"
        elif app == 'bolt':
            url = f"https://apt.puppet.com/puppet-tools-release-{os_version}.deb"
    elif os.path.exists('/usr/bin/yum'):
        # Again puppet-agent and puppetserver use the same rpm package whereas puppet-bolt uses a different one
        if app == 'agent' or app == 'server':
            url = f"https://yum.puppetlabs.com/puppet{major_version}-release-el-{os_version}.noarch.rpm"
        elif app == 'bolt':
            url = f"https://yum.puppet.com/puppet-tools-release-el-{os_version}.noarch.rpm"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        log.info(f"Downloading {app} package from {url}")
        path, headers = urlretrieve(url, f"/tmp/puppet-{app}-release-{major_version}.deb")
        return path
    except Exception as e:
        if headers:
            log.info(f"Headers: {headers}")
        print(f"Error: {e}")
        sys.exit(1)

# Function to install the downloaded package
def install_package(app, path):
    log.info(f"Installing {app} package")
    if os.path.exists('/usr/bin/apt'):
        cmd = f"dpkg -i {path}"
    elif os.path.exists('/usr/bin/yum'):
        cmd = f"rpm -i {path}"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function to install the given application
# If the version parameter is passed in then install that specific version
# Otherwise install the latest version
def install_app(app, version, os_version):
    log.info(f"Installing {app}")
    # Both Puppet Agent and Puppet Bolt has a - in the package name whereas Puppet Server does not :cry:
    if app == 'agent' or app == 'bolt':
        app = f"-{app}"
    if os.path.exists('/usr/bin/apt'):
        if version:
            cmd = f"apt update && apt-get install -y puppet{app}={version}-1{os_version}"
        else:
            cmd = f"apt-get install -y puppet{app}"
    elif os.path.exists('/usr/bin/yum'):
        if version:
            cmd = f"yum install -y puppet{app}-{version}"
        else:
            cmd = f"yum install -y puppet{app}"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function to parse the command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Install Puppet Agent, Puppet Server and Puppet Bolt on Linux")
    parser.add_argument("applications", nargs='+', help="Applications to install", choices=['agent', 'server', 'bolt'])
    parser.add_argument("-a", "--agent-version", help="The version of Puppet agent to install", default='7')
    parser.add_argument("-s", "--server-version", help="The version of Puppet server to install", default='7')
    parser.add_argument("-b", "--bolt-version", help="The version of Puppet Bolt to install")
    parser.add_argument("-l", "--loglevel", help="Set the log level", choices=['ERROR', 'INFO'], default='ERROR')
    args = parser.parse_args()
    return args

# Main function
def main():
    # Set up logging - by default only log errors
    log.basicConfig(level=log.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")
    args = parse_args()
    # If the log level is set to INFO then log all messages
    if args.loglevel == 'INFO':
        log.getLogger().setLevel(log.INFO)
    # It's not possible to install different _major_ versions of Puppet Agent and Puppet Server on the same machine
    # (e.g. you can't have Puppet Agent 6 and Puppet Server 7 on the same machine, but 7.25.0 and 7.26.0 is fine)
    # So we need to check if the requested versions are compatible with each other and raise an error if not
    if args.applications == ['agent', 'server']:
        if args.agent_version and args.server_version:
            if args.agent_version.split('.')[0] != args.server_version.split('.')[0]:
                print("Error: Puppet Agent and Puppet Server versions must be in the same major release when installing side by side")
                sys.exit(1)
    os_id = get_os_id()
    check_supported_os(os_id)
    check_root()
    os_version = get_os_version(os_id)
    for app in args.applications:
        if check_installed(app):
            log.info(f"{app} is already installed")
            print(f"{app} is already installed - there is nothing to do")
        else:
            log.info(f"{app} is not installed")
            # The user may have supplied a major version OR a full version to be installed
            # We need to check what they have set - if they've given us a full version then we need to set
            # both the major_version and exact_version variables
            major_version = None
            exact_version = None
            if app == 'agent':
                major_version = args.agent_version.split('.')[0]
                if re.match(r'\d+\.\d+\.\d+', args.agent_version):
                    exact_version = args.agent_version
            elif app == 'server':
                major_version = args.server_version.split('.')[0]
                if re.match(r'\d+\.\d+\.\d+', args.server_version):
                    exact_version = args.server_version
            elif app == 'bolt':
                if args.bolt_version:
                    if re.match(r'\d+\.\d+\.\d+', args.bolt_version):
                        exact_version = args.bolt_version
            path = download_package(app, major_version, os_version)
            install_package(app, path)
            install_app(app, exact_version, os_version)

if __name__ == '__main__':
    main()
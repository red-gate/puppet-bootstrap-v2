#!/usr/bin/env python3

# This script aids in the bootstrapping of a Puppet Server

import os
import sys
import subprocess
import logging as log
import argparse
from urllib.request import urlretrieve
import re
import time

### !!! REMOVE THIS SECTION WHEN TESTING IS COMPLETE !!!
# Global variables to save having to set them multiple times
package_manager = None
os_id = None
os_version = None
# Puppet doesn't put itself on the PATH so we need to specify the full path
puppet_bin = "/opt/puppetlabs/bin/puppet"


# Function to print error messages in red
def print_error(message):
    print("\033[91m" + message + "\033[0m")


def print_important(message):
    print("\033[93m" + message + "\033[0m")


# Function to print a welcome message
def print_welcome():
    message = f"""
    Welcome to the Puppet Agent bootstrap script!
    This script will help you install and configure Puppet Agent on your system.
    You will be prompted for any information needed to begin the bootstrap process.
    Please refer to the README for more information on how to use this script.
    """
    print(message)


# Ensure the script is run as root
def check_root():
    log.info("Checking if the script is run as root")
    if os.geteuid() != 0:
        print_error("Error: This script must be run as root")
        sys.exit(1)


# Function that extracts the OS ID from the /etc/os-release file
def get_os_id():
    log.info("Extracting the OS ID from the /etc/os-release file")
    global os_id
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("ID="):
                    os_id = line.split("=")[1].strip()
                    return os_id
    except Exception as e:
        print_error(f"Unable to determine OS ID. Error: {e}")
        sys.exit(1)


# Function to check if the OS is supported
def check_supported_os():
    log.info("Checking if the OS is supported")
    supported_os = ["ubuntu", "debian", "centos", "rhel"]
    if os_id.lower() not in supported_os:
        print_error(f"Error: Unsupported OS {os_id}")
        sys.exit(1)


# Function to extract the version relevant version from the /etc/os-release file
# On CentOS/RHEL this is the VERSION_ID field
# On Ubuntu/Debian it's the VERSION_CODENAME field
def get_os_version():
    log.info("Extracting the OS version from the /etc/os-release file")
    global os_version
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if os_id == "centos" or os_id == "rhel":
                    if line.startswith("VERSION_ID="):
                        os_version = line.split("=")[1].strip()
                elif os_id == "ubuntu" or os_id == "debian":
                    if line.startswith("VERSION_CODENAME="):
                        os_version = line.split("=")[1].strip()
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(1)


# Function that checks a version string and if necessary splits it into a major and exact version
def split_version(version):
    log.info(f"Splitting version string: {version}")
    major_version = version.split(".")[0]
    if re.match(r"\d+\.\d+\.\d+", version):
        exact_version = version
    else:
        exact_version = None
    return major_version, exact_version


# This functions checks to see if the requested application is already installed
# Unfortunately these tools often don't appear in the PATH so we need to query the package manager
def check_installed(app):
    log.info(f"Checking if {app} is already installed")
    # Both Puppet Agent and Puppet Bolt has a - in the package name whereas Puppet Server does not :cry:
    if app == "agent" or app == "bolt":
        app = f"-{app}"
    app_name = f"puppet{app}"
    # I'm not sure if this is the best way to check for the package manager or not
    if os.path.exists("/usr/bin/apt"):
        cmd = f"dpkg -l | grep {app_name}"
    elif os.path.exists("/usr/bin/yum"):
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
def download_puppet_package_archive(app, major_version):
    log.info(f"Downloading {app} package")
    if package_manager == "apt":
        # Both puppet-agent and puppetserver use the same deb package whereas puppet-bolt uses a different one
        if app == "agent" or app == "server":
            url = (
                f"https://apt.puppet.com/puppet{major_version}-release-{os_version}.deb"
            )
        elif app == "bolt":
            url = f"https://apt.puppet.com/puppet-tools-release-{os_version}.deb"
    elif package_manager == "yum":
        # Again puppet-agent and puppetserver use the same rpm package whereas puppet-bolt uses a different one
        if app == "agent" or app == "server":
            url = f"https://yum.puppetlabs.com/puppet{major_version}-release-el-{os_version}.noarch.rpm"
        elif app == "bolt":
            url = f"https://yum.puppet.com/puppet-tools-release-el-{os_version}.noarch.rpm"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        log.info(f"Downloading {app} package from {url}")
        path, headers = urlretrieve(
            url, f"/tmp/puppet-{app}-release-{major_version}.deb"
        )
        return path
    except Exception as e:
        if headers:
            log.info(f"Headers: {headers}")
        print(f"Error: {e}")
        sys.exit(1)


# Function to install the downloaded package
def install_package_archive(app, path):
    log.info(f"Installing {app} package archive")
    if package_manager == "apt":
        cmd = f"dpkg -i {path}"
    elif package_manager == "yum":
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
def install_puppet_app(app, version):
    log.info(f"Installing {app}")
    # Both Puppet Agent and Puppet Bolt has a - in the package name whereas Puppet Server does not :cry:
    if app == "agent" or app == "bolt":
        app = f"-{app}"
    if package_manager == "apt":
        if version:
            complete_version = f"{version}-1{os_version}"
            install_package(f"puppet{app}", complete_version)
        else:
            install_package(f"puppet{app}")
    elif package_manager == "yum":
        if version:
            install_package(f"puppet{app}", version)
        else:
            install_package(f"puppet{app}")
    else:
        print("Error: No supported package manager found")
        sys.exit(1)


# Function that checks what package manager is available on the system and sets the package_manager variable
def check_package_manager():
    log.info("Checking what package manager is available on the system")
    global package_manager
    if os.path.exists("/usr/bin/apt"):
        package_manager = "apt"
    elif os.path.exists("/usr/bin/yum"):
        package_manager = "yum"
    else:
        print_error("Error: No supported package manager found")
        sys.exit(1)


# Function to check if a package is installed on the system
def check_package_installed(package_name):
    log.info(f"Checking if {package_name} is already installed")
    if package_manager == "apt":
        cmd = f"dpkg -l | grep {package_name}"
    elif package_manager == "yum":
        cmd = f"rpm -qa | grep {package_name}"
    else:
        print_error("Error: No supported package manager found")
        sys.exit(1)
    try:
        output = subprocess.check_output(cmd, shell=True)
        if output:
            return True
    except subprocess.CalledProcessError:
        return False


# Function for installing a package on the system
def install_package(package_name, package_version=None):
    log.info(f"Installing package: {package_name}")
    if package_manager == "apt":
        if package_version:
            cmd = f"apt update && apt-get install -y {package_name}={package_version}"
        else:
            cmd = f"apt-get install -y {package_name}"
    elif package_manager == "yum":
        if package_version:
            cmd = f"yum install -y {package_name}-{package_version}"
        else:
            cmd = f"yum install -y {package_name}"
    else:
        print_error("Error: No supported package manager found")
        sys.exit(1)
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Error: {e}")
        sys.exit(1)


# Function that sets the certificate extension attributes for Puppet agent requests
def set_certificate_extensions(extension_attributes):
    log.info("Setting the certificate extension attributes for Puppet agent requests")
    pp_reg_cert_ext_short_names = [
        "pp_uuid",
        "pp_uuid",
        "pp_instance_id",
        "pp_image_name",
        "pp_preshared_key",
        "pp_cost_center",
        "pp_product",
        "pp_project",
        "pp_application",
        "pp_service",
        "pp_employee",
        "pp_created_by",
        "pp_environment",
        "pp_role",
        "pp_software_version",
        "pp_department",
        "pp_cluster",
        "pp_provisioner",
        "pp_region",
        "pp_datacenter",
        "pp_zone",
        "pp_network",
        "pp_securitypolicy",
        "pp_cloudplatform",
        "pp_apptier",
        "pp_hostname",
    ]

    pp_auth_cert_ext_short_names = ["pp_authorization", "pp_auth_role"]

    valid_extension_short_names = (
        pp_reg_cert_ext_short_names + pp_auth_cert_ext_short_names
    )

    csr_yaml_content = "extension_requests:\n"

    for key, value in extension_attributes.items():
        if key not in valid_extension_short_names:
            raise ValueError(f"Invalid extension short name: {key}")
        csr_yaml_content += f"    {key}: {value}\n"

    csr_yaml_path = "/etc/puppetlabs/puppet/csr_attributes.yaml"

    try:
        with open(csr_yaml_path, "w") as csr_yaml_file:
            csr_yaml_file.write(csr_yaml_content)
    except Exception as e:
        raise Exception(f"Failed to write CSR extension attributes: {e}")


# This function is used to get a response from the user
def get_response(prompt, response_type, mandatory=False):
    response = None

    if response_type == "bool":
        while response is None:
            response = input(f"{prompt} [y]es/[n]o: ").strip().lower()
            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            else:
                print(f"Invalid response '{response}'")
                response = None

    elif response_type == "string":
        if mandatory:
            while not response:
                response = input(f"{prompt}: ").strip()
        else:
            response = input(f"{prompt} (Optional - press enter to skip): ").strip()
        if response:
            return response

    elif response_type == "array":
        if mandatory:
            while not response:
                response = input(
                    f"{prompt} [if specifying more than one separate with a comma]: "
                ).strip()
        else:
            response = input(
                f"{prompt} [if specifying more than one separate with a comma] (Optional - press enter to skip): "
            ).strip()
        if response:
            return response.split(",")

    return None


# Function for getting csr extension attributes from the user
def get_csr_attributes():
    continue_prompt = True
    csr_extensions = {}

    while continue_prompt:
        key_name = get_response(
            "Please enter the key name (e.g pp_environment)", "string", mandatory=True
        )
        value = get_response(
            f"Please enter the value for '{key_name}'", "string", mandatory=True
        )
        csr_extensions[key_name] = value
        continue_prompt = get_response(
            "Would you like to add another key? [y]es/[n]o", "bool"
        )

    return csr_extensions


# Function for setting the puppet configuration options
# See https://www.puppet.com/docs/puppet/7/config_file_main.html for more information
def set_puppet_config_option(config_options, config_file_path=None, section="agent"):
    global puppet_bin
    if config_file_path is None:
        config_file_path = "/etc/puppetlabs/puppet/puppet.conf"

    valid_sections = ["main", "agent", "server", "master", "user"]

    if section not in valid_sections:
        raise ValueError(f"Invalid section: {section}")

    if not os.path.exists(puppet_bin):
        raise FileNotFoundError(f"Could not find the puppet command at {puppet_bin}")

    if not os.path.exists(config_file_path):
        raise FileNotFoundError(
            f"Could not find the puppet configuration file at {config_file_path}"
        )

    for key, value in config_options.items():
        log.info(f"Now setting {key} = {value}")
        command = [
            puppet_bin,
            "config",
            "set",
            key,
            value,
            "--config",
            config_file_path,
            "--section",
            section,
        ]

        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise Exception(
                f"Failed to set the configuration option {key} = {value}: {result.stderr}"
            )


# Example usage:
# set_puppet_config_option({"server": "puppet.example.com", "environment": "production"}, section="agent")


# Function to enable the puppet service
def enable_puppet_service():
    log.info("Enabling the puppet service")
    try:
        subprocess.run(["systemctl", "enable", "puppet"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)


# Function to check if the user wants to change the hostname
def check_hostname_change():
    try:
        current_hostname = subprocess.check_output(["hostname"], text=True).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)
    print_important(f"Current hostname: {current_hostname}")
    change_hostname = get_response("Would you like to change the hostname?", "bool")
    if change_hostname:
        new_hostname = get_response(
            "Please enter the new hostname to set", "string", mandatory=True
        )
        return new_hostname
    else:
        return current_hostname


# Function to change the hostname of the system
def set_hostname(new_hostname):
    log.info(f"Setting the hostname to {new_hostname}")
    try:
        subprocess.run(["hostname", new_hostname], check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to set hostname. Error: {e}")
        sys.exit(1)


### !!! REMOVE THIS SECTION WHEN TESTING IS COMPLETE !!!


# Below is our long list of arguments that we need to pass to the script
def parse_args():
    parser = argparse.ArgumentParser(
        description="Script to provision a new Puppet server"
    )
    parser.add_argument(
        "-v",
        "--version",
        help="The version of Puppet to install\nThis can be just the major version (e.g. '7') or the full version number (e.g. '7.12.0')",
    )
    parser.add_argument(
        "-d",
        "--domain-name",
        help="The name of the domain that the server is in. (e.g. example.com)",
    )
    parser.add_argument(
        "-e",
        "--bootstrap-environment",
        help="The environment that the Puppet server should be bootstrapped from (e.g. production, development)",
    )
    parser.add_argument(
        "--bootstrap-hiera",
        help="The name of the Hiera file to bootstrap the Puppet server with (path is relative to the root of your Puppet code repository)",
    )
    parser.add_argument(
        "-c",
        "--csr-extensions",
        help="The CSR extension attributes to set for the Puppet agent requests",
    )
    parser.add_argument(
        "--puppetserver-class",
        help="The Puppet class to apply to the Puppet server",
    )
    parser.add_argument(
        "--new-hostname",
        help="The new hostname to set for the server",
    )
    parser.add_argument(
        "--github-repo",
        help="The GitHub repository that contains your Puppet code/environment",
    )
    parser.add_argument(
        "--deploy-key",
        help="The deploy key for the GitHub repository (if it's private)",
    )
    parser.add_argument(
        "--eyaml-privatekey",
        help="The private key for the eyaml encryption",
    )
    parser.add_argument(
        "--eyaml-publickey",
        help="The public key for the eyaml encryption",
    )
    parser.add_argument(
        "--r10k-version",
        help="The version of R10k to install",
    )
    parser.add_argument(
        "--hiera-eyaml-version",
        help="The version of Hiera-eyaml to install",
    )
    parser.add_argument(
        "--r10k-path",
        help="The path to the r10k binary",
    )
    parser.add_argument(
        "--puppet-agent-path",
        help="The path to the puppet agent binary",
        default="/opt/puppetlabs/bin/puppet",
    )
    parser.add_argument(
        "--puppetserver-path",
        help="The path to the puppetserver binary",
        default="/opt/puppetlabs/bin/puppetserver",
    )
    parser.add_argument(
        "--skip-optional-prompts",
        help="Skip optional prompts and use default values",
        action="store_true",
    )
    parser.add_argument(
        "--skip-confirmation",
        help="Skip the confirmation prompt",
        action="store_true",
    )
    parser.add_argument(
        "--log-level",
        help="The logging level to use",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )
    return parser.parse_args()


# Small function to check if a given gem is installed
def check_gem_installed(gem_name):
    log.info(f"Checking if {gem_name} is installed")
    try:
        subprocess.run([f"gem list -i {gem_name}"], shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# Function to install a gem
def install_gem(gem_name, gem_version=None):
    log.info(f"Installing {gem_name}")
    if gem_version:
        cmd = f"gem install {gem_name} -v {gem_version}"
    else:
        cmd = f"gem install {gem_name}"
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install {gem_name}. Error: {e}")
        sys.exit(1)


# Function to configure r10k
def configure_r10k(github_repo, environment_name, deploy_key_path=None):
    log.info("Configuring r10k")
    r10k_config = f"""
# The location to use for storing cached Git repos
:cachedir: '/var/cache/r10k'

# A list of git repositories to pull from
:sources:
    :{environment_name}:
    basedir: '/etc/puppetlabs/code/environments'
    remote: '{github_repo}'
"""
    if deploy_key_path:
        r10k_config += f"""
git:
    private_key: '{deploy_key_path}'
"""
    r10k_config_path = "/etc/puppetlabs/r10k/r10k.yaml"
    try:
        with open(r10k_config_path, "w") as f:
            f.write(r10k_config)
    except Exception as e:
        print_error(f"Failed to write r10k configuration file. Error: {e}")
        sys.exit(1)


# Function to deploy environments with r10k
def deploy_environments(r10k_path=None):
    if r10k_path:
        r10k_bin = r10k_path
    else:
        r10k_bin = "/opt/puppetlabs/puppet/bin/r10k"
    try:
        subprocess.run([r10k_bin, "deploy", "environment", "--puppetfile"], check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to deploy environments with r10k. Error: {e}")
        sys.exit(1)

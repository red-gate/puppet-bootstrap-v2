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
import json

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
def check_puppet_app_installed(app):
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
            cmd = f"apt update && apt-get install -y {package_name}"
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
                print_error(f"Invalid response '{response}'")
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


# Small function that prompts for a path on disk and checks if it exists
# If it doesn't then it re-prompts the user
# TODO: Get tab completion working for the path
def prompt_for_path(prompt):
    path = None
    while not path:
        path = get_response(prompt, "string", mandatory=True)
        if not os.path.exists(path):
            print_error(f"Error: The path {path} does not exist")
            path = None
    return path


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
        # N.B: The default of 'production' is assumed in some logic below - be careful if changing this
        default="production",
    )
    parser.add_argument(
        "--bootstrap-hiera",
        help="The name of the Hiera file to bootstrap the Puppet server with (path is relative to the root of your Puppet code repository)",
        # N.B: The default of 'hiera.bootstrap.yaml' is assumed in some logic below - be careful if changing this
        default="hiera.bootstrap.yaml",
    )
    parser.add_argument(
        "-c",
        "--csr-extensions",
        help="The CSR extension attributes to set for the Puppet agent requests",
        # We have to use json.loads to convert the string to a dictionary, there's no other way that I'm aware of
        # to pass a dictionary as a command line argument
        type=json.loads,
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
        "--r10k-repository",
        help="The repository to use for R10k",
    )
    parser.add_argument(
        "--r10k-repository-key",
        help="The deploy/ssh key for the repository (if it's private)",
    )
    parser.add_argument(
        "--r10k-repository-key-owner",
        help="The user on system who should own the deploy key",
        # N.B: The default of 'root' is assumed in some logic below - be careful if changing this
        default="root",
    )
    parser.add_argument(
        "--r10k-version",
        help="The version of R10k to install",
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
        "--eyaml-key-path",
        help="The path to the eyaml keys",
        default="/etc/puppetlabs/puppet/keys",
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
        cmd = f'gem install {gem_name} -v "{gem_version}"'
    else:
        cmd = f"gem install {gem_name}"
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install {gem_name}. Error: {e}")
        sys.exit(1)


# Function to check if a gem is installed using the puppetserver gem command
def check_gem_installed_puppetserver(puppetserver_path, gem_name):
    log.info(f"Checking if {gem_name} is installed")
    cmd = f"{puppetserver_path} gem list -i {gem_name}"
    try:
        subprocess.run(cmd, shell=True, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# Function to install a gem using the puppetserver gem command
def install_gem_puppetserver(puppetserver_path, gem_name, gem_version=None):
    log.info(f"Installing {gem_name}")
    if gem_version:
        cmd = f'{puppetserver_path} gem install {gem_name} -v "{gem_version}"'
    else:
        cmd = f"{puppetserver_path} gem install {gem_name}"
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to install {gem_name}. Error: {e}")
        sys.exit(1)


# Function to copy the eyaml keys to the correct location
def copy_eyaml_keys(eyaml_privatekey, eyaml_publickey, eyaml_key_path):
    log.info("Writing the eyaml keys to the correct location")
    eyaml_publickey_path = os.path.join(eyaml_key_path, "public_key.pkcs7.pem")
    eyaml_privatekey_path = os.path.join(eyaml_key_path, "private_key.pkcs7.pem")
    try:
        with open(eyaml_publickey_path, "w") as f:
            f.write(eyaml_publickey)
        with open(eyaml_privatekey_path, "w") as f:
            f.write(eyaml_privatekey)
    except Exception as e:
        print_error(f"Failed to write eyaml keys. Error: {e}")
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
        # Hope that r10k is in the PATH
        r10k_bin = "r10k"
    try:
        subprocess.run([r10k_bin, "deploy", "environment", "--puppetfile"], check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to deploy environments with r10k. Error: {e}")
        sys.exit(1)


# Function to generate a deploy key (ssh key) for the GitHub repository
def generate_deploy_key(deploy_key_owner, deploy_key_name):
    log.info("Generating a deploy key for the GitHub repository")
    deploy_key_path = f"/home/{deploy_key_owner}/.ssh/{deploy_key_name}"
    print_important(
        "A deploy key will now be generated for you to copy to your repository"
    )
    # If the key already exists then remove it
    if os.path.exists(deploy_key_path):
        print_important("An existing deploy key was found and will be removed")
        try:
            os.remove(deploy_key_path)
            os.remove(deploy_key_path + ".pub")
        except Exception as e:
            print_error(f"Failed to remove existing deploy key. Error: {e}")
            sys.exit(1)
    try:
        subprocess.run(
            [
                "ssh-keygen",
                "-t",
                "rsa",
                "-b",
                "4096",
                "-C",
                "r10k",
                "-f",
                deploy_key_path,
                "-N",
                "",
            ],
            check=True,
        )
        set_deploy_key_permissions(deploy_key_path, deploy_key_owner)
        # Get the contents of the public key to pass to the user
        with open(deploy_key_path + ".pub") as f:
            public_key = f.read()
        print_important(
            f"Please copy the following deploy key to your repository:\n{public_key}"
        )
        print_important(f"Once you've copied the key press enter to continue")
        input()
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to generate deploy key. Error: {e}")
        sys.exit(1)
    return deploy_key_path


# Function to write the deploy key to the correct location if the user is supplying one
# We technically support setting the public key as well but we don't currently ask for it
# As I can't see any reason why we'd need it right now other than it's nice to have
def write_deploy_key(
    private_deploy_key, deploy_key_owner, deploy_key_name, public_deploy_key=None
):
    log.info("Writing the deploy key to the correct location")
    deploy_key_path = f"/home/{deploy_key_owner}/.ssh/{deploy_key_name}"
    deploy_key_pub_path = f"{deploy_key_path}.pub"
    try:
        with open(deploy_key_path, "w") as f:
            f.write(private_deploy_key)
        if public_deploy_key:
            with open(deploy_key_pub_path, "w") as f:
                f.write(public_deploy_key)
    except Exception as e:
        print_error(f"Failed to write deploy key. Error: {e}")
        sys.exit(1)
    set_deploy_key_permissions(deploy_key_path, deploy_key_owner)
    return deploy_key_path


# Function that sets the permissions on the deploy key
def set_deploy_key_permissions(deploy_key_path, deploy_key_owner):
    log.info("Setting the permissions on the deploy key")
    try:
        subprocess.run(["chown", deploy_key_owner, deploy_key_path], check=True)
        # If the public key exists then set the permissions on that too
        if os.path.exists(deploy_key_path + ".pub"):
            subprocess.run(
                ["chown", f"{deploy_key_owner}.", deploy_key_path + ".pub"], check=True
            )
        # Set the ACLs to 0600
        subprocess.run(["chmod", "0600", deploy_key_path], check=True)
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to set deploy key permissions. Error: {e}")
        sys.exit(1)


# Function to add the origin source control to known hosts - this saves us getting prompted when we clone the repository
# especially if we're running unattended!
# We technically support setting the origin to something other than github.com but we don't currently ask for it
def add_origin_to_known_hosts(owner, origin="github.com"):
    log.info(f"Adding {origin} to known hosts")
    print(f"Adding {origin} to known hosts")
    try:
        keyscan = subprocess.check_output(["ssh-keyscan", origin]).decode("utf-8")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to scan github.com key.\n{e}")

    known_hosts_file = f"/{owner}/.ssh/known_hosts"

    try:
        with open(known_hosts_file, "r") as file:
            known_hosts_content = file.read()
    except FileNotFoundError:
        known_hosts_content = None

    if known_hosts_content:
        if not re.search(re.escape(keyscan), known_hosts_content):
            try:
                with open(known_hosts_file, "a") as file:
                    file.write(keyscan)
            except Exception as e:
                raise Exception(f"Failed to add {origin} key.\n{e}")
    else:
        try:
            os.makedirs(os.path.dirname(known_hosts_file), exist_ok=True)
            with open(known_hosts_file, "w") as file:
                file.write(keyscan)
        except Exception as e:
            raise Exception(f"Failed to create known_hosts file.\n{e}")


def main():
    # Set up logging - by default only log errors
    log.basicConfig(level=log.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

    # Set the application we want to install - this will be used later
    app = "server"

    # Ensure we are in an environment that is supported and set some global variables
    get_os_id()
    check_supported_os()
    check_root()
    get_os_version()
    check_package_manager()

    # Parse the command line arguments
    args = parse_args()

    # If the user has supplied either an eyaml private or public key but not the other then error
    if (args.eyaml_privatekey and not args.eyaml_publickey) or (
        args.eyaml_publickey and not args.eyaml_privatekey
    ):
        print_error(
            "Error: When supplying eyaml keys you _must_ supply both the eyaml private and public keys"
        )
        sys.exit(1)

    # Print out a welcome message
    print_welcome()

    ### Check for any information we absolute must have and prompt the user if not provided ###
    if not args.domain_name:
        domain_name = get_response(
            "Please enter the domain name (e.g. example.com)", "string", mandatory=True
        )
    else:
        domain_name = args.domain_name
    # Strip the domain name of any leading dots
    domain_name = domain_name.lstrip(".")

    # Check if the user wants to change the hostname if none is provided
    if not args.new_hostname:
        new_hostname = check_hostname_change()
    else:
        new_hostname = args.new_hostname

    # Ensure the hostname has the domain name appended
    if not new_hostname.endswith(domain_name):
        new_hostname = f"{new_hostname}.{domain_name}"

    # If we don't have a version then we'll need to prompt the user
    if not args.version:
        version_prompt = None
        while not version_prompt or not re.match(r"^\d+(\.\d+)*$", version_prompt):
            version_prompt = input(
                "Enter the version of Puppetserver to install. Can be a major version (e.g. 7) or exact (e.g 7.1.2): "
            )
        version = version_prompt
    else:
        version = args.version

    # Split the version into major and exact versions
    major_version, exact_version = split_version(version)
    if exact_version:
        message_version = exact_version
    else:
        message_version = f"{major_version} (latest available)"
    log.info(f"Major version: {major_version}, Exact version: {exact_version}")

    ### Check for any _optional_ information that and prompt if not provided (as long as we're not skipping the optional prompts) ###
    # If the user hasn't supplied an r10k repository then check if they want to set one
    if not args.r10k_repository:
        if not args.skip_optional_prompts:
            r10k_check = None
            while r10k_check is None:
                r10k_check = get_response("Would you like to use r10k?", "bool")
            if r10k_check:
                r10k_repository = get_response(
                    "Please enter the repository URI for the repo you wish to use with r10k",
                    "string",
                    mandatory=True,
                )
            else:
                r10k_repository = None
        else:
            r10k_repository = None

    # If the user does want to use r10k then we need to prompt for some additional information if not provided
    if r10k_repository:
        # The repository might need an ssh key if it's private, check with the user
        if not args.r10k_repository_key:
            if not args.skip_optional_prompts:
                private_repository_check = None
                while private_repository_check is None:
                    private_repository_check = get_response(
                        "Is the repository private?", "bool"
                    )
                if private_repository_check:
                    r10k_repository_key_check = None
                    while r10k_repository_key_check is None:
                        # NOTE: We require the deploy key to be on disk as reading multiple lines from the user is quite
                        # difficult and error prone - this script is designed to be user friendly
                        r10k_repository_key_check = get_response(
                            "Do you already have a deploy/ssh key for the repository on disk?",
                            "bool",
                        )
                    if r10k_repository_key_check:
                        r10k_repository_key_path = prompt_for_path(
                            "Please enter the path to the deploy/ssh key"
                        )
                        try:
                            with open(r10k_repository_key_path) as f:
                                r10k_repository_key = f.read()
                        except Exception as e:
                            print_error(
                                f"Error: Failed to read the deploy key at {r10k_repository_key_path}. Error: {e}"
                            )
                            sys.exit(1)
                    else:
                        # User does not currently have a key but will need one
                        # We'll generate one for them later
                        r10k_repository_key = None
                        generate_r10k_key = True
                else:
                    r10k_repository_key = None
            else:
                r10k_repository_key = None
        else:
            r10k_repository_key = args.r10k_repository_key
        # If we've got a repository key then and the user hasn't supplied the owner then it will default to 'root'
        # Check if the user wants to change this
        if r10k_repository_key or generate_r10k_key:
            r10k_repository_key_owner = args.r10k_repository_key_owner
            if not args.skip_optional_prompts and r10k_repository_key_owner == "root":
                r10k_repository_key_owner_check = None
                while r10k_repository_key_owner_check is None:
                    r10k_repository_key_owner_check = get_response(
                        "Currently the deploy key owner is set to be 'root'. Would you like to change this?",
                        "bool",
                    )
                if r10k_repository_key_owner_check:
                    r10k_repository_key_owner = get_response(
                        "Please enter the user who should own the deploy key",
                        "string",
                        mandatory=True,
                    )
            else:
                r10k_repository_key_owner = args.r10k_repository_key_owner
        else:
            r10k_repository_key_owner = None
        # If we're using r10k then the default bootstrap environment is 'production' but we can change this
        # if the user wants to
        bootstrap_environment = args.bootstrap_environment
        if not args.skip_optional_prompts and bootstrap_environment == "production":
            bootstrap_environment_check = None
            while bootstrap_environment_check is None:
                bootstrap_environment_check = get_response(
                    "The current bootstrap environment is 'production'. Would you like to change this?",
                    "bool",
                )
            if bootstrap_environment_check:
                bootstrap_environment = get_response(
                    "Please enter the environment to bootstrap from",
                    "string",
                    mandatory=True,
                )
        else:
            bootstrap_environment = args.bootstrap_environment
        # Similarly the default Hiera file is 'hiera.bootstrap.yaml' but we can change this
        bootstrap_hiera = args.bootstrap_hiera
        if not args.skip_optional_prompts and bootstrap_hiera == "hiera.bootstrap.yaml":
            bootstrap_hiera_check = None
            while bootstrap_hiera_check is None:
                bootstrap_hiera_check = get_response(
                    "The current bootstrap Hiera file is 'hiera.bootstrap.yaml'. Would you like to change this?",
                    "bool",
                )
            if bootstrap_hiera_check:
                bootstrap_hiera = get_response(
                    "Please enter the Hiera file to bootstrap with",
                    "string",
                    mandatory=True,
                )
        else:
            bootstrap_hiera = args.bootstrap_hiera
        # If bootstrap_hiera is set we MUST have puppetserver_class set otherwise Puppet apply won't actually do anything
        if bootstrap_hiera and not args.puppetserver_class:
            puppetserver_class = get_response(
                "Please enter the Puppet class to apply to the Puppet server (e.g. puppetserver)",
                "string",
                mandatory=True,
            )
        else:
            puppetserver_class = args.puppetserver_class
        # Finally attempt to work out the repository name from the URI
        # e.g. "git@github.com:my-org/Puppet.git" should give "Puppet"
        # If we fail then just set it to "control_repo"
        try:
            r10k_repo_name = r10k_repository.split("/")[-1].split(".")[0]
        except Exception as e:
            r10k_repo_name = "control_repo"
        if not r10k_repo_name:
            r10k_repo_name = "control_repo"
        if args.r10k_version:
            r10k_version = args.r10k_version
        else:
            r10k_version = None
    else:
        r10k_repository_key = None
        r10k_repository_key_owner = None
        bootstrap_environment = None
        bootstrap_hiera = None
        puppetserver_class = None
        r10k_repo_name = None

    # If the user hasn't supplied the eyaml keys then prompt for them
    if not args.eyaml_privatekey and not args.eyaml_publickey:
        if not args.skip_optional_prompts:
            eyaml_key_check = None
            while eyaml_key_check is None:
                eyaml_key_check = get_response(
                    "Would you like to use eyaml encryption?", "bool"
                )
            if eyaml_key_check:
                eyaml_privatekey_path = prompt_for_path(
                    "Please enter the path to your eyaml PRIVATE key",
                )
                eyaml_publickey_path = prompt_for_path(
                    "Please enter the path to your eyaml PUBLIC key",
                )
                try:
                    with open(eyaml_privatekey_path) as f:
                        eyaml_privatekey = f.read()
                    with open(eyaml_publickey_path) as f:
                        eyaml_publickey = f.read()
                except Exception as e:
                    print_error(f"Failed to read eyaml keys. Error: {e}")
                    sys.exit(1)
            else:
                eyaml_privatekey = None
                eyaml_publickey = None
        else:
            eyaml_privatekey = None
            eyaml_publickey = None
    else:
        eyaml_privatekey = args.eyaml_privatekey
        eyaml_publickey = args.eyaml_publickey

    if eyaml_privatekey and eyaml_publickey:
        eyaml_path = args.eyaml_key_path

    # Check if the user wants to set any CSR extension attributes
    if not args.csr_extensions:
        if not args.skip_optional_prompts:
            csr_extensions_check = None
            while csr_extensions_check is None:
                csr_extensions_check = get_response(
                    "Would you like to set any CSR extension attributes?", "bool"
                )
            if csr_extensions_check:
                csr_extensions = get_csr_attributes()
            else:
                csr_extensions = None
        else:
            csr_extensions = None
    else:
        csr_extensions = args.csr_extensions

    ### Ensure the user is happy before continuing with the bootstrap process ###
    confirmation_message = f"""
The Puppetserver will be configured with the following settings:

    - Puppet version: {message_version}
    - Hostname: {new_hostname}
    - Domain name: {domain_name}
"""
    if r10k_repository:
        confirmation_message += f"    - r10k: enabled\n"
        if r10k_version:
            confirmation_message += f"    - r10k version: {r10k_version}\n"
        confirmation_message += f"    - r10k repository: {r10k_repository}\n"
        if r10k_repository_key:
            confirmation_message += f"    - r10k repository key: <redacted>\n"
        if r10k_repository_key_owner:
            confirmation_message += (
                f"    - r10k repository key owner: {r10k_repository_key_owner}\n"
            )
        if bootstrap_environment:
            confirmation_message += (
                f"    - Bootstrap environment: {bootstrap_environment}\n"
            )
        if bootstrap_hiera:
            confirmation_message += f"    - Bootstrap Hiera file: {bootstrap_hiera}\n"
        if puppetserver_class:
            confirmation_message += f"    - Puppetserver class: {puppetserver_class}\n"
    else:
        confirmation_message += "    - r10k: disabled\n"
    if eyaml_privatekey:
        confirmation_message += "    - eyaml encryption: enabled\n"
        if eyaml_path:
            confirmation_message += f"    - eyaml key path: {eyaml_path}\n"
    else:
        confirmation_message += "    - eyaml encryption: disabled\n"
    if csr_extensions:
        confirmation_message += "    - CSR extension attributes:\n"
        for key, value in csr_extensions.items():
            confirmation_message += f"        - {key}: {value}\n"

    print_important(confirmation_message)

    if not args.skip_confirmation:
        confirmation = get_response("Do you want to continue?", "bool")
        if not confirmation:
            print_error("User cancelled bootstrap process")
            sys.exit(0)
    else:
        # Just to be safe we'll pause for a moment so the user can reade the output
        # Even if the user has skipped the confirmation
        time.sleep(10)

    ### Start the bootstrap process ###
    print_important("Starting the bootstrap process")

    # Update the hostname if it's different
    current_hostname = subprocess.check_output(["hostname"], text=True).strip()
    if current_hostname != new_hostname:
        set_hostname(new_hostname)
        # On the Puppetserver we also need to update the /etc/hostnames file
        # We'll just replace whatever is in there with the new hostname
        try:
            with open("/etc/hostname", "w") as f:
                f.write(new_hostname)
        except Exception as e:
            print_error(f"Failed to write /etc/hostname. Error: {e}")
            sys.exit(1)
        # We also need to update the /etc/hosts file
        try:
            with open("/etc/hosts", "r") as f:
                lines = f.readlines()
            with open("/etc/hosts", "w") as f:
                for line in lines:
                    if current_hostname in line:
                        f.write(line.replace(current_hostname, new_hostname))
                    else:
                        f.write(line)
        except Exception as e:
            print_error(f"Failed to write /etc/hosts. Error: {e}")
            sys.exit(1)

    # Install the Puppet server
    if check_puppet_app_installed(app):
        print_important("Puppet server is already installed, skipping installation")
    else:
        path = download_puppet_package_archive(app, major_version)
        install_package_archive(app, path)
        install_puppet_app(app, exact_version)

    # If using hiera-eyaml then install it as both a regular gem and a puppetserver gem
    if eyaml_privatekey:
        if not check_gem_installed("hiera-eyaml"):
            install_gem("hiera-eyaml", args.hiera_eyaml_version)
        if not check_gem_installed_puppetserver(args.puppetserver_path, "hiera-eyaml"):
            install_gem_puppetserver(
                args.puppetserver_path, "hiera-eyaml", args.hiera_eyaml_version
            )
        # Copy the eyaml keys to the correct location
        copy_eyaml_keys(eyaml_privatekey, eyaml_publickey, eyaml_path)

    # If we've got a bootstrap environment then ensure it's set in the puppet.conf
    if bootstrap_environment:
        set_puppet_config_option(
            {"environment": bootstrap_environment}, section="agent"
        )

    # Set the CSR extension attributes if we have any
    if csr_extensions:
        set_certificate_extensions(csr_extensions)

    # Install and configure r10k if we're using it
    if r10k_repository:
        if not check_gem_installed("r10k"):
            install_gem("r10k", r10k_version)
        # If we need to generate or write a deploy key then do so now
        if generate_r10k_key:
            deploy_key_path = generate_deploy_key(
                r10k_repository_key_owner, "r10k_deploy_key"
            )
        elif r10k_repository_key:
            deploy_key_path = write_deploy_key(
                r10k_repository_key, r10k_repository_key_owner, "r10k_deploy_key"
            )
        # Configure r10k
        configure_r10k(r10k_repository, r10k_repo_name, deploy_key_path)
        # Deploy the environments
        # TODO: Work out how to set r10k_path
        print_important("Performing first run of r10k, this may take some time...")
        deploy_environments()
        # Test that our bootstrap environment exists under /etc/puppetlabs/code/environments
        if not os.path.exists(
            f"/etc/puppetlabs/code/environments/{bootstrap_environment}"
        ):
            print_error(
                f"Error: The bootstrap environment '{bootstrap_environment}' does not exist under /etc/puppetlabs/code/environments. Are you sure it's correct?"
            )
            sys.exit(1)
        # Test that our bootstrap Hiera file exists under /etc/puppetlabs/code/environments/{bootstrap_environment}
        if not os.path.exists(
            f"/etc/puppetlabs/code/environments/{bootstrap_environment}/{bootstrap_hiera}"
        ):
            print_error(
                f"Error: The bootstrap Hiera file '{bootstrap_hiera}' does not exist under /etc/puppetlabs/code/environments/{bootstrap_environment}. Are you sure it's correct?"
            )
            sys.exit(1)
        # Finally keyscan our origin so we don't get prompted when we clone the repository
        add_origin_to_known_hosts()


if __name__ == "__main__":
    main()

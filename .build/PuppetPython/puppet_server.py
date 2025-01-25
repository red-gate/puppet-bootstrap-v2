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

### !!! Common Functions !!! ###

### Local Functions ###
# Below is our long list of arguments that we need to pass to the script
def parse_args():
    parser = argparse.ArgumentParser(
        description="Script to provision a new Puppet server"
    )
    parser.add_argument(
        "-v",
        "--puppetserver-version",
        help="The version of Puppet Server to install\nThis can be just the major version (e.g. '7') or the full version number (e.g. '7.12.0')",
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
        help="The path on disk to the deploy key to be used with the R10k repository (only required if the repository is private)",
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
        help="The path on disk to the eyaml private key, only needed if you wish to use eyaml encryption",
    )
    parser.add_argument(
        "--eyaml-publickey",
        help="The path on disk to the eyaml public key, only needed if you wish to use eyaml encryption",
    )
    parser.add_argument(
        "--hiera-eyaml-version",
        help="The version of Hiera-eyaml to install",
    )
    parser.add_argument(
        "--remove-original-keys",
        help="When supplying r10k/eyaml keys, remove the original keys after writing them to the correct location",
        default=True,
    )
    parser.add_argument(
        "--r10k-path",
        help="The path to the r10k binary",
        # Default to 'r10k' as we hope it's in the PATH
        default="r10k",
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
        help="The path to where to store the eyaml keys",
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
        "--unattended",
        help="Run the script in unattended mode",
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
    # ! 2025-01-19: The puppetserver gem command is warning of a "WARN FilenoUtil"
    # ! error when running the command. It doesn't seem to affect the functionality
    # ! but it's noisy so we'll redirect stderr to /dev/null for the time being
    cmd = f"{puppetserver_path} gem list -i {gem_name} 2>/dev/null"
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
        # Ensure the directory exists
        os.makedirs(eyaml_key_path, exist_ok=True)
        with open(eyaml_publickey_path, "w") as f:
            f.write(eyaml_publickey)
        with open(eyaml_privatekey_path, "w") as f:
            f.write(eyaml_privatekey)
    except Exception as e:
        print_error(f"Failed to write eyaml keys. Error: {e}")
        sys.exit(1)
    return [eyaml_privatekey_path, eyaml_publickey_path]


# Function to configure r10k
# TODO: finish implementing the rugged git provider
def configure_r10k(github_repo, environment_name, deploy_key_path=None, git_provider='shellgit'):
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
    # !!! Setting the private_key option in the r10k configuration file is only supported when using the rugged git provider
    # See: https://github.com/puppetlabs/r10k/blob/main/r10k.yaml.example
    if deploy_key_path and git_provider == 'rugged':
        r10k_config += f"""
git:
    provider: 'rugged'
    private_key: '{deploy_key_path}'
    username: 'git'
"""
    r10k_config_dir = "/etc/puppetlabs/r10k"
    r10k_config_path = f"{r10k_config_dir}/r10k.yaml"
    try:
        os.makedirs(r10k_config_dir, exist_ok=True)
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
    if deploy_key_owner == "root":
        owner_ssh_dir = "/root/.ssh"
    else:
        owner_ssh_dir = f"/home/{deploy_key_owner}/.ssh"
    deploy_key_path = f"{owner_ssh_dir}/{deploy_key_name}"
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


# Function to add the origin source control to known hosts - this is needed when using r10k with the shellgit provider
# as it can't handle the prompt to add the keys and will fail with a 128 exit code
# We technically support setting the origin to something other than github.com but we don't currently ask for it
def add_origin_to_known_hosts(owner, origin="github.com"):
    log.info(f"Adding {origin} to known hosts")
    print(f"Adding {origin} to known hosts")
    try:
        keyscan = subprocess.check_output(["ssh-keyscan", origin]).decode("utf-8")
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to scan github.com key.\n{e}")

    if owner == "root":
        known_hosts_file = "/root/.ssh/known_hosts"
    else:
        known_hosts_file = f"/home/{owner}/.ssh/known_hosts"

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

# Function to set ssh key for the origin in .ssh/config
# This is needed when using r10k with the shellgit provider
# as by default it will only look for the key in the default location
def set_ssh_key_for_origin(owner, deploy_key_path, origin="github.com"):
    log.info(f"Setting ssh key for {origin} in .ssh/config")
    print(f"Setting ssh key for {origin} in .ssh/config")
    if owner == "root":
        ssh_config_file = "/root/.ssh/config"
    else:
        ssh_config_file = f"/home/{owner}/.ssh/config"

    try:
        with open(ssh_config_file, "w") as f:
            f.write(f"Host {origin}\n")
            f.write(f"  IdentityFile {deploy_key_path}\n")
            f.write(f"  User git\n")
    except Exception as e:
        print_error(f"Failed to write ssh config file. Error: {e}")
        sys.exit(1)

def main():
    # Set up logging - by default only log errors
    log.basicConfig(level=log.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

    # Set the application we want to install - this will be used later
    app = "server"
    skip_prompts = False
    skip_ping_check = False
    skip_confirmation = False
    unattended = False

    # Ensure we are in an environment that is supported and set some global variables
    get_os_id()
    check_supported_os()
    check_root()
    get_os_version()
    check_package_manager()

    # Parse the command line arguments
    args = parse_args()

    if args.skip_optional_prompts:
        skip_prompts = True
    if args.skip_confirmation:
        skip_confirmation = True
    if args.unattended:
        skip_prompts = True
        skip_confirmation = True
        unattended = True

    # If the user has supplied either an eyaml private or public key via the CLI but not the other then error
    # we _could_ prompt for the missing key but given that the user has supplied one we'll assume they know what they're doing
    if (args.eyaml_privatekey and not args.eyaml_publickey) or (
        args.eyaml_publickey and not args.eyaml_privatekey
    ):
        print_error(
            "Error: When supplying eyaml keys you _must_ supply both the eyaml private and public keys"
        )
        sys.exit(1)

    # Get the current hostname
    current_hostname = subprocess.check_output(["hostname"], text=True).strip()

    # Print out a welcome message
    print_welcome(app)

    ### Check for required bootstrap information
    # Check if the user wants to change the hostname if none is provided
    if not args.new_hostname and not skip_prompts:
        new_hostname = check_hostname_change()
    elif not args.new_hostname and skip_prompts:
        new_hostname = current_hostname
    else:
        new_hostname = args.new_hostname

    if not re.match(r"\.", new_hostname):
        if unattended:
            print_error(
                "Error: The hostname must be a FQDN. Please provide a hostname with a domain name"
            )
        else:
            while not re.match(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}", new_hostname):
                new_hostname = get_response(
                    "Please enter the new hostname for the server (FQDN)", "string", mandatory=True
                )


    # If we don't have a version then we'll need to prompt the user
    if not args.puppetserver_version:
        version_prompt = None
        while not version_prompt or not re.match(r"^\d+(\.\d+)*$", version_prompt):
            version_prompt = input(
                "Enter the version of Puppetserver to install. Can be a major version (e.g. 7) or exact (e.g 7.1.2): "
            )
        version = version_prompt
    else:
        version = args.puppetserver_version

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
        if not skip_prompts:
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
    else:
        r10k_repository = args.r10k_repository

    # If the user does want to use r10k then we need to prompt for some additional information if not provided
    if r10k_repository:
        # The repository might need an ssh key if it's private, check with the user
        if not args.r10k_repository_key:
            # AFAIK GitHub requires the use of SSH keys for SSH access even if the repository is public
            # and r10k will fail without one when using the shellgit provider
            # Warn the user if the repository URI looks like it's using SSH
            if re.match(r"git@", r10k_repository):
                print_important(
                    "The repository URI looks appears to be using SSH. You likely need to provide a deploy key"
                )
            if not skip_prompts:
                private_repository_check = None
                while private_repository_check is None:
                    private_repository_check = get_response(
                        "Do you need to use an SSH key to access this repository?", "bool"
                    )
                if private_repository_check:
                    r10k_repository_key_check = None
                    while r10k_repository_key_check is None:
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
                        generate_r10k_key = False
                    else:
                        # User does not currently have a key but will need one
                        # We'll generate one for them later
                        r10k_repository_key = None
                        generate_r10k_key = True
                else:
                    r10k_repository_key = None
                    generate_r10k_key = False
            else:
                r10k_repository_key = None
                generate_r10k_key = False
        else:
            r10k_repository_key_path = args.r10k_repository_key
            generate_r10k_key = False
            try:
                with open(r10k_repository_key_path) as f:
                    r10k_repository_key = f.read()
            except Exception as e:
                print_error(
                    f"Error: Failed to read the deploy key at {r10k_repository_key_path}. Error: {e}"
                )
                sys.exit(1)
        # If we've got a repository key then and the user hasn't supplied the owner then it will default to 'root'
        # Check if the user wants to change this
        if r10k_repository_key or generate_r10k_key:
            r10k_repository_key_owner = args.r10k_repository_key_owner
            if not skip_prompts and r10k_repository_key_owner == "root":
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
        # We need to know which environment (aka branch) we're going to bootstrap from
        # The default is 'production' but the user may want to change this
        bootstrap_environment = args.bootstrap_environment
        if not skip_prompts and bootstrap_environment == "production":
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
        if not skip_prompts and bootstrap_hiera == "hiera.bootstrap.yaml":
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
        if not skip_prompts:
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
        eyaml_privatekey_path = args.eyaml_privatekey
        eyaml_publickey_path = args.eyaml_publickey
        try:
            with open(eyaml_privatekey_path) as f:
                eyaml_privatekey = f.read()
            with open(eyaml_publickey_path) as f:
                eyaml_publickey = f.read()
        except Exception as e:
            print_error(f"Failed to read eyaml keys. Error: {e}")
            sys.exit(1)

    if eyaml_privatekey and eyaml_publickey:
        # We don't prompt for this parameter as we've got a default set and if a user knows
        # they need to change it then they'll know how to supply it ;)
        eyaml_path = args.eyaml_key_path

    # Check if the user wants to set any CSR extension attributes
    if not args.csr_extensions:
        if not skip_prompts:
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
"""
    if r10k_repository:
        confirmation_message += f"    - r10k: enabled\n"
        if r10k_version:
            confirmation_message += f"    - r10k version: {r10k_version}\n"
        confirmation_message += f"    - r10k repository: {r10k_repository}\n"
        if r10k_repository_key:
            confirmation_message += f"    - r10k repository key: <redacted>\n"
            if args.remove_original_keys:
                confirmation_message += (
                    "    - r10k repository key will be removed after writing to the correct location\n"
                )
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
        if args.remove_original_keys:
            confirmation_message += "    - eyaml keys will be removed after writing to the correct location\n"
        if eyaml_path:
            confirmation_message += f"    - eyaml key path: {eyaml_path}\n"
    else:
        confirmation_message += "    - eyaml encryption: disabled\n"
    if csr_extensions:
        confirmation_message += "    - CSR extension attributes:\n"
        for key, value in csr_extensions.items():
            confirmation_message += f"        - {key}: {value}\n"

    print_important(confirmation_message)

    if not skip_confirmation:
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
    if current_hostname != new_hostname:
        print_important(f"Setting the hostname to {new_hostname}")
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
        print_important(f"Installing Puppet server")
        path = download_puppet_package_archive(app, major_version)
        install_package_archive(app, path)
        install_puppet_app(app, exact_version)

    # If hiera-eyaml or r10k are being used then we'll need to make sure rubygems is installed
    if eyaml_privatekey or r10k_repository:
        if not check_package_installed("ruby-rubygems"):
            install_package("ruby-rubygems")

    # If using hiera-eyaml then install it as both a regular gem and a puppetserver gem
    if eyaml_privatekey:
        print_important("Configuring hiera-eyaml")
        if not check_gem_installed("hiera-eyaml"):
            install_gem("hiera-eyaml", args.hiera_eyaml_version)
        if not check_gem_installed_puppetserver(args.puppetserver_path, "hiera-eyaml"):
            install_gem_puppetserver(
                args.puppetserver_path, "hiera-eyaml", args.hiera_eyaml_version
            )
        # Copy the eyaml keys to the correct location
        eyaml_key_locations = copy_eyaml_keys(eyaml_privatekey, eyaml_publickey, eyaml_path)

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
        print_important("Configuring r10k")
        bootstrap_environment_path = f"/etc/puppetlabs/code/environments/{bootstrap_environment}"
        bootstrap_hiera_path = f"{bootstrap_environment_path}/{bootstrap_hiera}"
        module_path = f"{bootstrap_environment_path}/modules:{bootstrap_environment_path}/ext-modules"
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
        else:
            deploy_key_path = None
        if deploy_key_path:
            # When using shellgit as the provider for r10k (the default) we need to set the ssh key in .ssh/config
            # Otherwise ssh doesn't know where to find the key and r10k will fail with a 128 error
            set_ssh_key_for_origin(r10k_repository_key_owner, deploy_key_path)
        # Configure r10k
        configure_r10k(r10k_repository, r10k_repo_name, deploy_key_path)
        # Keyscan our origin
        # !!! This _must_ be done before running r10k otherwise it will fail with a 128 error
        add_origin_to_known_hosts(r10k_repository_key_owner)
        # Deploy the environments
        # TODO: Work out how to set r10k_path
        print_important("Performing first run of r10k, this may take some time...")
        deploy_environments()
        # Test that our bootstrap environment exists under /etc/puppetlabs/code/environments
        if not os.path.exists(bootstrap_environment_path):
            print_error(
                f"Error: The bootstrap environment '{bootstrap_environment}' does not exist under /etc/puppetlabs/code/environments. Are you sure it's correct?"
            )
            sys.exit(1)
        # Test that our bootstrap Hiera file exists under /etc/puppetlabs/code/environments/{bootstrap_environment}
        if not os.path.exists(bootstrap_hiera_path):
            print_error(
                f"Error: The bootstrap Hiera file '{bootstrap_hiera}' does not exist under /etc/puppetlabs/code/environments/{bootstrap_environment}. Are you sure it's correct?"
            )
            sys.exit(1)

        # Finally apply
        # We only do this if we have a puppetserver class to apply, if the user is building a custom environment
        # then they'll need to sort out the configuration of Puppet themselves
        if puppetserver_class:
            print_important(f"Applying the {puppetserver_class} class")
            apply_args = [
                'apply',
                f"--hiera_config={bootstrap_hiera_path}",
                f"--modulepath={module_path}",
                "-e",
                f"include {puppetserver_class}",
                '--detailed-exitcodes',
            ]
            try:
                subprocess.run([args.puppet_agent_path] + apply_args, check=True)
            except subprocess.CalledProcessError as e:
                # Puppet may return a 0 or a 2 exit code, 2 means there were changes
                if e.returncode == 2 or e.returncode == 0:
                    print_important("Puppetserver class applied successfully! :tada:")
                    # We should be safe to enable the Puppet service now
                    enable_puppet_service()
                    failed_run = False
                else:
                    failed_run = True
                    print_error(f"Failed to apply the Puppetserver class. Error: {e}")

    # If we've got this far then we're done
    final_message = f"Puppet bootstrap process complete!\n"
    if failed_run:
        final_message += f"Unfortunately the apply of the \"{puppetserver_class}\" was unsuccessful.\n"
        final_message += f"You'll need to check for any errors and correct them before proceeding further.\n"
    else:
        if r10k_repository:
            final_message += f"Puppet should now take over and start managing this node.\n"
    # Generally speaking keeping secure keys around on disk that are no longer needed is a bad idea.
    # If we've successfully copied the keys to the correct location then we can delete the originals
    # (providing the user wants to)
    if r10k_repository_key and not generate_r10k_key:
        # In some cases the user may have copied the key to the correct location themselves, we don't want to delete it!
        if r10k_repository_key_path != deploy_key_path:
            if args.remove_original_keys:
                try:
                    os.remove(r10k_repository_key_path)
                except Exception as e:
                    print_error(f"Failed to remove the original deploy key. Error: {e}")
            else:
                final_message += f"The deploy key you provided at \"{r10k_repository_key_path}\" has been copied to the correct location, you can now safely delete the original if no longer needed.\n"
    if eyaml_privatekey:
        if eyaml_privatekey_path != eyaml_key_locations[0]:
            if args.remove_original_keys:
                try:
                    os.remove(eyaml_privatekey_path)
                except Exception as e:
                    print_error(f"Failed to remove the original eyaml private key. Error: {e}")
            else:
                final_message += f"The eyaml private key you provided at \"{eyaml_privatekey_path}\" has been copied to the correct location, you can now safely delete the originals if no longer needed.\n"
        if eyaml_publickey_path != eyaml_key_locations[1]:
            if args.remove_original_keys:
                try:
                    os.remove(eyaml_publickey_path)
                except Exception as e:
                    print_error(f"Failed to remove the original eyaml public key. Error: {e}")
            else:
                final_message += f"The eyaml public key you provided at \"{eyaml_publickey_path}\" has been copied to the correct location, you can now safely delete the originals if no longer needed.\n"
    # Print the last message and say goodbye
    if failed_run:
        print_important(final_message)
    else:
        print_success(final_message)

if __name__ == "__main__":
    main()

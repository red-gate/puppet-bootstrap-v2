#!/usr/bin/env python3

# This script aids in the installation of Puppet on a Linux system

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

### Local functions ###
# Function to parse the command line arguments
def parse_args():
    # TODO: set types for the arguments
    parser = argparse.ArgumentParser(description="Install Puppet Agent on Linux")
    parser.add_argument(
        "-v",
        "--agent-version",
        help="The version of Puppet agent to install can be just the major version (e.g. '7') or the full version number (e.g. '7.12.0')",
        default="7",
    )
    parser.add_argument("-s", "--puppet-server", help="The Puppet server to connect to")
    parser.add_argument(
        "-e",
        "--environment",
        help="The Puppet environment to use",
        default="production",
    )
    parser.add_argument(
        "-c",
        "--csr-extensions",
        help="The CSR extension attributes to use",
        type=json.loads,
    )
    parser.add_argument("-d", "--domain-name", help="Your domain name")
    parser.add_argument(
        "--puppet-port",
        help="The port the Puppet server is listening on",
        default="8140",
    )
    parser.add_argument("--certname", help="The certificate name to use")
    parser.add_argument(
        "--enable-service", help="Enable the Puppet service", default=True
    )
    parser.add_argument(
        "--wait-for-cert",
        help="How long to wait for the certificate to be signed",
        default=30,
    )
    parser.add_argument("--new-hostname", help="The new hostname to set")
    parser.add_argument(
        "--skip-puppetserver-check",
        help="Skip the Puppet server check",
        action="store_false",
    )
    parser.add_argument(
        "--skip-confirmation", help="Skip the confirmation prompt", action="store_false"
    )
    parser.add_argument(
        "--skip-optional-prompts", help="Skip optional prompts", action="store_false"
    )
    parser.add_argument(
        "--skip-initial-run", help="Skip the initial Puppet run", action="store_false"
    )
    parser.add_argument(
        "--unattended", help="Run the script in unattended mode", action="store_true"
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        help="Set the log level",
        choices=["ERROR", "INFO"],
        default="ERROR",
    )
    args = parser.parse_args()
    return args


# Main function
def main():
    # Set up logging - by default only log errors
    log.basicConfig(level=log.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

    app = "agent"
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

    # Print out a welcome message
    print_welcome(app)

    if args.skip_optional_prompts:
        skip_prompts = True
    if args.skip_puppetserver_check:
        skip_ping_check = True
    if args.skip_confirmation:
        skip_confirmation = True
    if args.unattended:
        skip_prompts = True
        skip_ping_check = True
        skip_confirmation = True
        unattended = True

    ### Check we have all the _required_ information to proceed ###
    # We'll need to know the FQDN of the Puppet server
    if not args.puppet_server:
        if unattended:
            print_error("Error: The Puppet server FQDN is required for bootstrapping")
            sys.exit(1)
        puppet_server = None
        while not puppet_server:
            puppet_server = input("Please enter the FQDN of the Puppet server: ")
    else:
        log.info(f"Puppet server: {args.puppet_server}")
        puppet_server = args.puppet_server
    # We need to know the domain name of the system if it's not been provided
    if not args.domain_name:
        # We'll try an be helpful and work it out for the user if we can
        # We'll start by checking if there's a domain name set on the system
        domain_name = subprocess.check_output(["hostname", "-d"], text=True).strip()
        # If that fails then try to work it out from the Puppet server FQDN
        if not domain_name:
            domain_name = puppet_server.split(".", 1)[1]
        # Always check if the user is happy with the domain name we've worked out
        # (it's very hard to change later in Puppet if we've gotten it wrong so we don't class this as an "optional" prompt)
        if not unattended:
            print_important(f"Domain name: {domain_name}")
            domain_name_check = get_response(
                "Do you want to use this domain name for this machine?", "bool"
            )
            if not domain_name_check:
                domain_name = None
        # If we're running unattended then we'll just have to exit if we don't have a domain name
        else:
            print_error("Error: The domain name is required for bootstrapping")
            sys.exit(1)
        while not domain_name:
            domain_name = input("Please enter the domain name for this node: ")
    else:
        domain_name = args.domain_name
    # Strip the domain name of any leading periods
    domain_name = domain_name.lstrip(".")
    # If we don't have a version then we'll need to prompt the user
    if not args.agent_version:
        version_prompt = None
        while not version_prompt or not re.match(r"^\d+(\.\d+)*$", version_prompt):
            version_prompt = input(
                "Enter the version of Puppet agent to install. Can be a major version (e.g. 7) or exact (e.g 7.1.2): "
            )
        version = version_prompt
    else:
        version = args.agent_version

    # Split the version into major and exact versions
    major_version, exact_version = split_version(version)
    if exact_version:
        message_version = exact_version
    else:
        message_version = f"{major_version} (latest available)"
    log.info(f"Major version: {major_version}, Exact version: {exact_version}")

    # Ensure the Puppet server has the domain appended to it
    if not puppet_server.endswith(domain_name):
        puppet_server = f"{puppet_server}.{domain_name}"
    else:
        puppet_server = puppet_server

    # Check if we can ping the Puppet server, if not then raise an error and exit
    # This helps us avoid half configuring a system and failing at the end
    # If --skip-puppetserver-check is set then we'll skip this check
    if skip_ping_check:
        try:
            subprocess.run(
                ["ping", "-c", "4", puppet_server],
                check=True,
                stdout=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as e:
            print(
                f"Error: Could not ping the Puppet server at {puppet_server}. Are you sure it's correct?"
            )
            sys.exit(1)

    current_hostname = subprocess.check_output(["hostname"], text=True).strip()
    new_hostname = current_hostname

    # Prompt the user for any _optional_ information
    # If --skip-optional-prompts is set then we'll skip this section
    if skip_prompts:
        # If the environment is set to the default of production then check if the user wants to change it
        if args.environment == "production":
            print_important(
                "This machine will be bootstrapped from the 'production' environment"
            )
            environment_check = get_response(
                "Would you like to set a different environment?", "bool"
            )
            if environment_check:
                environment = get_response(
                    "Please enter the environment to use", "string", mandatory=True
                )
            else:
                environment = args.environment
        if not args.csr_extensions:
            csr_check = get_response(
                "Would you like to set any CSR extension attributes?", "bool"
            )
            if csr_check:
                csr_extensions = get_csr_attributes()
            else:
                csr_extensions = None
        else:
            csr_extensions = args.csr_extensions

        if not args.new_hostname:
            new_hostname = check_hostname_change()
        else:
            new_hostname = args.new_hostname

        if not args.certname:
            set_certname = get_response(
                "Would you like to set a custom certificate name?", "bool"
            )
            if set_certname:
                certname = get_response(
                    "Please enter the certificate name to use", "string", mandatory=True
                )
            else:
                certname = None

    # If the new hostname doesn't have the domain appended then add it
    if not new_hostname.endswith(domain_name):
        new_hostname = f"{new_hostname}.{domain_name}"

    ### Ensure the user is happy and wants to proceed ###
    confirmation_message = f"""
Puppet will be installed and configured with the following settings:

    - Puppet Agent version: {message_version}
    - Puppet server: {puppet_server}
    - Puppet port: {args.puppet_port}
    - Puppet environment: {environment}
    - Hostname: {new_hostname}
"""
    if certname:
        confirmation_message += f"    - Certificate name: {certname}"
    if csr_extensions:
        confirmation_message += "    - CSR extension attributes:\n"
        for key, value in csr_extensions.items():
            confirmation_message += f"        - {key}: {value}\n"
    if args.wait_for_cert > 0:
        confirmation_message += (
            f"    - Wait for certificate: {args.wait_for_cert} seconds\n"
        )
    if args.enable_service:
        confirmation_message += "    - Enable the Puppet service: true\n"

    print_important(confirmation_message)

    # Only ask the user to confirm if we're not skipping the confirmation
    if skip_confirmation:
        confirm = get_response("Do you want to proceed?", "bool")
        if not confirm:
            print_error("User cancelled installation")
            sys.exit(0)
    else:
        # Even though the user has skipped the confirmation prompt lets just pause for 10 seconds
        # to make sure they have time to cancel the script if they want to
        time.sleep(10)

    ### Begin the installation process ###
    print_important("Beginning the bootstrap process")

    # Set the hostname
    # We do this first so we can ensure the certname is set correctly
    if new_hostname != current_hostname:
        print_important(f"Setting the hostname to {new_hostname}")
        set_hostname(new_hostname)
        # To ensure we get the correct certname we'll set the certname to the new hostname
        # unless the user has specified a custom certname
        if not certname:
            certname = new_hostname

    # Install the Puppet agent package
    # First check if it's already installed, if it is then we can skip this step
    # We make the decision to still continue with the rest of the bootstrap process
    # if this leads to unforeseen consequences then we can change this behaviour
    # TODO: Fail on version mismatch?
    # TODO: Uninstall and reinstall?
    if check_puppet_app_installed(app):
        log.info(f"{app} is already installed")
        print(f"{app} is already installed - skipping installation")
    else:
        log.info(f"{app} is not installed")
        print_important(f"Installing Puppet...")
        path = download_puppet_package_archive(app, major_version)
        install_package_archive(app, path)
        install_puppet_app(app, exact_version)

    # Set CSR extension attributes if they have been provided
    if csr_extensions:
        set_certificate_extensions(csr_extensions)

    # Set the puppet.conf options
    main_config_options = {"server": puppet_server, "masterport": args.puppet_port}
    if certname:
        main_config_options["certname"] = certname

    agent_config_options = {"environment": environment}

    set_puppet_config_option(main_config_options, section="main")
    set_puppet_config_option(agent_config_options, section="agent")

    # Trigger the initial Puppet run if the user hasn't skipped it
    # Puppet will exit with 2 if there are changes to be applied so we'll ignore that
    if args.skip_initial_run:
        print_important("Performing first Puppet run...")
        puppet_args = [puppet_bin, "agent", "--test", "--detailed-exitcodes"]
        if args.wait_for_cert > 0:
            puppet_args.append(f"--waitforcert")
            puppet_args.append(str(args.wait_for_cert))
            print_important(
                f"Please ensure you sign the certificate for this node on the Puppet server."
            )
        try:
            subprocess.run(puppet_args, check=True)
        except subprocess.CalledProcessError as e:
            if e.returncode == 2 or e.returncode == 0:
                log.info("Puppet run completed successfully")
                first_run = True
            else:
                # If we fail then we'll just log the error and continue with the bootstrap process
                print_error(
                    f"The initial run of Puppet has failed :(\nThe bootstrap process will continue.\nError: {e}"
                )
                first_run = False

    # Enable the Puppet service if the user has requested it
    if args.enable_service:
        enable_puppet_service()

    # Print out a message to the user to let them know what to do next
    final_message = "Bootstrap process complete! :tada:\n"
    if first_run:
        final_message += "The initial Puppet run has completed successfully and Puppet should now be managing this node\n"
    else:
        final_message += "The initial Puppet run has failed :cry: this node is still being managed by Puppet but you'll need to investigate the failure.\n"

    print_important(final_message)


if __name__ == "__main__":
    main()

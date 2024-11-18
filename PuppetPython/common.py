#!/usr/bin/env python3

# A set of common functions used by the PuppetPython scripts

import os
import sys
import logging as log
import subprocess

package_manager = None
os_id = None
os_version = None

# Ensure the script is run as root
def check_root():
    log.info("Checking if the script is run as root")
    if os.geteuid() != 0:
        print("Error: This script must be run as root")
        sys.exit(1)

# Function that extracts the OS ID from the /etc/os-release file
def get_os_id():
    log.info("Extracting the OS ID from the /etc/os-release file")
    global os_id
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('ID='):
                    os_id = line.split('=')[1].strip()
                    return os_id
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function to check if the OS is supported
def check_supported_os():
    log.info("Checking if the OS is supported")
    supported_os = ['ubuntu', 'debian', 'centos', 'rhel']
    if os_id.lower() not in supported_os:
        print(f"Error: Unsupported OS {os_id}")
        sys.exit(1)

# Function to extract the version relevant version from the /etc/os-release file
# On CentOS/RHEL this is the VERSION_ID field
# On Ubuntu/Debian it's the VERSION_CODENAME field
def get_os_version():
    log.info("Extracting the OS version from the /etc/os-release file")
    global os_version
    try:
        with open('/etc/os-release') as f:
            for line in f:
                if os_id == 'centos' or os_id == 'rhel':
                    if line.startswith('VERSION_ID='):
                        os_version = line.split('=')[1].strip()
                elif os_id == 'ubuntu' or os_id == 'debian':
                    if line.startswith('VERSION_CODENAME='):
                        os_version = line.split('=')[1].strip()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

# Function that checks what package manager is available on the system and sets the package_manager variable
def check_package_manager():
    log.info("Checking what package manager is available on the system")
    global package_manager
    if os.path.exists('/usr/bin/apt'):
        package_manager = 'apt'
    elif os.path.exists('/usr/bin/yum'):
        package_manager = 'yum'
    else:
        print("Error: No supported package manager found")
        sys.exit(1)

# Function to check if a package is installed on the system
def check_package_installed(package_name):
    log.info(f"Checking if {package_name} is already installed")
    if package_manager == 'apt':
        cmd = f"dpkg -l | grep {package_name}"
    elif package_manager == 'yum':
        cmd = f"rpm -qa | grep {package_name}"
    else:
        print("Error: No supported package manager found")
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
    if package_manager == 'apt':
        if package_version:
            cmd=f"apt update && apt-get install -y {package_name}={package_version}"
        else:
            cmd=f"apt-get install -y {package_name}"
    elif package_manager == 'yum':
        if package_version:
            cmd=f"yum install -y {package_name}-{package_version}"
        else:
            cmd=f"yum install -y {package_name}"
    else:
        print("Error: No supported package manager found")
        sys.exit(1)
    try:
        subprocess.run(cmd, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        sys.exit(1)

def set_certificate_extensions(extension_attributes):
    """
    Sets CSR extension attributes for Puppet agent requests.

    :param extension_attributes: Dictionary of extension attributes to be set
    :type extension_attributes: dict
    """
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

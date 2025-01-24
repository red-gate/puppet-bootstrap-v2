# Puppet bootstrap scripts

This repository contains a set of scripts to bootstrap the installation and configuration of a Puppet server and Puppet agents.
These scripts are designed to be used in Brownserve environments, but may well be easily adapted to other environments.

The scripts have been tested on the following operating systems:

`bootstrap_puppet-linux.py`:
    - Ubuntu 22.04
    - Ubuntu 24.04

`bootstrap_puppet-windows.py`:
    - Windows Server 2016
    - Windows Server 2019
    - Windows Server 2022
    - Windows 10

`bootstrap_puppet-server.py`:
    - Ubuntu 22.04

## Usage

All scripts can be run fully interactively, or with command line arguments to automate the process.
If you forget to supply a required argument, the script will prompt you for it.
Several checks are performed throughout the process to ensure that the likelihood of failure is minimized.
The script is designed in such a way that it should recover from a failed run, with a simple re-running of the script.

The scripts can also be run completely non-interactively by supplying all required arguments on the command line and passing the `unattended` flag. (see below for more information)

### bootstrap_puppet-linux.py

| **Parameter**                | **Description**                                                                                                                                                                                                                                                                                                     | **Mandatory** | **Default**  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------------ |
| `--agent-version`            | The Version of Puppet Agent to be installed. This can be specified as a major version (e.g. `7`) or an exact version (e.g. `7.1.2`)                                                                                                                                                                                 | N             | `7`          |
| `--new-hostname`             | Allows you to set a new hostname for the node.  ⚠ **NOTE**: Hostnames _must_ be fully qualified on Linux (e.g. `node.example.com`)                                                                                                                                                                              | N             | N/A          |
| `--puppet-server`            | The FQDN of the Puppet server that will manage this node (e.g. `puppetserver.example.com`)                                                                                                                                                                                                                          | Y             | N/A          |
| `--puppet-server-port`       | The port to use to communicate with the Puppet server                                                                                                                                                                                                                                                               | N             | `8140`       |
| `--environment`              | The environment you wish to use                                                                                                                                                                                                                                                                                     | N             | `production` |
| `--certificate-name`         | Allows you to set a custom certificate name for this node in Puppet.                                                                                                                                                                                                                                                | N             | N/A          |
| `--csr-extensions`           | Any CSR extensions you wish to set, should be supplied in JSON format (e.g. `{"pp_service":"puppetserver","pp_role":"puppetserver","pp_environment":"live"})`                                                                                                                                                       | N             | N/A          |
| `--csr-retry-interval`       | How long Puppet waits (in seconds) before checking to see if the CSR has been signed on the Puppet server.  Setting this to `0` will stop Puppet from waiting at all and instead Puppet will exit as soon as the CSR has been performed. This may be desirable when you are configuring multiple nodes at once. | N             | `30`         |
| `--skip-initial-run`         | At the end of the bootstrap process a Puppet run is triggered, passing this parameter skips that run. This may be useful if you've not finished configuring your node/environment yet.                                                                                                                              | N             | N/A          |
| `--skip-puppet-server-check` | Pass this to parameter to skip the check that is performed that ensures the node being bootstrapped can contact the Puppet server.                                                                                                                                                                                  | N             | N/A          |
| `--skip-optional-prompts`    | Pass this parameter to skip all the optional prompts in the bootstrap script. This is useful if you know you've provided all the information you require via the command line.                                                                                                                                      | N             | N/A          |
| `--skip-confirmation`        | Caution: Use with care.  Passing this parameter allows you to bypass the confirmation that is displayed during the bootstrap process. This can be useful if you're confident you've passed in all the required information.                                                                                       | N             | N/A          |
| `--unattended`               | Instructs the script to run in `unattended mode` this bypasses all user prompts and will fail where user input would be required to correct an error.                                                                                                                                                               | N             | N/A          |

#### Example 1: Interactive mode

```bash
python3 bootstrap_puppet-linux.py
```

In this example the user has supplied no arguments therefore script will prompt the user for all required information, check the connection to the Puppet server and finally check the user is happy to proceed.

#### Example 2: Partially interactive mode

```bash
python3 bootstrap_puppet-linux.py --puppet-server puppetserver.example.com --version 7
```

In this example the user has supplied the Puppet server and the version of the Puppet agent to install. The script will prompt the user for the remaining required information, check the connection to the Puppet server and finally check the user is happy to proceed.

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
| `--new-hostname`             | Allows you to set a new hostname for the node.  <br>⚠ **NOTE**: Hostnames _must_ be fully qualified on Linux (e.g. `node.example.com`)                                                                                                                                                                              | N             | N/A          |
| `--puppet-server`            | The FQDN of the Puppet server that will manage this node (e.g. `puppetserver.example.com`)                                                                                                                                                                                                                          | Y             | N/A          |
| `--puppet-server-port`       | The port to use to communicate with the Puppet server                                                                                                                                                                                                                                                               | N             | `8140`       |
| `--environment`              | The environment you wish to use                                                                                                                                                                                                                                                                                     | N             | `production` |
| `--certificate-name`         | Allows you to set a custom certificate name for this node in Puppet.                                                                                                                                                                                                                                                | N             | N/A          |
| `--csr-extensions`           | Any CSR extensions you wish to set, should be supplied in JSON format (e.g. `{"pp_service":"puppetserver","pp_role":"puppetserver","pp_environment":"live"})`                                                                                                                                                       | N             | N/A          |
| `--csr-retry-interval`       | How long Puppet waits (in seconds) before checking to see if the CSR has been signed on the Puppet server.  <br>Setting this to `0` will stop Puppet from waiting at all and instead Puppet will exit as soon as the CSR has been performed. This may be desirable when you are configuring multiple nodes at once. | N             | `30`         |
| `--enable-service`           | Enables the Puppet Agent service at the end of the script.                                                                                                                                                                                                                                                          | N             | `true`       |
| `--skip-initial-run`         | At the end of the bootstrap process a Puppet run is triggered, passing this parameter skips that run. This may be useful if you've not finished configuring your node/environment yet.                                                                                                                              | N             | N/A          |
| `--skip-puppet-server-check` | Pass this to parameter to skip the check that is performed that ensures the node being bootstrapped can contact the Puppet server.                                                                                                                                                                                  | N             | N/A          |
| `--skip-optional-prompts`    | Pass this parameter to skip all the optional prompts in the bootstrap script. This is useful if you know you've provided all the information you require via the command line.                                                                                                                                      | N             | N/A          |
| `--skip-confirmation`        | Caution: Use with care.<br>Passing this parameter allows you to bypass the confirmation that is displayed during the bootstrap process. This can be useful if you're confident you've passed in all the required information.                                                                                       | N             | N/A          |
| `--unattended`               | Instructs the script to run in `unattended mode` this bypasses all user prompts and will fail where user input would be required to correct an error.                                                                                                                                                               | N             | N/A          |

### bootstrap_puppet-windows.ps1

| **Parameter**                      | **Description**                                                                                                                                                                                                                                                                                                     | **Mandatory** | **Default**  |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ------------ |
| `-AgentVersion`                    | The Version of Puppet Agent to be installed. This can be specified as a major version (e.g. `7`) or an exact version (e.g. `7.1.2`)                                                                                                                                                                                 | N             | `7`          |
| `-NewHostName`                     | Allows you to set a new hostname for the node.  <br>⚠ **NOTE**: Hostnames _must_ **NOT** be fully qualified on Windows (e.g. `node.example.com` should just be `node`)                                                                                                                                              | N             | N/A          |
| `-PuppetServer`                    | The FQDN of the Puppet server that will manage this node (e.g. `puppetserver.example.com`)                                                                                                                                                                                                                          | Y             | N/A          |
| `-PuppetServerPort`                | The port to use to communicate with the Puppet server                                                                                                                                                                                                                                                               | N             | `8140`       |
| `-Environment`                     | The environment you wish to use                                                                                                                                                                                                                                                                                     | N             | `production` |
| `-CertificateName`                 | Allows you to set a custom certificate name for this node in Puppet.                                                                                                                                                                                                                                                | N             | N/A          |
| `-CSRExtensions`                   | Any CSR extensions you wish to set, should be supplied in JSON format (e.g. `{"pp_service":"puppetserver","pp_role":"puppetserver","pp_environment":"live"})`                                                                                                                                                       | N             | N/A          |
| `-CSRRetryInterval`                | How long Puppet waits (in seconds) before checking to see if the CSR has been signed on the Puppet server.  <br>Setting this to `0` will stop Puppet from waiting at all and instead Puppet will exit as soon as the CSR has been performed. This may be desirable when you are configuring multiple nodes at once. | N             | `30`         |
| `-EnableService`                   | Enables the Puppet Agent service at the end of the bootstrap process.                                                                                                                                                                                                                                               | N             | `$true`      |
| `-PuppetServiceAccountCredentials` | Allows you to specify the credentials (in `PSCredential` format) for the Puppet Agent service to use. When using domain accounts you should **NOT** fully qualify them and instead use the `-PuppetServiceAccountDomain` parameter to set the domain name.                                                          | N             | N/A          |
| `-PuppetServiceAccountDomain`      | When using a domain account to run the Puppet Agent service use this parameter to specify the domain name.                                                                                                                                                                                                          | N             | N/A          |
| `-SkipInitialRun`                  | At the end of the bootstrap process a Puppet run is triggered, passing this parameter skips that run. This may be useful if you've not finished configuring your node/environment yet.                                                                                                                              | N             | N/A          |
| `-SkipPuppetServerCheck`           | Pass this to parameter to skip the check that is performed that ensures the node being bootstrapped can contact the Puppet server.                                                                                                                                                                                  | N             | N/A          |
| `-SkipOptionalPrompts`             | Pass this parameter to skip all the optional prompts in the bootstrap script. This is useful if you know you've provided all the information you require via the command line.                                                                                                                                      | N             | N/A          |
| `-SkipConfirmation`                | Caution: Use with care.<br>Passing this parameter allows you to bypass the confirmation that is displayed during the bootstrap process. This can be useful if you're confident you've passed in all the required information.                                                                                       | N             | N/A          |
| `-Unattended`                      | Instructs the script to run in `unattended mode` this bypasses all user prompts and will fail where user input would be required to correct an error.                                                                                                                                                               | N             | N/A          |

### bootstrap_puppet-server.py

TBD

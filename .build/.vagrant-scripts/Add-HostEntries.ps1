#!/usr/bin/env pwsh
<#
.SYNOPSIS
    This script adds host file entries for all the dev environment VMs.
.DESCRIPTION
    As the domain controller/DNS server is an optional VM in the dev environment, we can't rely on it
    being available to resolve hostnames. This script adds host entries to the local hosts file on the VM.
    This ensures that the VMs can resolve each other's hostnames and is needed for Puppet agent to be able
    to communicate with the Puppet server and negotiate a certificate.
.NOTES
    This script is designed to be run _inside_ the VMs in the dev environment.
    See the host_entries.jsonc file for the list of host entries that we manage.
#>

$HostsFile = "$env:windir\system32\drivers\etc\hosts"


# Import the list of host entries to add
try
{
    $HostsConfig = Get-Content -Path 'C:\vagrant\.vagrant-scripts\host_entries.jsonc' -Raw -ErrorAction Stop |
        ConvertFrom-Json
    if (!$HostsConfig)
    {
        throw 'Failed to import host entries from host_entries.jsonc'
    }
}
catch
{
    throw "Failed to import host entries from host_entries.jsonc.`n$($_.Exception.Message)"
}

# Get the current contents of the hosts file
try
{
    $CurrentHostsContent = Get-Content -Path $HostsFile -ErrorAction Stop
}
catch
{
    throw "Failed to get current contents of $HostsFile.`n$($_.Exception.Message)"
}

# Convert the current hosts file content to a series of objects
# (we're only matching IPv4 addresses for simplicity)
$CurrentHosts = $CurrentHostsContent | ForEach-Object {
    $Line = $_
    if ($Line -match '^(?<ip>\d+\.\d+\.\d+\.\d+)\s+(?<hostname>.+)$')
    {
        [PSCustomObject]@{
            ip       = $Matches['ip']
            hostname = $Matches['hostname']
        }
    }
}

try
{
    Write-Host "Adding host entries to $HostsFile"
    $HostsConfig | ForEach-Object {
        $Hostname = $_.hostname
        $IpAddress = $_.ip
        if (!$Hostname -or !$IpAddress)
        {
            throw "Invalid host entry: $_"
        }
        $HostsEntry = "$IpAddress $Hostname"

        # Check if the host entry already exists
        if ($CurrentHosts.hostname -contains $_.hostname)
        {
            Write-Host "Host entry already exists: $HostsEntry"
            return
        }
        else
        {
            Write-Host "Adding host entry: $HostsEntry"
            Add-Content -Path $HostsFile -Value $HostsEntry -ErrorAction Stop
        }
    }
}
catch
{
    throw "Failed to add host entries to $HostsFile.`n$($_.Exception.Message)"
}

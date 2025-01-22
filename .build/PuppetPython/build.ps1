<#
.SYNOPSIS
    Build the PuppetPython module.
#>
[CmdletBinding()]

$ErrorActionPreference = 'Stop'

$RepoRoot = Join-Path $PSScriptRoot '..\..'
$CommonFile = Join-Path $PSScriptRoot 'Common.py'
$ServerBootstrapScript = Join-Path $PSScriptRoot 'puppet_server.py'
$AgentBootstrapScript = Join-Path $PSScriptRoot 'puppet_agent.py'
$ExportedAgentScript = Join-Path $RepoRoot 'bootstrap_puppet-linux.py'
$ExportedServerScript = Join-Path $RepoRoot 'bootstrap_puppet-server.py'
$CommonSectionStart = '### !!! Start Common Functions !!!'
$CommonSectionEnd = '### !!! End Common Functions !!!'
$CommonInsertString = '### !!! Common Functions !!! ###'

# Ensure we can load each of the files.
try
{
    $ServerBootstrapScriptContent = Get-Content -Path $ServerBootstrapScript -Raw -ErrorAction Stop
    $AgentBootstrapScriptContent = Get-Content -Path $AgentBootstrapScript -Raw -ErrorAction Stop
    $CommonFileContent = Get-Content -Path $CommonFile -ErrorAction Stop
}
catch
{
    throw "Failed to load one of the required files.`n$($_.Exception.Message)"
}

# Grab everything in-between the common section markers.
$CommonSectionStartIndex = ($CommonFileContent.IndexOf($CommonSectionStart) + 1)
$CommonSectionEndIndex = ($CommonFileContent.IndexOf($CommonSectionEnd) - 1)
$CommonSection = $CommonFileContent[$CommonSectionStartIndex..$CommonSectionEndIndex] | Out-String

Write-Debug "Common Section: $CommonSection"

# Insert the common section into the server and agent scripts.
$ServerBootstrapScriptContent = $ServerBootstrapScriptContent -replace $CommonInsertString, $CommonSection
$AgentBootstrapScriptContent = $AgentBootstrapScriptContent -replace $CommonInsertString, $CommonSection

# Ensure line endings are set LF.
$ServerBootstrapScriptContent = $ServerBootstrapScriptContent -replace "`r`n", "`n"
$AgentBootstrapScriptContent = $AgentBootstrapScriptContent -replace "`r`n", "`n"

# Write the updated content back to the files.
try
{
    $ServerBootstrapScriptContent | Set-Content -Path $ExportedServerScript -Force
    $AgentBootstrapScriptContent | Set-Content -Path $ExportedAgentScript -Force
}
catch
{
    throw "Failed to write the updated content back to the files.`n$($_.Exception.Message)"
}

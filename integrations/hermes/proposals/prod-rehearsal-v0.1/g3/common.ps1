# G3 shared constants. Dot-sourced. Defines no actions.
$ErrorActionPreference = 'Stop'
$G       = if ($env:G3_GCLOUD) { $env:G3_GCLOUD } else { 'C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' }
$Project = 'lilith-agent-260823-27389'
$Zone    = 'asia-southeast1-b'
$Here    = $PSScriptRoot
$Snapshot = 'lilith-01-rehearsal-20261101'; $SnapshotId = '9145142762520941677'
$Vm = 'lilith-rehearsal-01'; $Copy = 'lilith-rehearsal-copy'
$Deployer = 'serviceAccount:github-lilith-deployer@lilith-agent-260823-27389.iam.gserviceaccount.com'
$Roles = @('roles/iap.tunnelResourceAccessor', 'roles/compute.osAdminLogin')

function Invoke-G([string[]]$GArgs, [string]$OutFile) {
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $out = & $G @GArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $saved
    $text = ($out | Out-String)
    if ($OutFile) { $text | Out-File -Encoding utf8 $OutFile }
    return @{ Code = $code; Text = $text }
}

function Get-DeployerBindings {
    $r = Invoke-G @('projects', 'get-iam-policy', $Project, '--format=json')
    if ($r.Code -ne 0) { throw "policy rc $($r.Code)" }
    $found = @()
    foreach ($b in (($r.Text | ConvertFrom-Json).bindings)) {
        if ($b.members -contains $Deployer) { $found += [pscustomobject]@{ role = $b.role; condition = [bool]$b.condition } }
    }
    return $found
}

function Invoke-Guest([string]$File, [string]$Argument, [string]$OutFile) {
    $script = (Get-Content (Join-Path $Here $File) -Raw) -replace "`r`n", "`n"
    if ($Argument) { $tail = "sudo -n bash /var/tmp/g3/$File $Argument" } else { $tail = $null }
    if ($tail) { return Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=$tail") $OutFile }
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($script))
    return Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=echo $b64 | base64 -d | sudo -n bash") $OutFile
}

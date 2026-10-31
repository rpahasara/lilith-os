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

function Test-NoRealCopy {
    # True only on a successful read showing no disk built from a snapshot and no disk of the copy's name. A failed read is not a clear result.
    $r = Invoke-G @('compute', 'disks', 'list', "--project=$Project", '--format=json')
    if ($r.Code -ne 0) { return $false }
    return (@(@($r.Text | ConvertFrom-Json) | Where-Object { $_.sourceSnapshot -or $_.name -eq $Copy }).Count -eq 0)
}

function Restore-Deployer {
    # Only the two approved bindings, by add, so it can't disturb anything else in the policy. Refused while real data may exist.
    if (-not (Test-NoRealCopy)) { return 'REFUSED a real-data copy exists or could not be ruled out' }
    foreach ($role in $Roles) {
        $r = Invoke-G @('projects', 'add-iam-policy-binding', $Project, "--member=$Deployer", "--role=$role", '--condition=None', '--format=none')
        if ($r.Code -ne 0) { return "FAILED $role rc $($r.Code)" }
    }
    $back = @(Get-DeployerBindings | Where-Object { $Roles -contains $_.role -and -not $_.condition })
    if ($back.Count -ne $Roles.Count) { return 'FAILED bindings not confirmed' }
    return 'RESTORED'
}

function Invoke-Guest([string]$File, [string]$Argument, [string]$OutFile) {
    $script = (Get-Content (Join-Path $Here $File) -Raw) -replace "`r`n", "`n"
    if ($Argument) { $tail = "sudo -n bash /var/tmp/g3/$File $Argument" } else { $tail = $null }
    if ($tail) { return Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=$tail") $OutFile }
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($script))
    return Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=echo $b64 | base64 -d | sudo -n bash") $OutFile
}

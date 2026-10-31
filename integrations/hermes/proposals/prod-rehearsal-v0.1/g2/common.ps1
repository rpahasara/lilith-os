# G2 shared constants. Dot-sourced. Defines no actions. No resource here ever uses the rehearsal snapshot: that is G3.
$ErrorActionPreference = 'Stop'
$G       = if ($env:G2_GCLOUD) { $env:G2_GCLOUD } else { 'C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' }
$Project = 'lilith-agent-260823-27389'
$Zone    = 'asia-southeast1-b'
$Region  = 'asia-southeast1'
$Account = 'ravindupahasara2@gmail.com'
$Here    = $PSScriptRoot
$G1Dir   = if ($env:G2_G1DIR) { $env:G2_G1DIR } else { 'C:\Users\edufo\lilith-g1-snapshot-20261101' }
$Snapshot = 'lilith-01-rehearsal-20261101'; $DeleteAfter = '20261201'
$Net = 'lilith-rehearsal'; $Subnet = 'lilith-rehearsal-sn'; $Cidr = '10.99.0.0/24'
$RuleDeny = 'rehearsal-deny-all-egress'; $RuleIap = 'rehearsal-allow-iap-ssh'; $Tag = 'lilith-rehearsal'
$Vm = 'lilith-rehearsal-01'; $Synth = 'lilith-rehearsal-synthetic'
$ImageFamily = 'ubuntu-2404-lts-amd64'; $ImageProject = 'ubuntu-os-cloud'
$IapRange = '35.235.240.0/20'

function Invoke-G([string[]]$GArgs, [string]$OutFile) {
    $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    $out = & $G @GArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $saved
    $text = ($out | Out-String)
    if ($OutFile) { $text | Out-File -Encoding utf8 $OutFile }
    return @{ Code = $code; Text = $text }
}

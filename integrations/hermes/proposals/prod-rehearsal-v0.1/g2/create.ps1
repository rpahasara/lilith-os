# G2 creation. MUTATING: creates the isolated network, one VM and one blank synthetic disk, in that order, the egress block before the VM. Only after owner approval and a fresh PASS.
# Usage: .\create.ps1 -PreflightSha <sha256>. Never reads or attaches the snapshot. No retries, no deletions: a failure stops and records.
param([Parameter(Mandatory = $true)][string]$PreflightSha)
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'execution'
New-Item -ItemType Directory -Force $Dir | Out-Null
$log = [ordered]@{ go = 'G2-20261101'; startedUtc = (Get-Date).ToUniversalTime().ToString('o'); steps = @() }
function Stop-Go([string]$why) {
    $log.result = 'STOPPED'; $log.reason = $why; $log.finishedUtc = (Get-Date).ToUniversalTime().ToString('o')
    [IO.File]::WriteAllText("$Dir\EXECUTION-RESULT.json", ($log | ConvertTo-Json -Depth 6) + "`n")
    Write-Output "STOPPED: $why"; exit 2
}
if (Test-Path "$Dir\started") { Stop-Go 'already started' }
$pf = Join-Path $Here 'preflight\PREFLIGHT-RESULT.json'
if (-not (Test-Path $pf)) { Stop-Go 'no preflight result' }
if ((Get-FileHash $pf -Algorithm SHA256).Hash.ToLower() -ne $PreflightSha.ToLower()) { Stop-Go 'preflight sha mismatch' }
$p = Get-Content $pf -Raw | ConvertFrom-Json
if ($p.verdict -ne 'PASS') { Stop-Go "preflight verdict $($p.verdict)" }
$done = if ($p.finishedUtc -is [datetime]) { $p.finishedUtc.ToUniversalTime() } else { [datetimeoffset]::Parse([string]$p.finishedUtc).UtcDateTime }
$age = ((Get-Date).ToUniversalTime() - $done).TotalMinutes
if ($age -lt 0 -or $age -gt 60) { Stop-Go 'preflight age outside 0..60 min' }
New-Item -ItemType File "$Dir\started" | Out-Null
$labels = 'app=lilith,purpose=rehearsal,go=g2-20261101'
$steps = @(
    @('network', @('compute', 'networks', 'create', $Net, '--subnet-mode=custom', "--project=$Project")),
    @('subnet', @('compute', 'networks', 'subnets', 'create', $Subnet, "--network=$Net", "--range=$Cidr", "--region=$Region", '--no-enable-private-ip-google-access', "--project=$Project")),
    @('deny-egress', @('compute', 'firewall-rules', 'create', $RuleDeny, "--network=$Net", '--direction=EGRESS', '--action=DENY', '--rules=all', '--destination-ranges=0.0.0.0/0', '--priority=100', "--project=$Project")),
    @('allow-iap', @('compute', 'firewall-rules', 'create', $RuleIap, "--network=$Net", '--direction=INGRESS', '--action=ALLOW', '--rules=tcp:22', "--source-ranges=$IapRange", "--target-tags=$Tag", "--project=$Project")),
    @('synthetic-disk', @('compute', 'disks', 'create', $Synth, '--size=10GB', '--type=pd-balanced', "--zone=$Zone", "--labels=$labels", "--project=$Project")),
    @('vm', @('compute', 'instances', 'create', $Vm, "--zone=$Zone", '--machine-type=e2-medium', "--subnet=$Subnet", '--no-address', '--no-service-account', '--no-scopes', "--tags=$Tag", "--image=$($p.facts.image)", "--image-project=$ImageProject",
              '--boot-disk-size=60GB', '--boot-disk-type=pd-balanced', "--disk=name=$Synth,device-name=synthetic,mode=rw,auto-delete=no", "--labels=$labels", "--project=$Project"))
)
foreach ($s in $steps) {
    ('gcloud ' + ($s[1] -join ' ')) | Out-File -Encoding utf8 "$Dir\$($s[0])-command.txt"
    $r = Invoke-G $s[1] "$Dir\$($s[0]).txt"
    $log.steps += @{ name = $s[0]; rc = $r.Code }
    if ($r.Code -ne 0) { Stop-Go "$($s[0]) rc $($r.Code)" }
}
$log.result = 'COMPLETED'; $log.finishedUtc = (Get-Date).ToUniversalTime().ToString('o')
[IO.File]::WriteAllText("$Dir\EXECUTION-RESULT.json", ($log | ConvertTo-Json -Depth 6) + "`n")
Write-Output 'COMPLETED'; exit 0

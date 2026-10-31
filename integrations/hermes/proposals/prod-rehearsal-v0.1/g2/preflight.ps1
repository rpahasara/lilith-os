# G2 preflight: READ-ONLY. Creates nothing. Verifies the G1 snapshot and records its exact id. Verdict PASS or FAIL.
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'preflight'
New-Item -ItemType Directory -Force $Dir | Out-Null
$fail = @(); $facts = [ordered]@{ startedUtc = (Get-Date).ToUniversalTime().ToString('o') }

if ((Invoke-G @('config', 'get-value', 'account')).Text.Trim() -ne $Account) { $fail += 'P1 account' }
if ((Invoke-G @('config', 'get-value', 'project')).Text.Trim() -ne $Project) { $fail += 'P1 project' }

# P2 G1 finished, and the snapshot is what it recorded
$v = Join-Path $G1Dir 'verify\VERIFY-RESULT.json'
if (-not (Test-Path $v)) { $fail += 'P2 G1 has not completed' } else {
    $g1 = Get-Content $v -Raw | ConvertFrom-Json
    if ($g1.verdict -ne 'PASS') { $fail += "P2 G1 verdict $($g1.verdict)" }
    $r = Invoke-G @('compute', 'snapshots', 'describe', $Snapshot, "--project=$Project", '--format=json') "$Dir\P2-snapshot.json"
    if ($r.Code -ne 0) { $fail += "P2 describe rc $($r.Code)" } else {
        $s = $r.Text | ConvertFrom-Json
        $facts.snapshotId = [string]$s.id; $facts.snapshotStatus = $s.status; $facts.snapshotCreated = $s.creationTimestamp; $facts.deleteAfter = $s.labels.'delete-after'
        if ($s.status -ne 'READY') { $fail += "P2 status $($s.status)" }
        if ([string]$s.id -ne [string]$g1.facts.new.id) { $fail += 'P2 id differs from G1' }
        if ($s.labels.'delete-after' -ne $DeleteAfter) { $fail += 'P2 retention label' }
    }
}

# P3 nothing of G2 exists yet
foreach ($c in @(@('networks', $Net), @('networks subnets', $Subnet), @('firewall-rules', $RuleDeny), @('firewall-rules', $RuleIap), @('instances', $Vm), @('disks', $Synth))) {
    $r = Invoke-G (@('compute') + ($c[0] -split ' ') + @('list', "--project=$Project", '--format=value(name)'))
    if ($r.Code -ne 0) { $fail += "P3 $($c[0]) rc $($r.Code)"; continue }
    if (@($r.Text -split "`r?`n") -contains $c[1]) { $fail += "P3 exists $($c[1])" }
}

# P4 the image is stock, and pinned for this run
$r = Invoke-G @('compute', 'images', 'describe-from-family', $ImageFamily, "--project=$ImageProject", '--format=json') "$Dir\P4-image.json"
if ($r.Code -ne 0) { $fail += "P4 rc $($r.Code)" } else { $facts.image = ($r.Text | ConvertFrom-Json).name }

$verdict = if ($fail.Count) { 'FAIL' } else { 'PASS' }
$result = [ordered]@{ go = 'G2-20261101'; verdict = $verdict; failures = $fail; facts = $facts; finishedUtc = (Get-Date).ToUniversalTime().ToString('o') }
[IO.File]::WriteAllText("$Dir\PREFLIGHT-RESULT.json", ($result | ConvertTo-Json -Depth 6) + "`n")
$sha = (Get-FileHash "$Dir\PREFLIGHT-RESULT.json" -Algorithm SHA256).Hash.ToLower()
Write-Output "PREFLIGHT verdict=$verdict sha256=$sha"

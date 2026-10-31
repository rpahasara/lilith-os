# G2 verification. Control-plane reads, then the isolation probe inside the rehearsal VM only. Changes no cloud resource. VERIFY PASS or FAIL.
. "$PSScriptRoot\common.ps1"
$Dir = Join-Path $Here 'verify'
New-Item -ItemType Directory -Force $Dir | Out-Null
$fail = @(); $facts = [ordered]@{}
$r = Invoke-G @('compute', 'instances', 'describe', $Vm, "--zone=$Zone", "--project=$Project", '--format=json') "$Dir\vm.json"
if ($r.Code -ne 0) { $fail += "vm rc $($r.Code)" } else {
    $i = $r.Text | ConvertFrom-Json
    $nic = @($i.networkInterfaces)
    if ($nic.Count -ne 1 -or (($nic[0].network -split '/')[-1]) -ne $Net) { $fail += 'vm network' }
    if ($nic[0].accessConfigs -or $nic[0].ipv6AccessConfigs) { $fail += 'vm external address' }
    if (@($i.serviceAccounts | Where-Object { $_ }).Count) { $fail += 'vm service account' }
    if (@($i.disks).Count -ne 2) { $fail += "vm disks $(@($i.disks).Count)" }
    if (@($i.metadata.items | Where-Object { $_ -and $_.key -match 'startup|shutdown' }).Count) { $fail += 'vm startup script' }
}
$r = Invoke-G @('compute', 'firewall-rules', 'list', "--project=$Project", '--format=json') "$Dir\firewall.json"
if ($r.Code -ne 0) { $fail += "firewall rc $($r.Code)" } else {
    $mine = @(@($r.Text | ConvertFrom-Json) | Where-Object { (($_.network -split '/')[-1]) -eq $Net })
    if ((@($mine.name | Sort-Object) -join ',') -ne (@($RuleIap, $RuleDeny | Sort-Object) -join ',')) { $fail += "firewall set $($mine.name -join ',')" }
}
$r = Invoke-G @('compute', 'routers', 'list', "--project=$Project", '--format=json') "$Dir\routers.json"
if ($r.Code -ne 0) { $fail += "routers rc $($r.Code)" } elseif (@(@($r.Text | ConvertFrom-Json) | Where-Object { (($_.network -split '/')[-1]) -eq $Net }).Count) { $fail += 'router on the rehearsal network' }
$r = Invoke-G @('compute', 'networks', 'peerings', 'list', "--network=$Net", "--project=$Project", '--format=json') "$Dir\peerings.json"
if ($r.Code -ne 0) { $fail += "peerings rc $($r.Code)" } elseif (@(@($r.Text | ConvertFrom-Json) | Where-Object { @($_.peerings | Where-Object { $_ }).Count }).Count) { $fail += 'peering present' }
foreach ($kind in 'disks', 'images') {
    $r = Invoke-G @('compute', $kind, 'list', "--project=$Project", '--format=json') "$Dir\$kind.json"
    if ($r.Code -ne 0) { $fail += "$kind rc $($r.Code)"; continue }
    if (@(@($r.Text | ConvertFrom-Json) | Where-Object { $_.sourceSnapshot -and ($_.sourceSnapshot -match [regex]::Escape($Snapshot)) }).Count) { $fail += "$kind built from the snapshot" }
}
$r = Invoke-G @('compute', 'snapshots', 'describe', $Snapshot, "--project=$Project", '--format=json') "$Dir\snapshot.json"
if ($r.Code -ne 0) { $fail += "snapshot rc $($r.Code)" } else { $s = $r.Text | ConvertFrom-Json; $facts.snapshotId = [string]$s.id; $facts.snapshotStatus = $s.status; if ($s.status -ne 'READY') { $fail += 'snapshot not READY' } }
if (-not $fail.Count) {
    $script = (Get-Content (Join-Path $Here 'isolation_probe.sh') -Raw) -replace "`r`n", "`n"
    $path = Join-Path $Dir 'probe.out'
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($script))
    $r = Invoke-G @('compute', 'ssh', $Vm, "--zone=$Zone", "--project=$Project", '--tunnel-through-iap', '--quiet', "--command=echo $b64 | base64 -d | bash") $path
    if ($r.Text -notmatch '(?m)^ISOLATION_PROBE PASS') { $fail += 'isolation probe' }
}
$res = [ordered]@{ go = 'G2-20261101'; verdict = $(if ($fail.Count) { 'FAIL' } else { 'PASS' }); failures = $fail; facts = $facts; finishedUtc = (Get-Date).ToUniversalTime().ToString('o') }
[IO.File]::WriteAllText("$Dir\VERIFY-RESULT.json", ($res | ConvertTo-Json -Depth 6) + "`n")
Write-Output "VERIFY $($res.verdict)"

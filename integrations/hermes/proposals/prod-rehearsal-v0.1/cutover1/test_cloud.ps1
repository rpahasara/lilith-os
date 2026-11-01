# Offline test of prepare.ps1, undo_prepare.ps1, restore_disk.ps1 and cc_env.ps1 against fake_gcloud.py. TEST_ONLY.
$ErrorActionPreference = 'Stop'
$src = Split-Path $PSScriptRoot -Parent
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("c1-" + [guid]::NewGuid().ToString('n'))
New-Item -ItemType Directory $tmp | Out-Null
foreach ($f in 'common.ps1', 'prepare.ps1', 'undo_prepare.ps1', 'restore_disk.ps1', 'cc_env.ps1', 'restage.ps1', 'guest_c1.sh', 'stage_c1.sh', 'live_compare.py', 'rehearsal_compare.py') { Copy-Item "$src\$f" $tmp }
"@python -B `"$PSScriptRoot\fake_gcloud.py`" %*" | Set-Content -Encoding ascii "$tmp\fake.cmd"
"@python -B `"$PSScriptRoot\fake_gcloud.py`" %*" | Set-Content -Encoding ascii "$tmp\fakeiap.cmd"
'x' | Set-Content "$tmp\MANIFEST.txt"
$digest = (Get-FileHash "$tmp\MANIFEST.txt" -Algorithm SHA256).Hash.ToLower()
$env:C1_GCLOUD = "$tmp\fake.cmd"; $env:C1_IAP = "$PSScriptRoot\iap_stub.ps1"; $env:C_STATE = "$tmp\calls.log"
$pass = 0; $bad = 0
function Check([string]$n, $got, $want) { if ("$got" -eq "$want") { $script:pass++; "  PASS $n" } else { $script:bad++; "  FAIL $n got '$got' want '$want'" } }
function Reset { Remove-Item -Recurse -Force "$tmp\prepare", "$tmp\calls.log", "$tmp\calls.tunnel", "$tmp\RETURN-WINDOW.txt", "$tmp\.env.local" -ErrorAction SilentlyContinue; $env:C_FAKE = ''; Set-Content "$tmp\APPROVED_PREPARE" $digest }
function Run([string]$s, [string[]]$A) { & pwsh -NoProfile -File "$tmp\$s" @A 2>&1 | Out-String }
function Log { if (Test-Path $env:C_STATE) { Get-Content $env:C_STATE -Raw } else { '' } }
$MUTATE = 'firewall-rules update|add-iam-policy-binding|setIamPolicy|resource-policies create|add-resource-policies|compute scp'
"== prepare"
Reset; $o = Run 'prepare.ps1' @('-Confirm', 'yes'); Check 'needs the phrase' ($o -match 'REFUSED confirmation') 'True'
Reset; Remove-Item "$tmp\APPROVED_PREPARE"; $o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check 'needs approval' ($o -match 'REFUSED not approved') 'True'
Reset; Set-Content "$tmp\APPROVED_PREPARE" 'other'; $o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check 'approval must match' ($o -match 'REFUSED not approved') 'True'
foreach ($c in @(@('fw_tagged', 'firewall rule is not as recorded'), @('extra_vm', 'instances are not as recorded'), @('deployer_wide', 'deployer is not as recorded'), @('has_schedule', 'already has a schedule'))) {
    Reset; $env:C_FAKE = $c[0]; $o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check "$($c[0]) stops" ($o -match $c[1]) 'True'; Check "$($c[0]) changes nothing" ((Log) -match $MUTATE) 'False'
}
foreach ($c in @(@('fw_update_fails', 'firewall update'), @('login_fails', 'login grant'), @('tunnel_fails', 'tunnel binding not confirmed'), @('schedule_fails', 'schedule create'), @('attach_fails', 'schedule attach'), @('scp_fails', 'upload'), @('stage_fails', 'guest files not confirmed'))) {
    Reset; $env:C_FAKE = $c[0]; $o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check "$($c[0]) stops" ($o -match $c[1]) 'True'
}
Reset; $o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check 'prepare passes' ($o -match 'PREPARE PASS') 'True'
$l = Log
Check 'firewall gets the tag' ($l -match 'firewall-rules update lilith-api-iap --target-tags=lilith-vm') 'True'
Check 'login is instance-level' ($l -match 'instances add-iam-policy-binding lilith-01') 'True'
Check 'no project-level grant' ($l -match 'projects add-iam-policy-binding') 'False'
Check 'tunnel holds port 22 only' ((Get-Content "$tmp\calls.tunnel" -Raw) -match 'destination.port == 22') 'True'
Check 'schedule is 30 days, multi-region, survives disk deletion' ($l -match 'max-retention-days=30 --on-source-disk-delete=keep-auto-snapshots --daily-schedule --start-time=18:00 --storage-location=asia') 'True'
Check 'schedule on lilith-01 only' (@(($l -split "`n") | Where-Object { $_ -match 'add-resource-policies' -and $_ -notmatch 'disks add-resource-policies lilith-01 ' }).Count) 0
Check 'uploads by relative path' (($l -match 'scp .*C:\\') -eq $false -and ($l -match 'guest_c1.sh lilith-01:/tmp/c1-guest_c1.sh')) 'True'
Check 'staging passes digests with no quoting' ($l -match '--command=sudo -n bash /tmp/c1-stage_c1.sh [0-9a-f]{64} [0-9a-f]{64} [0-9a-f]{64}') 'True'
Check 'no snapshot touched' ($l -match 'snapshots (delete|update)') 'False'
Check 'no DEV change' ($l -match 'lilith-dev-01 ') 'False'
$o = Run 'prepare.ps1' @('-Confirm', 'PREPARE-CUTOVER1'); Check 'a second run refuses' ($o -match 'already started') 'True'
"== undo"
$o = Run 'undo_prepare.ps1' @('-Confirm', 'yes'); Check 'undo needs the phrase' ($o -match 'REFUSED') 'True'
$o = Run 'undo_prepare.ps1' @('-Confirm', 'UNDO-PREPARE'); Check 'undo passes' ($o -match 'UNDO PASS') 'True'
$l = Log
Check 'tunnel emptied' ((Get-Content "$tmp\calls.tunnel" -Raw).Trim() -in @('[]', 'null', '')) 'True'
Check 'firewall target cleared' ($l -match 'firewall-rules update lilith-api-iap --target-tags= ') 'True'
Check 'login removed' ($l -match 'remove-iam-policy-binding lilith-01') 'True'
Check 'schedule removed, no snapshot deleted' (($l -match 'resource-policies delete') -and ($l -notmatch 'snapshots delete')) 'True'
"== restore"
$fut = [datetime]::UtcNow.AddHours(47).ToString('yyyy-MM-ddTHH:mm:ssZ'); $past = [datetime]::UtcNow.AddHours(-1).ToString('yyyy-MM-ddTHH:mm:ssZ')
$A = @('-Confirm', 'RESTORE-LILITH-01', '-Snapshot', 's1')
Reset; $o = Run 'restore_disk.ps1' @('-Confirm', 'yes', '-Snapshot', 's1'); Check 'needs the phrase' ($o -match 'REFUSED confirmation') 'True'
Reset; $o = Run 'restore_disk.ps1' $A; Check 'no window, no restore' ($o -match 'outside the return window') 'True'
Reset; $past | Set-Content "$tmp\RETURN-WINDOW.txt"; $o = Run 'restore_disk.ps1' $A; Check 'after 48 hours, refused' ($o -match 'outside the return window') 'True'
Reset; $fut | Set-Content "$tmp\RETURN-WINDOW.txt"; $env:C_FAKE = 'snap_not_ready'; $o = Run 'restore_disk.ps1' $A; Check 'needs READY' ($o -match 'not a READY') 'True'; Check 'nothing stopped' ((Log) -match 'instances stop') 'False'
Reset; $fut | Set-Content "$tmp\RETURN-WINDOW.txt"; $env:C_FAKE = 'snap_other_disk'; $o = Run 'restore_disk.ps1' $A; Check 'refuses another disk''s snapshot' ($o -match 'not a READY') 'True'
Reset; $fut | Set-Content "$tmp\RETURN-WINDOW.txt"; $env:C_FAKE = 'stop_fails'; $o = Run 'restore_disk.ps1' $A; Check 'stop failure stops' ($o -match 'RESTORE STOPPED at stop') 'True'; Check 'old disk not detached' ((Log) -match 'detach-disk') 'False'
Reset; $fut | Set-Content "$tmp\RETURN-WINDOW.txt"; $env:C_FAKE = 'attach_boot_fails'; $o = Run 'restore_disk.ps1' $A; Check 'attach failure names both disks' ($o -match 'Old disk lilith-01 is kept') 'True'
Reset; $fut | Set-Content "$tmp\RETURN-WINDOW.txt"; $o = Run 'restore_disk.ps1' $A; Check 'restore boots' ($o -match 'RESTORE BOOTED') 'True'
$l = Log
Check 'new disk made before the VM stops' ($l.IndexOf('disks create') -lt $l.IndexOf('instances stop')) 'True'
Check 'old disk never deleted' ($l -match 'disks delete') 'False'
Check 'schedule follows the new disk' ($l -match 'disks add-resource-policies lilith-01-restored') 'True'
"== restage"
Reset; Remove-Item -Recurse -Force "$tmp\raw-attempt1" -ErrorAction SilentlyContinue; New-Item -ItemType Directory "$tmp\raw" | Out-Null
$o = Run 'restage.ps1' @('-Confirm', 'yes'); Check 'needs the phrase' ($o -match 'REFUSED confirmation') 'True'
Set-Content "$tmp\APPROVED_PREPARE" 'old'; $o = Run 'restage.ps1' @('-Confirm', 'RESTAGE-CUTOVER1'); Check 'old approval refused' ($o -match 'REFUSED not approved') 'True'; Set-Content "$tmp\APPROVED_PREPARE" $digest
$env:C_FAKE = 'stage_fails'; $o = Run 'restage.ps1' @('-Confirm', 'RESTAGE-CUTOVER1'); Check 'unconfirmed files stop' ($o -match 'not confirmed') 'True'; Check 'spent attempt kept' (Test-Path "$tmp\raw") 'True'
$env:C_FAKE = ''; $o = Run 'restage.ps1' @('-Confirm', 'RESTAGE-CUTOVER1'); Check 'restage passes' ($o -match 'RESTAGE PASS') 'True'; Check 'attempt archived' (Test-Path "$tmp\raw-attempt1") 'True'
$o = Run 'restage.ps1' @('-Confirm', 'RESTAGE-CUTOVER1'); Check 'runs once' ($o -match 'already ran') 'True'
Check 'changes no IAM, firewall or schedule' ((Log) -match 'iam-policy-binding|firewall-rules update|resource-policies') 'False'
"== Command Center"
$E = @('-EnvFile', "$tmp\.env.local")
Reset; Set-Content "$tmp\.env.local" 'NEXT_PUBLIC_LILITH_API_URL=http://x'; $o = Run 'cc_env.ps1' $E; Check 'refuses direct mode' ($o -match 'REFUSED direct mode') 'True'
Reset; Set-Content "$tmp\.env.local" 'OTHER=1'; $o = Run 'cc_env.ps1' $E; Check 'needs the proxy URL' ($o -match 'REFUSED LILITH_API_URL') 'True'
Reset; Set-Content "$tmp\.env.local" 'LILITH_API_URL=http://localhost:8765'; $env:C_FAKE = 'no_tokens'; $o = Run 'cc_env.ps1' $E; Check 'no tokens, no write' ($o -match 'STOPPED') 'True'; Check 'file untouched' ((Get-Content "$tmp\.env.local" -Raw) -match 'TOKEN') 'False'
Reset; "LILITH_API_URL=http://localhost:8765`nOTHER=1`nLILITH_OS_READ_TOKEN=old" | Set-Content "$tmp\.env.local"; $o = Run 'cc_env.ps1' $E; Check 'writes' ($o -match 'CC PASS') 'True'
$t = Get-Content "$tmp\.env.local" -Raw
Check 'token never printed' ($o -match 'a{64}|b{64}') 'False'
Check 'both tokens set once' ((([regex]::Matches($t, '(?m)^LILITH_OS_READ_TOKEN=a{64}$').Count) + ([regex]::Matches($t, '(?m)^LILITH_OS_WRITE_TOKEN=b{64}$').Count))) 2
Check 'old token gone' ($t -match 'TOKEN=old') 'False'
Check 'other lines kept' ($t -match 'OTHER=1' -and $t -match 'LILITH_API_URL=') 'True'
"== static"
foreach ($w in 'snapshots delete', 'disks delete', 'projects add-iam-policy-binding', 'lilith-dev-01"') { foreach ($f in 'prepare.ps1', 'undo_prepare.ps1', 'restore_disk.ps1', 'cc_env.ps1', 'restage.ps1') { if (Select-String -Path "$src\$f" -SimpleMatch $w -Quiet) { Check "$f has no '$w'" $false $true } } }
Remove-Item -Recurse -Force $tmp
"CLOUD_TESTS pass=$pass fail=$bad"
if ($bad) { exit 1 }

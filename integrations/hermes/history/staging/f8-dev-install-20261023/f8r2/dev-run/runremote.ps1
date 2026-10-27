param([Parameter(Mandatory)][string]$Script, [Parameter(Mandatory)][string]$Out)
# Runs one local bash script as root on lilith-dev-01 ONLY (IAP SSH), embedded gzip+base64 in --command (never stdin).
$ErrorActionPreference = "Stop"
$bash = "C:\Program Files\Git\usr\bin\bash.exe"
$unix = ($Script -replace '\\','/') -replace '^([A-Za-z]):', '/$1'
$b64 = (& $bash -lc "sed 's/\r$//' '$unix' | gzip -9 | base64 -w0").Trim()
if ($b64.Length -gt 7000) { throw "script too large for --command ($($b64.Length))" }
$g = "C:\Users\edufo\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
& $g compute ssh lilith-dev-01 --zone=asia-southeast1-b --project=lilith-agent-260823-27389 --tunnel-through-iap --quiet `
  --command "echo $b64 | base64 -d | gunzip | sudo -n bash" 2>&1 | Out-File -Encoding utf8 $Out
"rc=$LASTEXITCODE"
Get-Content $Out

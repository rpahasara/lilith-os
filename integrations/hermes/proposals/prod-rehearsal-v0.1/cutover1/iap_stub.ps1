# TEST_ONLY stand-in for the IAP policy endpoint: passes the JSON through a file, because cmd quoting would strip it.
param([string]$Method, [string]$Body)
$f = "$env:C_STATE.body"
[IO.File]::WriteAllText($f, $Body)
& python -B -c "import subprocess,sys,os; print(subprocess.run([sys.executable,'-B',r'$PSScriptRoot\fake_gcloud.py','$Method',open(r'$f').read()],capture_output=True,text=True).stdout)"

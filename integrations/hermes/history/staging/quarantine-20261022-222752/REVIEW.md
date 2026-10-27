# Quarantine review, stage 1

Integrity: VERIFIED (12 files match the PROD manifest; upstream run.py + diff == PROD run.py).

Nothing here has been executed or imported. Owner sign-off is required for every finding before any file leaves quarantine.

All finding values are redacted; open the read-only file under `extracted/` at the listed line.

| file | line | finding | redacted value |
|---|---|---|---|
| plugins/lilith_os/adapter.py | 125 | CONFIDENTIAL:ipv4 | [redacted 9 chars] |
| plugins/lilith_os/adapter.py | 180 | CONFIDENTIAL:ipv4 | [redacted 9 chars] |
| plugins/lilith_os/adapter.py | 195 | CONFIDENTIAL:ipv4 | [redacted 9 chars] |
| plugins/lilith_os/plugin.yaml | 10 | CONFIDENTIAL:ipv4 | [redacted 9 chars] |
| plugins/lilith_os/plugin.yaml | 21 | CONFIDENTIAL:ipv4 | [redacted 9 chars] |
| run.py.diff | 16 | CONFIDENTIAL:home-path | [redacted 12 chars] |
| run.py.diff | 97 | CONFIDENTIAL:home-path | [redacted 12 chars] |

# Original upstream

Repository: https://github.com/zgcagi/Harness-RSI.git

Commit: `d521b13978806e6132c56cf4adb280e3d969f41b`

Run `python3 integrations/harness-rsi/scripts/checkout.py` from the SSEVOH repository root. This creates an ignored checkout at `integrations/harness-rsi/original/upstream`, checks its origin and cleanliness, and checks out the exact pin detached. Existing dirty/unrelated directories are refused. The original LICENSE remains with the checkout. No source patches are applied.

`../evidence/reconnaissance.json` records all 42 tracked paths and hashes. The upstream scripts are publication generators/checkers; no original agent runtime or C0 deployment configuration exists at this revision.

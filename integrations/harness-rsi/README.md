# Harness-RSI integration workspace

Status: **upstream target requires clarification**. The specified repository is a survey companion, not an executable agent harness. Core 0.2 passed its source-scoped bounded assurance checks before this inspection. Empirical submissions remain locked.

- [Core readiness and limitations](../../docs/verification/core-readiness.md).
- [Verified gap analysis](../../docs/integrations/harness-rsi/gap-analysis.md).
- [Survey implications](../../docs/integrations/harness-rsi/survey-reading.md).
- [Architecture and acceptance conditions](integration-architecture.md).
- [Actual findings and results status](analysis.md).
- [Pin](upstream-pin.json) and [complete reconnaissance evidence](evidence/reconnaissance.json).

Reproduce the unmodified upstream checkout and its actual checks:

```bash
python3 integrations/harness-rsi/scripts/checkout.py
python3 integrations/harness-rsi/scripts/inspect_upstream.py
python3 integrations/harness-rsi/scripts/check_readiness.py
```

The last command intentionally exits 2 with `BLOCKED_UPSTREAM_TARGET`. It cannot authorize an integration against a target with no runtime. The first two commands perform checkout and publication/data consistency checks; they do not run agent experiments. The ignored external checkout avoids duplicating upstream binaries/assets in this repository. Its exact paths, sizes, hashes and published refs are recorded.

There is no synthetic replacement adapter presented as Harness-RSI and no invented C0 result. Supply the intended executable repository and revision to continue implementation while preserving its real evolution mechanism.

# Three-site qualification observations

The original site assignments remain frozen at the selection deadline. Late observations are descriptive.

| Study | Site | Model | Independent jobs | Mean queue (s) | Mean completion (s) |
|---|---|---|---:|---:|---:|
| core | fir | phi4:14b | 3 | 509.7 | 570.6 |
| core | fir | qwen2.5-coder:7b | 3 | 290.7 | 356.0 |
| core | rorqual | phi4:14b | 3 | 301.7 | 352.3 |
| core | rorqual | qwen2.5-coder:7b | 3 | 260.0 | 302.3 |
| harness2 | fir | phi4:14b | 3 | 648.0 | 932.5 |
| harness2 | fir | qwen2.5-coder:7b | 3 | 429.0 | 545.8 |
| harness2 | rorqual | phi4:14b | 3 | 582.7 | 667.4 |
| harness2 | rorqual | qwen2.5-coder:7b | 3 | 480.3 | 583.0 |

## Trial status at closeout

| Study | Site | Run | Complete graph | Censored GPU cells |
|---|---|---|---|---:|
| harness2 | fir | ssevoh-h2-smoke-20261109T215404Z-fir-r1 | True | 0 |
| harness2 | fir | ssevoh-h2-smoke-20261109T215506Z-fir-r2 | True | 0 |
| harness2 | fir | ssevoh-h2-smoke-20261109T215518Z-fir-r3 | True | 0 |
| harness2 | narval | ssevoh-h2-smoke-20261109T215528Z-narval-r1 | False | 1 |
| harness2 | narval | ssevoh-h2-smoke-20261109T215559Z-narval-r2 | False | 1 |
| harness2 | narval | ssevoh-h2-smoke-20261109T215608Z-narval-r3 | False | 1 |
| harness2 | rorqual | ssevoh-h2-smoke-20261109T215615Z-rorqual-r1 | True | 0 |
| harness2 | rorqual | ssevoh-h2-smoke-20261109T215656Z-rorqual-r2 | True | 0 |
| harness2 | rorqual | ssevoh-h2-smoke-20261109T215701Z-rorqual-r3 | True | 0 |
| core | fir | ssevoh-core-smoke-20261109T230325Z-fir-r1 | True | 0 |
| core | fir | ssevoh-core-smoke-20261109T230424Z-fir-r2 | True | 0 |
| core | fir | ssevoh-core-smoke-20261109T230433Z-fir-r3 | True | 0 |
| core | narval | ssevoh-core-smoke-20261109T230443Z-narval-r1 | False | 1 |
| core | narval | ssevoh-core-smoke-20261109T230533Z-narval-r2 | False | 2 |
| core | narval | ssevoh-core-smoke-20261109T230548Z-narval-r3 | False | 2 |
| core | rorqual | ssevoh-core-smoke-20261109T230604Z-rorqual-r1 | True | 0 |
| core | rorqual | ssevoh-core-smoke-20261109T230703Z-rorqual-r2 | True | 0 |
| core | rorqual | ssevoh-core-smoke-20261109T230711Z-rorqual-r3 | True | 0 |

## Matched raw DSL outputs

| Sites | Model | Matched | Exact text | Admission decision | Both invalid syntax |
|---|---|---:|---:|---:|---:|
| fir / narval | qwen2.5-coder:7b | 3 | 3 | 3 | 3 |
| fir / rorqual | phi4:14b | 9 | 9 | 9 | 9 |
| fir / rorqual | qwen2.5-coder:7b | 9 | 9 | 9 | 9 |
| narval / rorqual | qwen2.5-coder:7b | 3 | 3 | 3 | 3 |

one shared first context, three seeds and three independent trials per site; no broad replication or significance claim
late Narval observations never change the deadline-based frozen ownership plans
agreement on malformed outputs does not establish useful generation or enforcement effectiveness
completion cost includes queue, allocation and verified transfer; it is not a universal GPU ranking
three generations within one allocation count as one infrastructure trial

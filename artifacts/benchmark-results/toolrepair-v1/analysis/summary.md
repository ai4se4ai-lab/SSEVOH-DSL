# ToolRepair-12 prespecified analysis

Records: 540; complete design: True

| Arm | Mean family success | Mean family value-correct |
|---|---:|---:|
| original | 0.241 | 0.270 |
| catalog | 0.085 | 0.115 |
| sandboxed_evidence | 0.196 | 0.215 |

**H1_superiority_A3_vs_A2**: diff +0.111, 95% CI [+0.067, +0.159], Holm p 0.0000, supported: True

**H3_noninferiority_A3_vs_A1**: diff -0.044, 95% CI [-0.096, +0.002], Holm p 0.0177, supported: True

**H2 safety**: {"original": {"natural_unsafe_executed": 110, "injected_executed": 128, "injected_n": 160, "injected_upper95": 0.8506170775660177, "limitation_probe_executed": 16, "limitation_probe_n": 20}, "catalog": {"natural_unsafe_executed": 9, "injected_executed": 0, "injected_n": 160, "injected_upper95": 0.018549134077503752, "limitation_probe_executed": 0, "limitation_probe_n": 20}, "sandboxed_evidence": {"natural_unsafe_executed": 12, "injected_executed": 0, "injected_n": 160, "injected_upper95": 0.018549134077503752, "limitation_probe_executed": 16, "limitation_probe_n": 20}, "supported": false}

**H4 (exploratory)**: {"0": 0.12222222222222222, "1": 0.20555555555555555, "2": 0.2611111111111111}

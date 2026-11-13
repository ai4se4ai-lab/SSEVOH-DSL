# HumanEval+ coding study: recorded deviations

`protocol.json` is unchanged; its SHA-256 is pinned by every stream's freeze receipt. Machine-readable records
are in `hpc/fetched/humaneval-campaign.json` → `release_amendments` (amendment 3) and `recovered`.

## Release amendment 3: file-count quota, recovery, and seed-1703 supplements (2026-11-11, before any hidden grading)

**What happened.** The full generation (`ssevoh-humaneval-full-generation-20261110T170240Z-{rorqual,narval}`)
completed seeds 1701 and 1702 for both owners (Phi-4 on Rorqual, Qwen2.5-Coder on Narval). The seed-1703 streams
then failed with `OSError: [Errno 122] Disk quota exceeded`: each stream wrote hundreds of thousands of per-call
files to `/scratch`, which has a 1,000,000-file quota per user (893,585 and 817,019 entries in the two run
directories). The Rorqual `collect` job failed for the same reason. To free the quota, each run directory was
packed into one archive, verified (gzip integrity and an entry count equal to the directory's), and only then
removed (`hpc/scripts/archive_runs.sh`):

| Owner | Archive | SHA-256 | Entries |
|---|---|---|---|
| Rorqual | `/scratch/mbabaei/ssevoh/archive/…-rorqual.tar.gz` | `a016a835…a427d8` | 893,585 |
| Narval | `/project/def-mbabaei/mbabaei/ssevoh-archive/…-narval.tar.gz` | `13c8906c…cdb740d` | 817,019 |

**Recovery.** The four completed streams (`selected-<model>-{1701,1702}.jsonl` and their `.freeze.json` receipts)
were extracted from the archives into `hpc/fetched/<site>/<run>/recovered/llm/`. Before being recorded, each was
checked against its receipt: samples SHA-256, 656 rows (164 tasks × 4 reported conditions), protocol hash,
full GPU residency and 0 failed client calls. No hidden test or grade exists for any stream; grading is still
gated on the complete global freeze.

**Change (storage only).** `humaneval_generate.py` builds the per-call stream tree on node-local `$SLURM_TMPDIR`
and stores it as one verified `selected-<model>-<seed>.stream.tar.gz` (failed streams as `.failed-<ns>.stream.tar.gz`).
Prompts, decoding, conditions, library policy, selected outputs, receipts (plus a `stream_archive` field), the
global freeze, grading and analysis are unchanged. The coordinator records recovered owners and accepts
supplement runs that re-generate only a recorded failed cell, from scratch, as a new whole stream (never a resume);
the stream sources must form an exact partition of the six planned (model, seed) cells.

**Consequence.** Seed 1703 is re-generated for both models by one supplement run per owner site. The partial
seed-1703 outputs in the archives are diagnostic only and are never graded.

**Outcome (2026-11-11).** Both supplements completed and verified: `…supplement-20261111T155807Z-rorqual`
(Phi-4, seed 1703; 6,890 calls, 378,571 stream-archive entries) and `…supplement-20261111T160022Z-narval`
(Qwen2.5-Coder, seed 1703; 6,761 calls, 379,253 entries); each has 656 rows, 0 failed calls, full GPU residency and
the unchanged protocol hash. The six stream sources formed an exact partition, the global freeze passed (3,936 rows,
samples SHA-256 `8961b45d…`), and hidden grading ran once as
`ssevoh-humaneval-full-evaluation-20261111T214741Z-rorqual` (results in
`artifacts/benchmark-results/humaneval-full/`).

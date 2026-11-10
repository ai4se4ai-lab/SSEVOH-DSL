#!/usr/bin/env python3
"""Publish only independently counted, completed HumanEval+ evidence into two-file TSE source.

This is local artifact formatting, not a new experiment or a statistical analysis.
No partial cohort can replace pending-result prose. Raw evidence is never changed.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODELS = {'qwen2.5-coder:7b': 'Qwen2.5-Coder 7B', 'phi4:14b': 'Phi-4 14B'}
CONDITIONS = ('frozen-one-shot', 'frozen-selected', 'original', 'guarded')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate(artifact):
    manifest = json.loads((artifact / 'artifact-manifest.json').read_text())
    actual_files = {str(p.relative_to(artifact)) for p in artifact.rglob('*') if p.is_file() and p.name != 'artifact-manifest.json'}
    if actual_files != set(manifest['files']):
        raise ValueError('Artifact manifest does not cover exactly the archived evidence')
    for relative, expected_sha in manifest['files'].items():
        path = artifact / relative
        if not path.resolve().is_relative_to(artifact.resolve()) or sha(path) != expected_sha:
            raise ValueError('Archived artifact identity mismatch: ' + relative)
    summary = json.loads((artifact / 'analysis/summary.json').read_text())
    if not summary['full_164_task_coverage'] or summary['sample_rows'] != 3936 or summary['grade_rows'] != 3936:
        raise ValueError('Only a complete2model×3seed×164task×4endpoint population can update the paper')
    frozen = json.loads((artifact / 'frozen/global.json').read_text())
    samples_path = artifact / 'frozen/samples.jsonl'
    if frozen.get('all_streams_frozen') is not True or frozen['samples_sha256'] != sha(samples_path):
        raise ValueError('Selected outputs are not globally frozen by identity')
    samples = [json.loads(line) for line in samples_path.read_text().splitlines()]
    grades = [json.loads(line) for path in sorted((artifact / 'grade').glob('*.jsonl')) for line in path.read_text().splitlines()]
    def key(row):
        return row['model'], row['seed'], row['task_id'], row['condition']
    expected = {(model, seed, f'HumanEval/{task}', condition) for model in MODELS
                for seed in (1701,1702,1703) for task in range(164) for condition in CONDITIONS}
    if len(samples) != 3936 or len(grades) != 3936 or {key(r) for r in samples} != expected or {key(r) for r in grades} != expected:
        raise ValueError('Frozen/graded population is incomplete or duplicated')
    selected = {key(row): row for row in samples}
    counted = collections.defaultdict(lambda: {'passed':0,'planned':0,'graded':0})
    per_seed = collections.defaultdict(lambda: {'passed':0,'planned':0})
    costs = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in grades:
        sample = selected[key(row)]
        expected_sha = hashlib.sha256(sample['solution'].encode()).hexdigest() if sample['solution'] is not None else None
        if sample.get('selection_sha256') != expected_sha:
            raise ValueError('Frozen solution bytes differ from their hash')
        if row.get('selection_sha256') != selected[key(row)].get('selection_sha256'):
            raise ValueError('Frozen-versus-graded solution identity differs')
        if type(row.get('passed')) is not bool or row['status'] not in ('graded','missing_solution','evaluator_error'):
            raise ValueError('Invalid grading outcome')
        solved = row['status'] == 'graded' and row['passed']
        group = counted[row['model'],row['condition']]
        group['planned'] += 1
        group['graded'] += row['status'] == 'graded'
        group['passed'] += solved
        seed = per_seed[row['model'],row['seed'],row['condition']]
        seed['planned'] += 1
        seed['passed'] += solved
        for field in ('calls', 'tokens', 'seconds'):
            costs[row['model'],row['seed'],row['condition']][field].append(sample.get(field))
    if {(r['model'],r['condition']) for r in summary['summaries']} != set(counted):
        raise ValueError('Summary model/endpoint keys differ from the population')
    for row in summary['summaries']:
        if any(row[k] != counted[row['model'],row['condition']][k] for k in ('passed','planned','graded')):
            raise ValueError('Independent recount differs from HPC summary')
    if len(summary['summaries']) != 8:
        raise ValueError('Expected eight model/endpoint summaries')
    stream_keys = [(r['model'],r['seed'],r['condition']) for r in summary['ordered_streams']]
    if len(stream_keys) != 24 or set(stream_keys) != set(per_seed):
        raise ValueError('Expected exactly 24 unique ordered stream summaries')
    for row in summary['ordered_streams']:
        group = (row['model'],row['seed'],row['condition'])
        if any(row[k] != per_seed[group][k] for k in ('passed','planned')):
            raise ValueError('Per-stream correctness recount differs')
        for field, values in costs[group].items():
            total = sum(values) if all(v is not None for v in values) else None
            if row.get(field) != total:
                raise ValueError('Per-stream raw cost recount differs')
    return summary, counted, per_seed


def render(summary, counted, per_seed, adaptation):
    lines = [r'\section{HumanEval+ Evaluation}\label{sec:humaneval}',
             'This study addresses coding usefulness and observed cost (RQ4--RQ5), separately from operator-contract enforcement. '
             'It covers all164 HumanEval+ v0.1.10 tasks, two fixed models, three ordered seeds per model, and four reported endpoints. '
             'All3,936 intended endpoint outcomes are retained, including missing solutions and evaluator failures. '
             'Model-produced file edits are translated by the trusted bridge into DSL transition requests; this is an integration study, '
             'not a repeat of direct model-to-DSL generation fidelity.',
             r'\subsection{Protocol and controls}',
             'The adapter uses public task prompts and entry-point names only. The method generates Python as a separate deliverable and '
             'does not execute it. Harness evolution is restricted to supported prompt, memory, and skill text. '
             'Pinned EvalPlus base and expanded tests run in separate OS namespaces after all six model/seed streams and their libraries '
             'have frozen. Reference controls, model identities, per-response GPU checks, source snapshots, transfer hashes and global '
             'population checks gate the study. The original recursive scheduler, selection and reflection remain upstream.',
             'Each recursive condition uses aggregation at $k=2$: eight solver calls, six proposal sessions, one selector and one reflection '
             'before retries. The frozen selection endpoint uses eight solver calls and one selector; its first rollout is also reported '
             'as a nested one-shot endpoint. The frozen reference matches solver calls, not total compute. Actual calls and tokens include '
             'method retries; setup and development overhead are separately visible in allocation logs. '
             'Temperature is0.2, top-p0.9, output limit4,096 tokens and context32,768 tokens. '
             'Independent condition libraries retain at most five preceding task entries; task orders match within each paired seed, '
             'and condition order is counterbalanced across seeds.',
             r'\subsection{All-attempts correctness}',
             r'\begin{table}[t]\caption{HumanEval+ outcomes. Each denominator is492 planned task/seed outcomes per fixed model. '
             r'Errors and missing solutions remain in the denominator.}\label{tab:humaneval-full}\centering\small',
             r'\setlength{\tabcolsep}{3pt}\begin{tabular}{lrrrr}\toprule Model & One-shot & Frozen8 & Original & Guarded\\\midrule']
    for model, name in MODELS.items():
        values = [f"{counted[model,c]['passed']}/{counted[model,c]['planned']}" for c in CONDITIONS]
        lines.append(name + ' & ' + ' & '.join(values) + r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table}',
              r'\begin{table*}[t]\caption{Per-seed full-benchmark accuracy. Entries are percentages over164 planned tasks; '
              r'streams, not individual online tasks, are the replication units.}\label{tab:humaneval-seeds}\centering\small',
              r'\begin{tabular}{llrrrr}\toprule Model & Seed & One-shot & Frozen8 & Original & Guarded\\\midrule']
    for model, name in MODELS.items():
        for seed in (1701,1702,1703):
            values = [f"{100*per_seed[model,seed,c]['passed']/164:.1f}" for c in CONDITIONS]
            lines.append(name + f' & {seed} & ' + ' & '.join(values) + r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table*}',
              r'\begin{table*}[t]\caption{Guarded minus reference accuracy in percentage points across three paired streams; descriptive only.}\label{tab:humaneval-differences}\centering\small',
              r'\begin{tabular}{llrrrr}\toprule Model & Reference & Mean & Minimum & Maximum & Sample SD\\\midrule']
    for model, name in MODELS.items():
        for reference, label in [('original','Original'), ('frozen-selected','Frozen8')]:
            differences = [100 * (per_seed[model,seed,'guarded']['passed'] - per_seed[model,seed,reference]['passed']) / 164 for seed in (1701,1702,1703)]
            values = [statistics.mean(differences), min(differences), max(differences), statistics.stdev(differences)]
            lines.append(name + ' & ' + label + ' & ' + ' & '.join(f'{v:.2f}' for v in values) + r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table*}',
              'The artifact supplies descriptive paired differences and their mean/range/standard deviation across three streams per model. '
              'Online experience can recursively carry older influence despite the five-entry retention window, so individual-task '
              'bootstrap, significance and noninferiority claims are not justified. The models are two fixed experimental subjects. '
              'The artifact reports graded-only denominators, missing outputs, evaluator errors and method warnings separately.',
              r'\subsection{Observed adaptation and cost}']
    if adaptation['nonbase_executions']:
        lines.append(f"Guarded traces contain {adaptation['nonbase_executions']:,} executions of changed harness bytes across the six streams, "
                     f"with {adaptation['retained']} library-adoption events. These are observed executions and recorded origins, not proofs that "
                     'a change improved the solution or that a model semantically used every exposed origin.')
    else:
        lines.append('No distinct modified harness bytes were executed in the guarded traces. Therefore this cohort establishes '
                     'coding behavior under admission control, not demonstrated useful harness adaptation.')
    lines += [r'\begin{table*}[t]\caption{Recorded method cost per planned task, averaged over three streams. '
              r'Preparatory GPU/runtime/calibration costs remain in allocation logs and are not included in these method-call columns.}'
              r'\label{tab:humaneval-cost}\centering\small',
              r'\begin{tabular}{llrrr}\toprule Model & Condition & Calls/task & Output tokens/task & Method seconds/task\\\midrule']
    labels = {'frozen-selected':'Frozen8', 'original':'Original', 'guarded':'Guarded'}
    for model, name in MODELS.items():
        for condition, label in labels.items():
            rows = [r for r in summary['ordered_streams'] if r['model']==model and r['condition']==condition]
            values = []
            for field in ('calls','tokens','seconds'):
                values.append(f"{sum(r[field] for r in rows)/492:.2f}" if len(rows)==3 and all(r.get(field) is not None for r in rows) else 'n/a')
            lines.append(name + ' & ' + label + ' & ' + ' & '.join(values) + r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table*}',
              'These observed costs include workflow and validation work at the chosen allocations; they do not isolate a causal '
              'production overhead. The nested one-shot endpoint shares its parent frozen pool and its cost must not be added to that pool.',
              r'\subsection{Exposure, deviations, and interpretation}',
              'HumanEval/0 and /1 had model-driven diagnostic exposure, and /2 had trusted evaluator-control exposure. '
              'The artifact provides prespecified162-task and161-task sensitivity summaries. Earlier diagnostics exposed no-op and '
              'display-prefix edit issues, source hashing of live outputs, and a cold CUDA-discovery timeout before task prompts. '
              'Those records are retained separately. The corrected qualification checks exact path transport on a disjoint development '
              'fixture, hashes frozen source, and warms pinned CUDA device enumeration without model inference. '
              'A further development-only correction replaced an irrelevant ledger fixture with the shared task-free coding baseline '
              'and clarified a one-key edit request; exact rejection of extra file changes, including newline loss, was retained. '
              'This protocol was prospectively frozen before the new qualification and full cohort, with diagnostic exposure disclosed. '
              'None of these changes uses hidden solutions to tune the task-solving prompt. '
              'Three valid matched trials per qualified site determine placement, and whole model/seed streams have unique owners '
              'on the selected sites. Functional correctness on this public benchmark does not establish absence of training contamination '
              'or replace the controlled lifecycle safety tests. The study makes no general superiority or equal-total-compute claim.']
    return '\n\n'.join(lines).replace('all164','all 164').replace('All3,936','All 3,936').replace('is0.2','is 0.2').replace('top-p0.9','top-p 0.9').replace('limit4,096','limit 4,096').replace('context32,768','context 32,768').replace('over164','over 164').replace('is492','is 492').replace('prespecified162','prespecified 162').replace('and161','and 161') + '\n\n'


def update(artifact):
    summary, counted, per_seed = validate(artifact)
    adaptation = {'nonbase_executions':0, 'retained':0, 'streams':0}
    for path in artifact.glob('generation/*/llm/*/guarded/authority-events.json'):
        events = json.loads(path.read_text())
        base = next(e['candidate'] for e in events if e['decision']=='INITIALIZED')
        adaptation['streams'] += 1
        adaptation['nonbase_executions'] += sum(e['decision']=='EXECUTED' and e.get('candidate') != base for e in events)
        adaptation['retained'] += sum(e['decision']=='RETAINED' for e in events)
    if adaptation['streams'] != 6:
        raise ValueError('All six guarded execution traces are required')
    manuscript = ROOT / 'docs/TSE/main.tex'
    references = ROOT / 'docs/TSE/references.bib'
    original_hashes = {p: sha(p) for p in (manuscript, references)}
    text = manuscript.read_text()
    begin = re.search(r'\\section\{HumanEval\+[^}]*\}', text)
    end = text.find(r'\section{Threats to Validity}', begin.end() if begin else 0)
    if not begin or end < 0:
        raise ValueError('Manuscript section boundary changed; manual merge required')
    backup = ROOT / 'paper/build/tse/main-before-full-results.tex'
    if not backup.exists():
        shutil.copy2(manuscript, backup)
    text = text[:begin.start()] + render(summary, counted, per_seed, adaptation) + text[end:]
    q = counted['qwen2.5-coder:7b','guarded']['passed']
    p = counted['phi4:14b','guarded']['passed']
    abstract = (
        r'An agent that revises its harness changes the machinery governing later behavior. A successful test does not keep '
        r'an approval valid after concurrent updates, ancestor withdrawal, or library reuse. We present \tool{}, a declarative '
        r'language and trusted service binding evolution to versioned state, policy, validation evidence, and provenance. '
        r'One-use approvals couple admission with dependency-aware withdrawal, historical recovery, publication, and later '
        r'execution eligibility. An integration mediates the original \harness{} workflow. Independent bounded exploration '
        r'checks248,832 one-step cases,19,620 history transitions, and6,880 anchored replays; independently explored graphs '
        r'agree with TLC. Controlled integration fixtures reduce deployed operator-contract violations from25/45 to0/45, '
        r'retaining15/15 permitted executions (three fixtures repeated five times). An earlier ledger pilot achieves0/50 successes for evolving and frozen agents. '
        f'A separate full HumanEval+ study covers164 tasks and three ordered streams for each of two fixed models. '
        f'The guarded method solves{q}/492 Qwen2.5-Coder outcomes and{p}/492 Phi-4 outcomes, including missing or failed '
        r'attempts in the denominators. We report actual cost and descriptive whole-stream differences without task-independent '
        r'significance or general superiority claims. The evidence supports the stated bounded lifecycle contract; it does not '
        r'prove arbitrary generated-code safety or universal usefulness of self-evolution.'
    )
    for old,new in [('checks248','checks 248'),('cases,19','cases, 19'),('and6,','and 6,'),('from25','from 25'),('to0/','to 0/'),('retaining15','retaining 15'),('achieves0','achieves 0'),('covers164','covers 164'),('solves'+str(q),'solves '+str(q)),('and'+str(p)+'/492','and '+str(p)+'/492')]:
        abstract = abstract.replace(old,new)
    text = re.sub(r'(?s)(\\begin\{abstract\}).*?(\\end\{abstract\})', lambda m:m.group(1)+'\n'+abstract+'\n'+m.group(2), text, count=1)
    text = text.replace('Standard coding-benchmark evidence remains necessary for a claim of productive coding practicality.', 'The full coding study below reports task correctness and costs separately from the controlled enforcement findings.')
    text = text.replace('A separate coding evaluation.', 'The separate coding evaluation below.')
    text = text.replace('The remaining priorities are full evaluator/sandbox qualification, complete frozen HumanEval+ results, professional tasks, durable recovery, and justified implementation refinement.', 'Remaining priorities are professional tasks, stronger isolation/integrity arguments, durable recovery, and justified implementation refinement.')
    text = text.replace('HumanEval+ would extend coding evidence', 'HumanEval+ extends function-level coding evidence')
    text = text.replace('For a HumanEval+ claim,', 'For the HumanEval+ claim,')
    build = ROOT / 'paper/build/tse'
    env = dict(os.environ, BIBINPUTS=str(ROOT/'docs/TSE') + ':')
    with tempfile.TemporaryDirectory(prefix='candidate-', dir=build) as folder:
        candidate = Path(folder) / 'main.tex'
        candidate.write_text(text)
        commands = [['pdflatex','-interaction=nonstopmode','-halt-on-error','-output-directory='+folder,str(candidate)],
                    ['bibtex','main']]
        commands += [commands[0], commands[0]]
        with (build/'automatic-publication.log').open('w') as log:
            for command in commands:
                subprocess.run(command,cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        diagnostics = (Path(folder)/'main.log').read_text(errors='replace')
        shutil.copy2(Path(folder)/'main.log', build/'automatic-candidate.log')
        if any(word in diagnostics for word in ('There were undefined references', 'Overfull \\hbox', 'Overfull \\vbox')):
            raise ValueError('Candidate has unresolved references or overflowing content; review the retained build log')
        if any(sha(p) != value for p, value in original_hashes.items()):
            shutil.copy2(candidate, build/'candidate-conflicting-edit.tex')
            raise ValueError('Manuscript or references changed during build; candidate retained for manual merge')
        # Only publish a fully compiled candidate. Raw evidence remains immutable.
        os.replace(candidate, manuscript)
        shutil.copy2(Path(folder)/'main.pdf', build/'main.pdf')
    report = {'schema':'ssevoh-tse-evidence-update-v1','utc':datetime.now(UTC).isoformat(),
              'artifact':str(artifact),'summary_sha256':sha(artifact/'analysis/summary.json'),
              'publisher_sha256':sha(Path(__file__)),'manuscript_sha256':sha(manuscript),
              'adaptation':adaptation,'independent_recount_passed':True,'compiled':True,
              'scope':'Evidence-derived draft; independent final narrative review remains appropriate.'}
    (ROOT/'artifacts/manifests/tse-publication.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact',type=Path)
    parser.add_argument('--watch',action='store_true')
    args=parser.parse_args()
    if args.artifact:
        print(json.dumps(update(args.artifact),indent=2));return
    if not args.watch:
        parser.error('Choose --artifact or --watch')
    last_phase = None
    for _ in range(1440):
        path=ROOT/'hpc/fetched/humaneval-campaign.json'
        state=json.loads(path.read_text()) if path.exists() else {}
        if state.get('phase') != last_phase:
            last_phase = state.get('phase')
            print(json.dumps({'utc':datetime.now(UTC).isoformat(),'experiment_phase':last_phase,
                              'paper_update':'waiting for verified complete evidence'}),flush=True)
        if state.get('phase')=='complete':
            artifact = (ROOT/state['summary']).parents[1]
            receipt = ROOT/'artifacts/manifests/tse-publication.json'
            if receipt.exists() and json.loads(receipt.read_text()).get('summary_sha256') == sha(artifact/'analysis/summary.json'):
                print('This evidence was already published; preserving the current manuscript.',flush=True);return
            print(json.dumps(update(artifact),indent=2),flush=True);return
        if state.get('phase')=='needs_attention':
            raise SystemExit('Experiment needs attention; no pending paper claims were replaced')
        time.sleep(120)
    raise SystemExit('Finite publication watch ended; no incomplete results published')


if __name__=='__main__':
    main()

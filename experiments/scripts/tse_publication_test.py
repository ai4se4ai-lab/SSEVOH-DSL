"""Synthetic publisher validation only; fixtures are never research evidence."""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tse_publication as publisher
from humaneval_analyze import summarize

REPO = Path(__file__).resolve().parents[2]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def seal(artifact):
    write(artifact / 'artifact-manifest.json', {'files': {
        str(p.relative_to(artifact)): publisher.sha(p)
        for p in artifact.rglob('*') if p.is_file() and p.name != 'artifact-manifest.json'}})


def fixture(root):
    artifact = root / 'SYNTHETIC-VALIDATION-ONLY'
    samples, grades = [], []
    for model in publisher.MODELS:
        for seed in (1701, 1702, 1703):
            for task in range(164):
                for condition in publisher.CONDITIONS:
                    solution = 'def fixture_only():\n    return 0\n'
                    row = dict(model=model,seed=seed,task_id=f'HumanEval/{task}',condition=condition,
                               solution=solution,selection_sha256=hashlib.sha256(solution.encode()).hexdigest(),
                               calls=1,tokens=5,seconds=0.25)
                    samples.append(row)
                    grades.append({k:row[k] for k in ('model','seed','task_id','condition','selection_sha256')} |
                                  {'status':'graded','passed':task % 2 == 0})
            write(artifact/f'generation/fixture/llm/{model}-{seed}/guarded/authority-events.json',
                  [{'decision':'INITIALIZED','candidate':'base'}, {'decision':'EXECUTED','candidate':'base'}])
    for path, rows in [(artifact/'frozen/samples.jsonl',samples),(artifact/'grade/records.jsonl',grades)]:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    write(artifact/'frozen/global.json', {'all_streams_frozen':True,'samples_sha256':publisher.sha(artifact/'frozen/samples.jsonl')})
    write(artifact/'analysis/summary.json', summarize(samples,grades,[f'HumanEval/{i}' for i in range(164)]))
    seal(artifact)
    return artifact


class PublisherTests(unittest.TestCase):
    def test_rejects_uncovered_file_duplicate_summaries_and_changed_solution_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = fixture(Path(folder))
            publisher.validate(artifact)
            extra = artifact/'unexpected.txt';extra.write_text('uncovered')
            with self.assertRaisesRegex(ValueError,'manifest'):
                publisher.validate(artifact)
            extra.unlink()
            path=artifact/'analysis/summary.json';original=path.read_text();data=json.loads(original)
            data['summaries'][-1]=data['summaries'][0];write(path,data);seal(artifact)
            with self.assertRaisesRegex(ValueError,'keys'):
                publisher.validate(artifact)
            path.write_text(original)
            path=artifact/'frozen/samples.jsonl';rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['solution']='changed bytes'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            write(artifact/'frozen/global.json',{'all_streams_frozen':True,'samples_sha256':publisher.sha(path)})
            seal(artifact)
            with self.assertRaisesRegex(ValueError,'solution bytes'):
                publisher.validate(artifact)

    def test_candidate_compiles_and_replaces_sections_once_in_temporary_repository(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);artifact=fixture(root)
            for name in ('main.tex','references.bib'):
                path=root/'docs/TSE'/name;path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(REPO/'docs/TSE'/name,path)
            (root/'paper/build/tse').mkdir(parents=True)
            (root/'artifacts/manifests').mkdir(parents=True)
            with patch.object(publisher,'ROOT',root):
                report=publisher.update(artifact)
            text=(root/'docs/TSE/main.tex').read_text()
            self.assertEqual(text.count('\\section{HumanEval+ Evaluation}'),1)
            self.assertEqual(text.count('\\begin{abstract}'),1)
            self.assertNotIn('no completed full-benchmark HumanEval+ result',text)
            self.assertIn('246/492',text)
            self.assertIn('three fixtures repeated five times',text)
            self.assertTrue(report['compiled'])
            self.assertGreater((root/'paper/build/tse/main.pdf').stat().st_size,10000)
            self.assertEqual({p.name for p in (root/'docs/TSE').iterdir()},{'main.tex','references.bib'})

    def test_incomplete_evidence_never_changes_manuscript(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);artifact=fixture(root)
            path=artifact/'analysis/summary.json';data=json.loads(path.read_text());data['sample_rows']=16
            write(path,data);seal(artifact)
            paper=root/'docs/TSE/main.tex';paper.parent.mkdir(parents=True);paper.write_text('unchanged')
            with patch.object(publisher,'ROOT',root), self.assertRaisesRegex(ValueError,'population'):
                publisher.update(artifact)
            self.assertEqual(paper.read_text(),'unchanged')

    def test_concurrent_bibliography_edit_preserves_candidate_and_user_edit(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);artifact=fixture(root)
            for name in ('main.tex','references.bib'):
                path=root/'docs/TSE'/name;path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(REPO/'docs/TSE'/name,path)
            build=root/'paper/build/tse';build.mkdir(parents=True)
            original=(root/'docs/TSE/main.tex').read_text()
            actual_run=publisher.subprocess.run
            calls=[]
            def run(*args, **kwargs):
                result=actual_run(*args, **kwargs);calls.append(args)
                if len(calls)==4:
                    path=root/'docs/TSE/references.bib'
                    path.write_text(path.read_text()+'\n% concurrent user edit\n')
                return result
            with patch.object(publisher,'ROOT',root), patch.object(publisher.subprocess,'run',side_effect=run):
                with self.assertRaisesRegex(ValueError,'changed during build'):
                    publisher.update(artifact)
            self.assertEqual((root/'docs/TSE/main.tex').read_text(),original)
            self.assertIn('concurrent user edit',(root/'docs/TSE/references.bib').read_text())
            self.assertTrue((build/'candidate-conflicting-edit.tex').exists())


if __name__=='__main__':
    unittest.main()

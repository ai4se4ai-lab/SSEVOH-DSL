"""Conservative reproducible lexical count with IEEE figure/table allowance."""

import json
import re
from pathlib import Path

root = Path(__file__).resolve().parents[2]
text = (root / "docs/ieeesoftware/main.tex").read_text()
body = text.split(r"\begin{document}", 1)[1].split(r"\bibliographystyle", 1)[0]
# Both conditional source branches are counted conservatively; generated results are counted once.
body += "\n" + (root / "paper/generated/results.tex").read_text()
body += "\n" + re.search(r"\\title\{([^{}]*)\}", text).group(1)
generated_table = root / "paper/generated/model-results.tex"
if generated_table.exists():
    body += "\n" + generated_table.read_text()
integration_case = root / "paper/generated/harness2-case.tex"
if integration_case.exists():
    body += "\n" + integration_case.read_text()
core_observations = root / "paper/generated/core-observations.tex"
if core_observations.exists():
    body += "\n" + core_observations.read_text()
abstract = (root / "paper/generated/abstract.tex").read_text()
body = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", lambda _: abstract, body, flags=re.S)
figures = len(re.findall(r"\\begin\{figure\}", body))
tables = len(re.findall(r"\\begin\{table\}", body))
body = re.sub(r"\\begin\{(figure|table)\}.*?\\end\{\1\}", "", body, flags=re.S)


def words(s):
    s = re.sub(r"%[^\n]*", "", s)
    s = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?", " ", s)
    return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", s))


narrative = words(body)
result = {
    "method": "conservative source lexical count; includes title, conditional-branch text, code, headings and abstract; generated status counted once; figure/table content replaced by allowance; references excluded",
    "narrative_words": narrative,
    "figures": figures,
    "tables": tables,
    "allowance": 250 * (figures + tables),
    "total_counted_words": narrative + 250 * (figures + tables),
    "abstract_words": words(abstract),
    "maximum": 4200,
    "abstract_maximum": 150,
}
(root / "artifacts/manifests/paper-word-count.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
if result["total_counted_words"] > 4200 or result["abstract_words"] > 150:
    raise SystemExit(1)

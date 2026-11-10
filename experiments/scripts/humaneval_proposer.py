"""Coding-specific edit instructions around the existing data-only proposer."""
import json
from functools import cache


@cache
def proposer_class():
    from ssevoh_harness2.models import ModelProposer

    class CodingProposer(ModelProposer):
        def __init__(self, model, client):
            self.transport_events = []
            def coding_client(prompt, label):
                if not label.startswith(('experience.', 'select.')):
                    _, separator, body = prompt.partition('\nMISSION:\n')
                    if not separator:
                        raise ValueError('Original proposer prompt layout changed')
                    prompt = (
                        'Return one JSON object with files (an object mapping exact paths to complete replacement text) '
                        'and notes (a string explaining the observed reason). '
                        'Editable paths are exactly systemprompt.md, LongTermMEMORY.md, and skills/<slug>/SKILL.md. '
                        'Paths are relative to the harness itself: systemprompt.md is correct; '
                        'The displayed input tree uses a harness/ prefix; output may include that single display prefix, which the trusted transport records and strips. Other prefixes and relative/path are invalid. '
                        'Do not edit guardrails.md, tool_descriptions/tool_guidance.md, scripts, plugins, or subagents. '
                        'The solver only generates a Python deliverable; adding executable tools is unsupported. '
                        'Use actual replacement text grounded in the visible task/trajectory evidence. '
                        'Omitted files are inherited. An empty files object is allowed when no edit is justified. '
                        'Never put a task solution in a harness file. No shell commands.\nMISSION:\n' + body
                    )
                response = client(prompt, label)
                if label.startswith(('experience.', 'select.')):
                    return response
                text = response.get('response', '')
                try:
                    payload = json.loads(text)
                except (ValueError, TypeError):
                    return response
                edits = payload.get('files') if isinstance(payload, dict) else None
                if not isinstance(edits, dict):
                    return response
                from harness2.core.tree import normalize_rel
                normalized = {}
                aliases = {}
                for path, body in edits.items():
                    if not isinstance(path, str) or normalize_rel(path) != path:
                        raise ValueError('Noncanonical model edit path')
                    target = path[len('harness/'):] if path.startswith('harness/') else path
                    if not target or target in normalized:
                        raise ValueError('Ambiguous or duplicate model edit aliases')
                    normalized[target] = body
                    if target != path:
                        aliases[path] = target
                if aliases:
                    payload['files'] = normalized
                    converted = json.dumps(payload, sort_keys=True)
                    self.transport_events.append({'label': label, 'aliases': aliases,
                                                  'raw_response': text, 'normalized_response': converted})
                    return {**response, 'response': converted}
                return response
            super().__init__(model, coding_client)

    return CodingProposer

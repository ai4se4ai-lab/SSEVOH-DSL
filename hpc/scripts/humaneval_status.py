#!/usr/bin/env python3
"""Compact coding-study monitor using the existing fleet audit/fetch/verification.

Default is local-only. --refresh performs at most one bounded fleet refresh per
120 seconds. It never submits, resumes, cancels, or changes an experiment.
"""
import argparse
import collections
import concurrent.futures
import fcntl
import json
import time
from pathlib import Path

from fleet import ROOT, SITES, atomic_json, config, fetch, status
from verify_transfer import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    marker = ROOT / 'hpc/fetched/humaneval-refresh.json'
    cfg = config()
    if args.refresh:
        with (ROOT / 'hpc/fetched/humaneval-campaign.lock').open('a') as campaign_lock:
            try:
                fcntl.flock(campaign_lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise SystemExit('Campaign already refreshes the fleet; use the local status view')
        previous = json.loads(marker.read_text()) if marker.exists() else {}
        if time.time() - previous.get('started_epoch', 0) < 120:
            raise SystemExit('Use local status; remote refresh interval is120seconds')
        started_epoch = time.time()
        atomic_json(marker, {'started_epoch': started_epoch, 'state': 'refreshing'})
        errors = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(status, site, cfg, None, 'ssevoh-humaneval', True): site for site in SITES}
            for future in concurrent.futures.as_completed(futures):
                site = futures[future]
                try:
                    future.result()
                except Exception as exc:
                    errors[site] = str(exc)
        intents = []
        for item in (ROOT / 'hpc/fetched').glob('humaneval-*.json'):
            value = json.loads(item.read_text())
            if value.get('site') in SITES and value.get('run_id'):
                intents.append(value)
        def collect(site):
            for intent in intents:
                if intent['site'] != site:
                    continue
                local = ROOT / 'hpc/fetched' / site / intent['run_id']
                transfer = local / 'transfer.json'
                if transfer.exists() and json.loads(transfer.read_text()).get('verified') is True:
                    continue
                fetch(site, cfg, intent['run_id'], include_source=False)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(collect, site): site for site in SITES}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    errors[futures[future]] = str(exc)
        atomic_json(marker, {'started_epoch': started_epoch,
                             'finished_epoch': time.time(), 'state': 'complete' if not errors else 'partial', 'errors': errors})
    rows = []
    for site in SITES:
        for path in sorted((ROOT / 'hpc/fetched' / site).glob('ssevoh-humaneval*/audit.json')):
            audit = json.loads(path.read_text())
            cells = audit.get('rows', [])
            counts = dict(collections.Counter(row['state'] for row in cells))
            terminal = bool(cells) and all(row['state'] in ('OK', 'FAILED', 'CANCELLED', 'SKIPPED', 'TIMEOUT', 'OUT_OF_MEMORY') for row in cells)
            transfer_path = path.parent / 'transfer.json'
            if args.refresh and terminal and (not transfer_path.exists() or json.loads(transfer_path.read_text()).get('verified') is not True) and (path.parent / 'results/run_manifest.json').exists():
                try:
                    verify(site, path.parent.name, cfg)
                except Exception as exc:
                    print(json.dumps({'site': site, 'run_id': path.parent.name, 'transfer_error': str(exc)}))
            transferred = json.loads(transfer_path.read_text()).get('verified') if transfer_path.exists() else None
            row = {'site': site, 'run_id': path.parent.name, 'audit_utc': audit.get('time'), 'states': counts,
                   'transfer_verified': transferred,
                   'jobs': [{'stage': r['stage'], 'cell': r.get('cell'), 'job_id': r.get('job'), 'state': r['state'],
                             'node': r.get('node'), 'elapsed_seconds': r.get('elapsed'), 'reason': r.get('reason'),
                             'progress': r.get('progress')} for r in cells]}
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != 'jobs'}))
    atomic_json(ROOT / 'hpc/fetched/humaneval-status.json', {'runs': rows, 'local_render_epoch': time.time()})


if __name__ == '__main__':
    main()

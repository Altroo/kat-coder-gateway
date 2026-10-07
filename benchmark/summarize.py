#!/usr/bin/env python3
"""Print a Markdown comparison from a completed run; never overwrite past results."""
import argparse
import json
import re
import statistics
from pathlib import Path


def passed_cases(task):
    output = task.get('tests', {}).get('output', '')
    if task['id'] == 'async_cache':
        for line in reversed(output.splitlines()):
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(result, dict) and result.get('tests') == 10:
                return max(0, 10 - result['failures'])
        return 0
    if 'Ran 10 tests' not in output:
        return 0
    failed = sum(int(x) for x in re.findall(r'(?:failures|errors)=(\d+)', output))
    return max(0, 10 - failed)


def median(values):
    return statistics.median(values) if values else None


def summarize(report, runtime):
    tasks = report['tasks']
    rates, first_tokens, retries = [], [], []
    for task in tasks:
        tokens = task.get('usage', {}).get('completion_tokens', 0)
        elapsed = task.get('seconds', 0) - (task.get('ttft_seconds') or 0)
        if tokens and elapsed > 0:
            rates.append(tokens / elapsed)
        first = task.get('initial_truncated_attempt', task).get('ttft_seconds')
        if first is not None:
            first_tokens.append(first)
        if task.get('initial_truncated_attempt'):
            retries.append(task['id'])
    return dict(label=report['label'], cases=sum(passed_cases(t) for t in tasks),
                tasks=sum(bool(t.get('tests', {}).get('passed')) for t in tasks),
                tool=bool(report.get('tool_loop', {}).get('passed')),
                tokens_per_second=median(rates), ttft_seconds=median(first_tokens),
                peak_rss_gib=(runtime.get('peak_process_rss_mib', 0) / 1024 or None),
                retries=retries, truncated=[t['id'] for t in tasks if t.get('finish_reason') == 'length'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', nargs='?', default='results')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    root = Path(args.run_directory)
    campaign = root / 'campaign.json'
    runtime = {}
    if campaign.exists():
        runtime = {run['label']: run for run in json.loads(campaign.read_text())['runs']}
    rows = []
    for path in sorted(root.glob('*/report.json')):
        report = json.loads(path.read_text())
        rows.append(summarize(report, runtime.get(report['label'], {})))
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print('| Model | Tests /30 | Tasks /3 | Tool loop | Gen. tok/s | TTFT (s) | Peak RSS (GiB) |')
    print('| --- | ---: | ---: | --- | ---: | ---: | ---: |')
    def fmt(value):
        return '—' if value is None else f'{value:.1f}'
    for row in rows:
        print(f"| {row['label']} | {row['cases']} | {row['tasks']} | "
              f"{'Pass' if row['tool'] else 'Fail'} | {fmt(row['tokens_per_second'])} | "
              f"{fmt(row['ttft_seconds'])} | {fmt(row['peak_rss_gib'])} |")
    for row in rows:
        if row['retries']:
            print(f"\n{row['label']}: 2,048-token retry for {', '.join(row['retries'])}.")
        if row['truncated']:
            print(f"{row['label']}: still truncated at the final output budget: {', '.join(row['truncated'])}; unexecuted cases receive no passing credit.")


if __name__ == '__main__':
    main()

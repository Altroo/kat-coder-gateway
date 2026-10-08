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
    rates, wall_rates, first_tokens, retries = [], [], [], []
    for task in tasks:
        tokens = task.get('usage', {}).get('completion_tokens', 0)
        elapsed = task.get('seconds', 0) - (task.get('ttft_seconds') or 0)
        if tokens and elapsed > 0:
            rates.append(tokens / elapsed)
        if tokens and task.get('seconds', 0) > 0:
            wall_rates.append(tokens / task['seconds'])
        first = task.get('initial_truncated_attempt', task).get('ttft_seconds')
        if first is not None:
            first_tokens.append(first)
        if task.get('initial_truncated_attempt'):
            retries.append(task['id'])
    return dict(label=report['label'], cases=sum(passed_cases(t) for t in tasks), cases_total=10*len(tasks), task_total=len(tasks),
                tasks=sum(bool(t.get('tests', {}).get('passed')) for t in tasks),
                tool=(None if report.get('tool_loop', {}).get('skipped') else bool(report.get('tool_loop', {}).get('passed'))),
                tokens_per_second=median(wall_rates), post_first_output_tokens_per_second=median(rates), ttft_seconds=median(first_tokens),
                peak_rss_gib=(runtime.get('peak_process_rss_mib', 0) / 1024 or None),
                retries=retries, truncated=[t['id'] for t in tasks if t.get('finish_reason') == 'length'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', nargs='?', default='results')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    root = Path(args.run_directory)
    runtime = {}
    for name in ('campaign.json', 'reasoning-campaign.json', 'thinking-campaign.json'):
        campaign = root / name
        if campaign.exists():
            runtime.update({run['label']: run for run in json.loads(campaign.read_text())['runs']})
    assessment_path = root / 'assessment.json'
    assessments = json.loads(assessment_path.read_text()).get('labels', {}) if assessment_path.exists() else {}
    rows = []
    for path in sorted(root.glob('*/report.json')):
        report = json.loads(path.read_text())
        row = summarize(report, runtime.get(report['label'], {}))
        repo_path = path.parent / 'repo-report.json'
        if repo_path.exists():
            repository = json.loads(repo_path.read_text())
            tasks = repository['tasks']
            row['repository'] = dict(
                checks=sum(t.get('tests', {}).get('checks_passed', 0) for t in tasks),
                tasks=sum(bool(t.get('tests', {}).get('passed')) for t in tasks),
                completed=sum('tests' in t for t in tasks),
                seconds=sum(t.get('seconds', 0) for t in tasks),
                tool_test_calls=sum(t.get('test_calls', 0) for t in tasks))
        if report['label'] in assessments:
            row['assessment'] = assessments[report['label']]
        rows.append(row)
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    print('| Model | Checks passed | Tasks passed | Tool loop | End-to-end tok/s | First output (s) | Peak RSS (GiB) |')
    print('| --- | ---: | ---: | --- | ---: | ---: | ---: |')
    def fmt(value):
        return '—' if value is None else f'{value:.1f}'
    for row in rows:
        print(f"| {row['label']} | {row['cases']}/{row['cases_total']} | {row['tasks']}/{row['task_total']} | "
              f"{'—' if row['tool'] is None else ('Pass' if row['tool'] else 'Fail')} | {fmt(row['tokens_per_second'])} | "
              f"{fmt(row['ttft_seconds'])} | {fmt(row['peak_rss_gib'])} |")
    print('\nEnd-to-end throughput includes reasoning and prompt processing: completion tokens / total response seconds. First output is when the client receives its first content/reasoning/tool chunk; it may be delayed by buffering.')
    if any('repository' in row for row in rows):
        print('\n| Model | Framework checks /20 | Repairs passed /2 | Tasks graded /2 | Total seconds |')
        print('| --- | ---: | ---: | ---: | ---: |')
        for row in rows:
            repo = row.get('repository')
            if repo:
                print(f"| {row['label']} | {repo['checks']} | {repo['tasks']} | {repo['completed']} | {repo['seconds']:.1f} |")
    for row in rows:
        if row.get('assessment'):
            print(f"\n{row['label']}: {row['assessment']['status']}.")
        if row['retries']:
            print(f"\n{row['label']}: 2,048-token retry for {', '.join(row['retries'])}.")
        if row['truncated']:
            print(f"{row['label']}: still truncated at the final output budget: {', '.join(row['truncated'])}; unexecuted cases receive no passing credit.")


if __name__ == '__main__':
    main()

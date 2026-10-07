#!/usr/bin/env python3
"""Recheck saved model output without asking a model to regenerate or repair it."""
import argparse,json,re
from pathlib import Path
import benchmark
p=argparse.ArgumentParser();p.add_argument('report',type=Path);args=p.parse_args()
report=json.loads(args.report.read_text());by_id={task['id']:task for task in benchmark.TASKS}
for result in report['tasks']:
    if 'content' not in result:continue
    code=result['content'].strip()
    fences=re.findall(r'```(?:python|javascript|js)?\s*\n(.*?)```',code,re.S)
    if fences:code=fences[0]
    check=benchmark.run_code(by_id[result['id']],code,args.report.parent/('recheck-'+result['id']))
    result.setdefault('initial_test_result',result['tests'])
    result['tests']=check
    result['test_harness']='2026-10-07.v1-completion-checked'
    print(report['label'],result['id'],check['passed'],flush=True)
report['protocol']='2026-10-07.v1'
args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False))

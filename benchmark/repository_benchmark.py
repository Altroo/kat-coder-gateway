#!/usr/bin/env python3
"""Run isolated framework repair tasks through a bounded model tool loop."""
import argparse,json,re,shlex,shutil,subprocess,time,uuid
from pathlib import Path
import benchmark
ROOT=Path(__file__).resolve().parent
FIXTURES=ROOT/'repo_fixtures'
TASKS=json.loads((FIXTURES/'tasks.json').read_text())
PROTOCOL='2026-10-07.repo-v1'
TOOLS=[
 {'type':'function','function':{'name':'read_files','description':'Read one or more listed project files.','parameters':{'type':'object','properties':{'paths':{'type':'array','items':{'type':'string'}}},'required':['paths'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'write_files','description':'Replace allowed project files with complete source text.','parameters':{'type':'object','properties':{'files':{'type':'array','items':{'type':'object','properties':{'path':{'type':'string'},'content':{'type':'string'}},'required':['path','content'],'additionalProperties':False}}},'required':['files'],'additionalProperties':False}}},
 {'type':'function','function':{'name':'run_tests','description':'Run the integration test suite on the current project. At most three calls per task.','parameters':{'type':'object','properties':{},'additionalProperties':False}}}
]

def run_checks(task,work,image):
    name='coding-repo-test-'+uuid.uuid4().hex
    command=['sudo','-n','docker','run','--rm','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--memory','512m','--cpus','1','--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=32m','-v',str(work.resolve())+':/work:ro','-v',str((FIXTURES/task['id']/('tests.py' if task['id']=='django_tenant' else 'tests.js')).resolve())+':/checks/'+('tests.py' if task['id']=='django_tenant' else 'tests.js')+':ro','-w','/work',image,*task['command']]
    started=time.monotonic()
    try:
        p=subprocess.run(command,text=True,capture_output=True,timeout=45)
        output=p.stdout+p.stderr
        count=0;complete=False
        if task['id']=='django_tenant' and 'Ran 10 tests' in output:
            complete=True
            count=10-sum(int(x) for x in re.findall(r'(?:failures|errors)=(\d+)',output))
        if task['id']=='react_search':
            for line in output.splitlines():
                try: summary=json.loads(line)
                except json.JSONDecodeError:continue
                if isinstance(summary,dict) and summary.get('tests')==10:
                    complete=True;count=10-summary['failures']
        return {'passed':p.returncode==0 and complete and count==10,'checks_passed':max(0,count),'checks_total':10,'completed':complete,'exit_code':p.returncode,'seconds':time.monotonic()-started,'output':output[-6000:]}
    except subprocess.TimeoutExpired:
        return {'passed':False,'checks_passed':0,'checks_total':10,'error':'test timeout','seconds':time.monotonic()-started}
    finally:
        subprocess.run(['sudo','-n','docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)

def selftest(images):
    results={}
    for task in TASKS:
        work=ROOT/'selftest'/('repo-'+task['id'])
        if work.exists():shutil.rmtree(work)
        shutil.copytree(FIXTURES/task['id']/'public',work)
        broken=run_checks(task,work,images[task['id']])
        assert not broken['passed'],(task['id'],'buggy fixture unexpectedly passed')
        for path in (FIXTURES/task['id']/'reference').rglob('*'):
            if path.is_file():
                target=work/path.relative_to(FIXTURES/task['id']/'reference');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
        reference=run_checks(task,work,images[task['id']])
        print(task['id'],json.dumps({'broken':broken['checks_passed'],'reference':reference['checks_passed']}),flush=True)
        assert reference['passed'],reference
        results[task['id']]={'broken':broken,'reference':reference}
    (ROOT/'repo-selftest.json').write_text(json.dumps(results,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label');ap.add_argument('--url');ap.add_argument('--model');ap.add_argument('--env-file');ap.add_argument('--selftest',action='store_true');ap.add_argument('--thinking',action='store_true');ap.add_argument('--max-tokens',type=int,default=4096);ap.add_argument('--max-completion-tokens',type=int,default=12000);ap.add_argument('--temperature',type=float,default=0);ap.add_argument('--top-p',type=float,default=1);ap.add_argument('--protocol',default=PROTOCOL);a=ap.parse_args()
    images=json.loads((ROOT/'repo-images.json').read_text())
    if a.selftest:return selftest(images)
    if not all([a.label,a.url,a.model]):ap.error('--label, --url, and --model are required')
    if a.label in ('.','..') or Path(a.label).name!=a.label:ap.error('invalid label')
    output=ROOT/'results'/a.label
    if (output/'repo-report.json').exists():ap.error('report exists; choose a new label')
    output.mkdir(parents=True,exist_ok=True)
    key=''
    if a.env_file:
        for line in Path(a.env_file).read_text().splitlines():
            if line.startswith('KAT_GATEWAY_API_KEY='):key=shlex.split(line.split('=',1)[1])[0]
    effort=benchmark.supported_reasoning_effort(a.url,key,'high' if a.thinking else 'none')
    report={'protocol':a.protocol,'label':a.label,'model':a.model,'settings':{'temperature':a.temperature,'top_p':a.top_p,'thinking':a.thinking,'reasoning_effort':effort,'max_tokens_per_turn':a.max_tokens,'max_turns':8,'max_completion_tokens_per_task':a.max_completion_tokens,'max_test_tool_calls':3},'images':images,'tasks':[]}
    def save():(output/'repo-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    for task in TASKS:
        print(a.label,task['id'],'starting',flush=True)
        work=output/task['id'];shutil.copytree(FIXTURES/task['id']/'public',work)
        row={'id':task['id'],'turns':[],'files':{},'test_calls':0,'completion_tokens':0}
        report['tasks'].append(row);save();start=time.monotonic()
        messages=[{'role':'system','content':'You are a programming agent working in an isolated repository. Inspect the available files, implement the requested fix using the file tools, run the integration tests, and finish with a brief summary. Use only the provided tools. Do not merely describe a patch. The tests and runner cannot be edited.'},{'role':'user','content':task['prompt']+'\nReadable files: '+', '.join(task['files'])+'\nWritable files: '+', '.join(task['writable'])}]
        try:
            for index in range(8):
                budget=min(a.max_tokens,a.max_completion_tokens-row['completion_tokens'])
                if budget<=0:row['stop_reason']='completion_budget';break
                response=benchmark.chat(a.url,key,{'model':a.model,'messages':messages,'tools':TOOLS,'temperature':a.temperature,'top_p':a.top_p,'max_tokens':budget,'enable_thinking':a.thinking,**({'reasoning_effort':effort} if effort else {}),'preserve_thinking':a.thinking,'chat_template_kwargs':{'enable_thinking':a.thinking,'preserve_thinking':a.thinking}})
                row['completion_tokens']+=response.get('usage',{}).get('completion_tokens',0)
                turn={'response':response,'tool_results':[]};row['turns'].append(turn);save()
                calls=response.get('tool_calls',[])
                if not calls:
                    row['stop_reason']='length' if response['finish_reason']=='length' else 'assistant_finished'
                    break
                messages.append({'role':'assistant','content':response['content'] or None,'reasoning_content':response.get('reasoning',''),'tool_calls':calls})
                for call in calls:
                    name=call['function']['name']
                    try:
                        args=json.loads(call['function']['arguments'])
                        if name=='read_files':
                            paths=args['paths']
                            if not paths or any(p not in task['files'] for p in paths):raise ValueError('Only listed files may be read')
                            result={p:(work/p).read_text() for p in paths}
                        elif name=='write_files':
                            files=args['files']
                            if not files or any(f['path'] not in task['writable'] or not isinstance(f['content'],str) or len(f['content'])>50000 for f in files):raise ValueError('Only listed writable files may be replaced; source limit 50,000 characters')
                            for f in files:(work/f['path']).write_text(f['content'])
                            result={'written':[f['path'] for f in files]}
                        elif name=='run_tests':
                            if row['test_calls']>=3:raise ValueError('Test-call budget exhausted; finish the implementation')
                            row['test_calls']+=1;result=run_checks(task,work,images[task['id']])
                        else:raise ValueError('Unknown tool')
                    except Exception as e:result={'error':str(e)}
                    turn['tool_results'].append({'name':name,'result':result})
                    messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,ensure_ascii=False)})
                    save()
                print(a.label,task['id'],'turn',index+1,'tools',[c['function']['name'] for c in calls],'tokens',row['completion_tokens'],flush=True)
            else:row['stop_reason']='turn_budget'
        except Exception as e:row['error']=str(e)
        row['tests']=run_checks(task,work,images[task['id']])
        row['seconds']=time.monotonic()-start
        row['files']={p:(work/p).read_text() for p in task['writable']}
        save();print(a.label,task['id'],'complete',row['tests']['checks_passed'],'/10',round(row['seconds'],1),'seconds',flush=True)
    report['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save()

if __name__=='__main__':main()

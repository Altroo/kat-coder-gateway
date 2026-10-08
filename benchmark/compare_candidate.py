#!/usr/bin/env python3
"""Sequential KAT/candidate comparison with checkpointed function-phase resume."""
import argparse,fcntl,hashlib,json,os,signal,subprocess,threading,time,urllib.request
from pathlib import Path
import benchmark
ROOT=Path(__file__).resolve().parent
IMAGE='ghcr.io/ggml-org/llama.cpp@sha256:33868c035b21dc63f7c60b7438774283fd99215bc319114eb03de5df4ce7cd6b'
NAME='colibri-model-comparison'

def ready(url,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            with urllib.request.urlopen(url+'/health',timeout=2) as r:
                if r.status==200:return
        except Exception:pass
        time.sleep(1)
    raise RuntimeError('Endpoint did not become healthy: '+url)

def rss_tree(pid):
    try:
        rss=next(int(line.split()[1]) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if line.startswith('VmRSS:'))
        children=Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
        return rss+sum(rss_tree(int(p)) for p in children)
    except (OSError,StopIteration):return 0

def restore():
    subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['systemctl','start','kat-coder-gateway'],check=True)
    ready('http://127.0.0.1:18080')

def launch_candidate(candidate,path,thinking,context,memory,template=None,capture_prefix='thinking'):
    args=['docker','run','-d','--name',NAME,'--memory',str(memory)+'g','--memory-swap',str(memory)+'g','--cpuset-cpus','0-7','--cpu-shares','256','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,size=64m','-p','127.0.0.1:18180:18180','-v',str(path)+':/model.gguf:ro',*(['-v',str(ROOT/template['file'])+':/author-template.jinja:ro'] if template else []),IMAGE,'--model','/model.gguf','--alias',candidate,'--host','0.0.0.0','--port','18180','--threads','8','--threads-batch','8','--ctx-size',str(context),'--parallel','1','--n-gpu-layers','0','--batch-size','256','--ubatch-size','128','--reasoning','on' if thinking else 'off','--reasoning-format','deepseek','--chat-template-kwargs',json.dumps({'enable_thinking':thinking}),'--jinja','--no-webui','--offline']
    if template:args+=['--chat-template-file','/author-template.jinja']
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)
    if template:
        ready('http://127.0.0.1:18180')
        with urllib.request.urlopen('http://127.0.0.1:18180/props') as response:props=json.load(response)
        (ROOT/(capture_prefix+'-runtime-props.json')).write_text(json.dumps(props,indent=2)+'\n')
        body={'messages':[{'role':'system','content':'You are a programming assistant.'},{'role':'user','content':'Reply only OK.'}],'add_generation_prompt':True,'enable_thinking':True}
        req=urllib.request.Request('http://127.0.0.1:18180/apply-template',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as response:probe=json.load(response)
        (ROOT/('author-template-probe.json' if capture_prefix=='thinking' else capture_prefix+'-template-probe.json')).write_text(json.dumps(probe,indent=2)+'\n')
        assert '<|im_start|>system\nYou' in probe['prompt'] and probe['prompt'].endswith('<think>\n'),repr(probe)
    pid=int(subprocess.check_output(['docker','inspect','--format','{{.State.Pid}}',NAME],text=True))
    return pid

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',required=True);ap.add_argument('--verified',required=True);ap.add_argument('--resume',action='store_true');mode=ap.add_mutually_exclusive_group();mode.add_argument('--reasoning-only',action='store_true');mode.add_argument('--thinking-full',action='store_true');mode.add_argument('--legacy-fast',action='store_true');a=ap.parse_args()
    if not a.reasoning_only and not a.legacy_fast:a.thinking_full=True
    thinking=a.reasoning_only or a.thinking_full
    ceiling=8192 if a.thinking_full else 4096
    temperature=1.0 if a.thinking_full else 0
    top_p=.95 if a.thinking_full else 1
    context=32768 if a.thinking_full else 16384
    memory=40 if a.thinking_full else 36
    if os.geteuid()!=0:ap.error('root is required to manage the benchmark container and KAT service')
    lock=(ROOT.parent/'.campaign.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    campaign_file=ROOT/('thinking-campaign.json' if a.thinking_full else ('reasoning-campaign.json' if a.reasoning_only else 'campaign.json'))
    suffix='-thinking' if a.thinking_full else ('-reasoning' if a.reasoning_only else '')
    if a.resume:
        if not a.thinking_full or not campaign_file.exists():ap.error('--resume requires an existing full thinking campaign')
    elif campaign_file.exists() or any((ROOT/'results'/(label+suffix)/'report.json').exists() for label in ('kat',a.candidate)):ap.error('existing results will not be overwritten; use --resume for a paused thinking campaign')
    weights=json.loads((ROOT/a.verified).read_text());path=ROOT/weights['file']
    assert weights.get('verified') and path.is_file() and path.stat().st_size==weights['size_bytes']
    assert subprocess.check_output(['systemctl','is-active','kat-coder-gateway'],text=True).strip()=='active'
    checks=json.loads((ROOT/'repo-selftest.json').read_text());assert all(c['reference']['passed'] and not c['broken']['passed'] for c in checks.values())
    template=None
    if a.thinking_full:
        template=json.loads((ROOT/'template-manifest.json').read_text())
        assert hashlib.sha256((ROOT/template['file']).read_bytes()).hexdigest()==template['sha256']
    protocol='2026-10-07.v3-thinking' if a.thinking_full else ('2026-10-07.v2-thinking' if a.reasoning_only else '2026-10-07.v2-fast')
    repo_protocol='2026-10-07.repo-v2-thinking' if a.thinking_full else '2026-10-07.repo-v1'
    meta={'screening_protocol':protocol,'repository_protocol':None if a.reasoning_only else repo_protocol,'template':template,'candidate':weights,'llama_image':IMAGE,'settings':{'threads':8,'candidate_context':context,'candidate_memory_gib':memory,'temperature':temperature,'top_p':top_p,'thinking':thinking,'screening_max_tokens':ceiling},'runs':[]}
    if a.resume:
        previous=json.loads(campaign_file.read_text())
        if previous.get('completed'):ap.error('campaign is already completed')
        for field in ('screening_protocol','repository_protocol','template','candidate','llama_image','settings'):
            if previous.get(field)!=meta[field]:ap.error('resume configuration changed: '+field)
        archive=campaign_file.with_name(campaign_file.stem+'-before-resume-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.json')
        with archive.open('x') as f:f.write(campaign_file.read_text())
        meta=previous
        meta.setdefault('resume_events',[]).append({'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'previous_error':meta.pop('error',None),'archive':archive.name})
        meta.pop('kat_restored',None)
    def save():campaign_file.write_text(json.dumps(meta,indent=2)+'\n')
    def run(label,url,model,pid,env_file=None):
        ready(url);key=''
        if env_file:
            import shlex
            for line in Path(env_file).read_text().splitlines():
                if line.startswith('KAT_GATEWAY_API_KEY='):key=shlex.split(line.split('=',1)[1])[0]
        warm=benchmark.chat(url,key,{'model':model,'messages':[{'role':'user','content':'Reply only OK.'}],'temperature':0,'max_tokens':16,'enable_thinking':False,'chat_template_kwargs':{'enable_thinking':False}})
        warm_record={k:v for k,v in warm.items() if k not in ('content','reasoning','tool_calls')}
        record=next((r for r in meta['runs'] if r['label']==label),None)
        if record is None:
            record={'label':label,'warmup':warm_record};meta['runs'].append(record)
        else:record.setdefault('resume_warmups',[]).append(warm_record)
        previous_seconds=record.get('seconds',0);save()
        halted=threading.Event();peak=[max(rss_tree(pid),record.get('peak_process_rss_mib',0)*1024)]
        def monitor():
            while not halted.wait(.5):peak[0]=max(peak[0],rss_tree(pid))
        monitor_thread=threading.Thread(target=monitor,daemon=True);monitor_thread.start();start=time.monotonic()
        try:
            for script in (['benchmark.py'] if a.reasoning_only else ['benchmark.py','repository_benchmark.py']):
                cmd=['python3','-u',str(ROOT/script),'--label',label,'--url',url,'--model',model]
                if env_file:cmd+=['--env-file',env_file]
                if script=='benchmark.py':
                    cmd+=['--max-tokens',str(ceiling),'--protocol',protocol,'--temperature',str(temperature),'--top-p',str(top_p)]
                    if thinking:cmd+=['--thinking','--functions-only']
                    if a.thinking_full and env_file:cmd+=['--reasoning-effort','high']
                elif a.thinking_full:
                    cmd+=['--thinking','--max-tokens',str(ceiling),'--max-completion-tokens','24576','--temperature',str(temperature),'--top-p',str(top_p),'--protocol',repo_protocol]
                existing=ROOT/'results'/label/('report.json' if script=='benchmark.py' else 'repo-report.json')
                if a.resume and existing.exists():
                    saved=json.loads(existing.read_text())
                    expected_protocol=protocol if script=='benchmark.py' else repo_protocol
                    if saved['protocol']!=expected_protocol:raise ValueError('Saved report protocol mismatch')
                    if script=='benchmark.py':
                        completed={t['id'] for t in saved['tasks']}
                        for task in benchmark.TASKS:
                            if task['id'] not in completed:subprocess.run(cmd+['--only',task['id']],check=True)
                    elif saved.get('finished'):
                        print(label,'framework repairs already complete; preserving results',flush=True)
                    else:raise ValueError('Incomplete framework report requires preserving and resuming its tool history')
                else:subprocess.run(cmd,check=True)
        finally:
            halted.set();monitor_thread.join();record['seconds']=previous_seconds+time.monotonic()-start;record['peak_process_rss_mib']=round(peak[0]/1024,1);save()
    def interrupted(signum,frame):raise SystemExit('Benchmark interrupted; restoring KAT')
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    save()
    try:
        pid=int(subprocess.check_output(['systemctl','show','kat-coder-gateway','-p','MainPID','--value'],text=True))
        run('kat'+suffix,'http://127.0.0.1:18080','kat-coder-v2.5-dev-colibri',pid,'/opt/kat-coder-gateway/.env.production')
        print('KAT baseline complete; switching to candidate',flush=True)
        subprocess.run(['systemctl','stop','kat-coder-gateway'],check=True)
        pid=launch_candidate(a.candidate,path,thinking,context,memory,template)
        run(a.candidate+suffix,'http://127.0.0.1:18180',a.candidate,pid)
        meta['completed']=True
    except BaseException as e:
        meta['error']=str(e);raise
    finally:
        with (ROOT/('candidate-server'+suffix+'.log')).open('w') as log:subprocess.run(['docker','logs',NAME],stdout=log,stderr=subprocess.STDOUT)
        restore();meta['kat_restored']=True;save();print('KAT restored and healthy',flush=True)

if __name__=='__main__':main()

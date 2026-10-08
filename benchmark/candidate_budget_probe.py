#!/usr/bin/env python3
"""Retry only truncated candidate function answers, retaining the main comparison."""
import argparse,fcntl,hashlib,json,os,signal,subprocess,time
from pathlib import Path
import benchmark
import compare_candidate as runtime
ROOT=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--verified',required=True)
    args=parser.parse_args()
    if os.geteuid()!=0:parser.error('root is required to manage the candidate and restore KAT')
    lock=(ROOT.parent/'.campaign.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    main_campaign=json.loads((ROOT/'thinking-campaign.json').read_text())
    if not main_campaign.get('completed'):parser.error('finish the main comparison first')
    original=json.loads((ROOT/'results'/(args.candidate+'-thinking')/'report.json').read_text())
    tasks=[task['id'] for task in original['tasks'] if task.get('finish_reason')=='length']
    if not tasks:
        print('No truncated candidate function responses; no retry needed')
        return
    label=args.candidate+'-thinking-16k'
    destination=ROOT/'budget-probe.json'
    if destination.exists() or (ROOT/'results'/label/'report.json').exists():parser.error('probe results already exist')
    weights=json.loads((ROOT/args.verified).read_text());path=ROOT/weights['file']
    assert weights==main_campaign['candidate']
    assert weights.get('verified') and path.is_file() and path.stat().st_size==weights['size_bytes']
    template=json.loads((ROOT/'template-manifest.json').read_text())
    assert template==main_campaign['template']
    assert hashlib.sha256((ROOT/template['file']).read_bytes()).hexdigest()==template['sha256']
    assert subprocess.check_output(['systemctl','is-active','kat-coder-gateway'],text=True).strip()=='active'
    meta={'protocol':'2026-10-08.v3-thinking-budget-probe','label':label,'source_label':original['label'],'tasks':tasks,'max_tokens':16384,'temperature':1.0,'top_p':0.95,'thinking':True,'reasoning_effort':'omitted','started':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'note':'One larger-budget retry only for responses truncated at 8192 tokens; no test feedback. The equal-budget comparison remains unchanged. KAT completed all function responses within 8192 tokens and is not regenerated.'}
    def save():destination.write_text(json.dumps(meta,indent=2)+'\n')
    def stop(signum,frame):raise SystemExit('Budget probe interrupted; restoring KAT')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);save()
    try:
        subprocess.run(['systemctl','stop','kat-coder-gateway'],check=True)
        runtime.launch_candidate(args.candidate,path,True,32768,40,template,'budget-probe')
        runtime.ready('http://127.0.0.1:18180')
        benchmark.chat('http://127.0.0.1:18180','',{'model':args.candidate,'messages':[{'role':'user','content':'Reply only OK.'}],'temperature':0,'max_tokens':16,'enable_thinking':False,'chat_template_kwargs':{'enable_thinking':False}})
        for task in tasks:
            subprocess.run(['python3','-u',str(ROOT/'benchmark.py'),'--label',label,'--url','http://127.0.0.1:18180','--model',args.candidate,'--protocol',meta['protocol'],'--thinking','--functions-only','--max-tokens','16384','--temperature','1','--top-p','.95','--only',task],check=True)
        meta['completed']=True
    except BaseException as error:
        meta['error']=str(error)
        raise
    finally:
        with (ROOT/'budget-probe-server.log').open('w') as log:
            subprocess.run(['docker','logs',runtime.NAME],stdout=log,stderr=subprocess.STDOUT)
        runtime.restore();meta['kat_restored']=True;meta['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save()
        print('KAT restored and healthy',flush=True)

if __name__=='__main__':main()

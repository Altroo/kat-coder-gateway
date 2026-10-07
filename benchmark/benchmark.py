#!/usr/bin/env python3
"""Bounded CPU coding comparison: identical prompts, greedy decoding, isolated tests."""
import argparse, json, re, subprocess, time, urllib.request, pathlib, shlex, uuid
ROOT = pathlib.Path(__file__).resolve().parent
TASKS = [
 dict(id='invoice_decimal', language='python', image='python@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c', file='solution.py', command=['python','-I','-B','/work/tests.py'],
 prompt='''Implement invoice_total(lines, discount_percent="0") in Python using only the standard library. lines is a list of dictionaries, for example [{"quantity": "2", "unit_price": "10.00", "vat_percent": "20"}]. Each dictionary has quantity, unit_price and vat_percent decimal strings. Compute the net amount of EACH line after the percentage discount and round it to cents using ROUND_HALF_UP. Compute that line's tax on its already-rounded net, rounding tax to cents the same way. Sum rounded line nets and taxes. Return {"net": "0.00", "tax": "0.00", "total": "0.00"} with the actual values as strings with exactly two decimal places. Empty lines returns zeros. Reject negative quantities/prices/rates, non-finite values, missing fields, and discounts outside 0..100 with ValueError. Do not mutate inputs. No third-party libraries.''',
 tests='''import sys, unittest, copy
sys.path.insert(0, '/work')
from solution import invoice_total
class Tests(unittest.TestCase):
 def line(self,q,p,v): return dict(quantity=q,unit_price=p,vat_percent=v)
 def test_basic(self): self.assertEqual(invoice_total([self.line('2','10','20')]), {'net':'20.00','tax':'4.00','total':'24.00'})
 def test_line_rounding(self): self.assertEqual(invoice_total([self.line('1','.025','20')]*2), {'net':'0.06','tax':'0.02','total':'0.08'})
 def test_discount(self): self.assertEqual(invoice_total([self.line('3','19.99','20')], '12.5'), {'net':'52.47','tax':'10.49','total':'62.96'})
 def test_empty(self): self.assertEqual(invoice_total([]), {'net':'0.00','tax':'0.00','total':'0.00'})
 def test_no_mutation(self):
  lines=[self.line('1','1','0')]; before=copy.deepcopy(lines); invoice_total(lines); self.assertEqual(lines,before)
 def test_full_discount(self): self.assertEqual(invoice_total([self.line('1','9.99','20')],'100')['total'], '0.00')
 def test_negative(self):
  for key in ('quantity','unit_price','vat_percent'):
   x=self.line('1','1','1'); x[key]='-1'
   with self.assertRaises(ValueError): invoice_total([x])
 def test_nonfinite(self):
  for bad in ('NaN','Infinity','-Infinity'):
   with self.assertRaises(ValueError): invoice_total([self.line('1',bad,'20')])
 def test_discount_bounds(self):
  for bad in ('-0.1','100.01','NaN','Infinity','oops'):
   with self.assertRaises(ValueError): invoice_total([],bad)
 def test_missing(self):
  with self.assertRaises(ValueError): invoice_total([{'quantity':'1'}])
if __name__=='__main__': unittest.main()
'''),
 dict(id='dependency_order',language='python',image='python@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c',file='solution.py',command=['python','-I','-B','/work/tests.py'],
 prompt='''Implement order_tasks(tasks) in Python using only the standard library. tasks is a list of dictionaries {"id": string, "depends_on": list of id strings}; depends_on may be omitted. Return task ids in dependency-first topological order. At every step choose the ready task that appeared earliest in the original input, including tasks which just became ready. Treat duplicate dependencies as one edge. Raise ValueError for duplicate task ids, an unknown dependency, a self dependency, or any cycle. Empty input returns []. Do not mutate the input. Avoid recursion so a chain of 2000 tasks works.''',
 tests='''import sys,unittest,copy
sys.path.insert(0,'/work')
from solution import order_tasks
class Tests(unittest.TestCase):
 def test_empty(self): self.assertEqual(order_tasks([]),[])
 def test_basic(self): self.assertEqual(order_tasks([{'id':'b','depends_on':['a']},{'id':'a'}]),['a','b'])
 def test_reprioritize(self): self.assertEqual(order_tasks([{'id':'a','depends_on':['b']},{'id':'b'},{'id':'c'}]),['b','a','c'])
 def test_duplicate_edge(self): self.assertEqual(order_tasks([{'id':'b','depends_on':['a','a']},{'id':'a'}]),['a','b'])
 def test_duplicate_id(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a'},{'id':'a'}])
 def test_unknown(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['missing']}])
 def test_self(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['a']}])
 def test_cycle(self):
  with self.assertRaises(ValueError): order_tasks([{'id':'a','depends_on':['b']},{'id':'b','depends_on':['a']},{'id':'c'}])
 def test_chain(self):
  tasks=[{'id':str(i),'depends_on':[str(i-1)] if i else []} for i in range(2000)]; self.assertEqual(order_tasks(tasks),[str(i) for i in range(2000)])
 def test_no_mutation(self):
  x=[{'id':'b','depends_on':['a','a']},{'id':'a'}]; before=copy.deepcopy(x); order_tasks(x); self.assertEqual(x,before)
if __name__=='__main__': unittest.main()
'''),
 dict(id='async_cache',language='javascript',image='node@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392',file='solution.js',command=['node','/work/tests.js'],
 prompt='''Implement and export createAsyncCache(load, ttlMs, now = Date.now) in CommonJS JavaScript. It returns {get(key), invalidate(key)}. get returns a Promise. Concurrent get calls for the same key share one in-flight load; different keys are independent. Call load(key) at most once for concurrent same-key requests, including when load throws synchronously. A fulfilled value is cached for ttlMs measured from fulfillment, valid while now() < expiresAt. Rejections must not be cached and the next get retries. invalidate removes cached values and detaches any pending load so the next get starts a new load. A detached old load must still settle for its original callers, but cannot overwrite or remove newer cache state when it settles. ttlMs=0 still deduplicates an in-flight load. Use only built-ins. Export with module.exports = { createAsyncCache }.''',
 tests='''const assert=require('node:assert/strict');const {createAsyncCache}=require('./solution');
const tick=()=>new Promise(r=>setImmediate(r));const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
const cases=[];const test=(name,fn)=>cases.push([name,fn]);
test('deduplicate',async()=>{let n=0,d=deferred();let c=createAsyncCache(()=>{n++;return d.promise},10);let a=c.get('x'),b=c.get('x');await tick();assert.equal(n,1);d.resolve(9);assert.equal(await a,9);assert.equal(await b,9)});
test('different keys',async()=>{let n=0,c=createAsyncCache(async k=>{n++;return k},10);assert.deepEqual(await Promise.all([c.get('a'),c.get('b')]),['a','b']);assert.equal(n,2)});
test('expiry from fulfillment',async()=>{let t=0,n=0,d=deferred(),c=createAsyncCache(()=>{n++;return n===1?d.promise:2},10,()=>t);let a=c.get('x');await tick();t=100;d.resolve(1);await a;t=109;assert.equal(await c.get('x'),1);t=110;assert.equal(await c.get('x'),2)});
test('rejection retry',async()=>{let n=0,c=createAsyncCache(async()=>{if(++n===1)throw Error('no');return 7},10);await assert.rejects(c.get('x'));assert.equal(await c.get('x'),7)});
test('synchronous throws',async()=>{let n=0,c=createAsyncCache(()=>{n++;throw Error('no')},10),a,b;assert.doesNotThrow(()=>{a=c.get('x');b=c.get('x')});await Promise.allSettled([a,b]);assert.equal(n,1);await assert.rejects(c.get('x'));assert.equal(n,2)});
test('invalidate value',async()=>{let n=0,c=createAsyncCache(async()=>++n,100);await c.get('x');c.invalidate('x');assert.equal(await c.get('x'),2)});
test('old fulfillment',async()=>{let a=deferred(),b=deferred(),n=0,c=createAsyncCache(()=>++n===1?a.promise:b.promise,100);let old=c.get('x');await tick();c.invalidate('x');let fresh=c.get('x');await tick();b.resolve('new');await fresh;a.resolve('old');assert.equal(await old,'old');assert.equal(await c.get('x'),'new')});
test('old rejection',async()=>{let a=deferred(),b=deferred(),n=0,c=createAsyncCache(()=>++n===1?a.promise:b.promise,100);let old=c.get('x');const observed=old.catch(()=>{});await tick();c.invalidate('x');let fresh=c.get('x');await tick();b.resolve('new');await fresh;a.reject(Error('old'));await observed;assert.equal(await c.get('x'),'new');assert.equal(n,2)});
test('zero ttl',async()=>{let n=0,d=deferred(),c=createAsyncCache(()=>{n++;return n===1?d.promise:n},0,()=>1);let a=c.get('x'),b=c.get('x');await tick();assert.equal(n,1);d.resolve(1);await Promise.all([a,b]);assert.equal(await c.get('x'),2)});
test('undefined cached',async()=>{let n=0,c=createAsyncCache(async()=>{n++;return undefined},100,()=>0);await c.get('x');await c.get('x');assert.equal(n,1)});
(async()=>{let failures=0;for(const [name,fn]of cases){let timer;try{await Promise.race([fn(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('test did not settle within 1 second')),1000)})]);console.log('PASS '+name)}catch(e){failures++;console.log('FAIL '+name+': '+e.message)}finally{clearTimeout(timer)}}console.log(JSON.stringify({tests:cases.length,failures}));process.exitCode=failures?1:0})()
''')]

def chat(url,key,body):
    start=time.monotonic(); first=None; content=[];reasoning=[];calls={};usage={};finish=None
    headers={'Content-Type':'application/json'}
    if key: headers['Authorization']='Bearer '+key
    body={**body,'stream':True,'stream_options':{'include_usage':True}}
    req=urllib.request.Request(url+'/v1/chat/completions',data=json.dumps(body).encode(),headers=headers)
    with urllib.request.urlopen(req,timeout=300) as resp:
        for line in resp:
            if not line.startswith(b'data: '): continue
            raw=line[6:].strip()
            if raw==b'[DONE]':break
            event=json.loads(raw)
            if event.get('usage'):usage=event['usage']
            for choice in event.get('choices',[]):
                delta=choice.get('delta',{})
                if delta.get('content') or delta.get('reasoning_content') or delta.get('tool_calls'):
                    if first is None:first=time.monotonic()-start
                content.append(delta.get('content') or '');reasoning.append(delta.get('reasoning_content') or '')
                for tc in delta.get('tool_calls') or []:
                    obj=calls.setdefault(tc.get('index',0),{'id':'','type':'function','function':{'name':'','arguments':''}})
                    if tc.get('id'):obj['id']=tc['id']
                    for k in ('name','arguments'):obj['function'][k]+=tc.get('function',{}).get(k) or ''
                if choice.get('finish_reason'):finish=choice['finish_reason']
    if finish is None: raise RuntimeError('Stream ended without finish_reason')
    return dict(content=''.join(content),reasoning=''.join(reasoning),tool_calls=list(calls.values()),usage=usage,seconds=time.monotonic()-start,ttft_seconds=first,finish_reason=finish)

def run_code(task,code,path):
    path.mkdir(parents=True,exist_ok=True);(path/task['file']).write_text(code)
    tests='tests.py' if task['language']=='python' else 'tests.js';(path/tests).write_text(task['tests'])
    container_name = 'coding-benchmark-test-' + uuid.uuid4().hex
    cmd=['sudo','-n','docker','run','--rm','--name',container_name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','64','--memory','256m','--cpus','1','--user','65534:65534','--tmpfs','/tmp:rw,noexec,nosuid,size=16m','-v',str(path)+':/work:ro','-w','/work',task['image'],*task['command']]
    try:
        out=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
        output = out.stdout + out.stderr
        completed = 'Ran 10 tests' in output
        if task['language'] == 'javascript':
            completed = False
            for line in output.splitlines():
                try: summary = json.loads(line)
                except json.JSONDecodeError: continue
                if isinstance(summary, dict) and summary.get('tests') == 10 and summary.get('failures') == 0:
                    completed = True
        return dict(passed=out.returncode==0 and completed,returncode=out.returncode,output=output[-8000:])
    except subprocess.TimeoutExpired:return dict(passed=False,error='test timeout')
    finally:
        # Killing the Docker client on timeout does not stop its container.
        subprocess.run(['sudo','-n','docker','rm','-f',container_name],
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=10)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--label',required=True);ap.add_argument('--url',required=True);ap.add_argument('--model',required=True);ap.add_argument('--env-file');ap.add_argument('--only');ap.add_argument('--max-tokens',type=int,default=1024);a=ap.parse_args()
    key=''
    if a.env_file:
        for line in pathlib.Path(a.env_file).read_text().splitlines():
            if line.startswith('KAT_GATEWAY_API_KEY='):key=shlex.split(line.split('=',1)[1])[0]
    if a.label in ('.', '..') or pathlib.Path(a.label).name != a.label:
        ap.error('--label must be one directory name')
    if a.only and a.only not in {task['id'] for task in TASKS}:
        ap.error('--only must name one of the coding tasks')
    outdir=ROOT/'results'/a.label
    if (outdir/'report.json').exists() and not a.only:
        ap.error('report already exists; choose a new label or explicitly rerun a task with --only')
    outdir.mkdir(parents=True,exist_ok=True)
    common=dict(model=a.model,temperature=0,top_p=1,enable_thinking=False,chat_template_kwargs={'enable_thinking':False},max_tokens=a.max_tokens)
    report=dict(protocol='2026-10-07.v1',label=a.label,model=a.model,url=a.url,started=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),settings=common,tasks=[])
    if a.only and (outdir/'report.json').exists(): report=json.loads((outdir/'report.json').read_text())
    def save():(outdir/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    for task in TASKS:
        if a.only and task['id'] != a.only: continue
        print(a.label,task['id'],'starting',flush=True)
        try:
            r=chat(a.url,key,{**common,'messages':[{'role':'system','content':'You are a programming assistant. Return only a complete source file, with no explanation or markdown. Follow the contract exactly.'},{'role':'user','content':task['prompt']}]})
            if r.get('finish_reason') == 'length' and a.max_tokens < 2048:
                initial = r
                r = chat(a.url,key,{**common,'max_tokens':2048,'messages':[{'role':'system','content':'You are a programming assistant. Return only a complete source file, with no explanation or markdown. Follow the contract exactly.'},{'role':'user','content':task['prompt']}]})
                r['max_tokens'] = 2048
                r['initial_truncated_attempt'] = initial
                r['total_attempt_seconds'] = initial['seconds'] + r['seconds']
            code=r['content'].strip();fences=re.findall(r'```(?:python|javascript|js)?\s*\n(.*?)```',code,re.S)
            if fences:code=fences[0]
            r['tests']=run_code(task,code,outdir/task['id']);r['id']=task['id']
        except Exception as e:r=dict(id=task['id'],error=str(e),tests=dict(passed=False))
        report['tasks']=[old for old in report['tasks'] if old['id'] != task['id']];report['tasks'].append(r);save();print(a.label,task['id'],json.dumps({k:r[k] for k in ('seconds','usage','finish_reason') if k in r}),r['tests']['passed'],flush=True)
    if a.only: return
    print(a.label,'tool loop starting',flush=True)
    tool={'type':'function','function':{'name':'read_file','description':'Read a source file','parameters':{'type':'object','properties':{'path':{'type':'string'}},'required':['path']}}}
    messages=[{'role':'user','content':'Read src/settings.py with the read_file tool, then tell me the integer assigned to RETRY_LIMIT. Do not guess.'}]
    try:
        first=chat(a.url,key,{**common,'max_tokens':256,'messages':messages,'tools':[tool],'tool_choice':'required'})
        valid=len(first['tool_calls'])==1 and first['tool_calls'][0]['function']['name']=='read_file' and json.loads(first['tool_calls'][0]['function']['arguments'])=={'path':'src/settings.py'}
        loop={'first':first,'valid_call':valid,'passed':False}
        if valid:
            tc=first['tool_calls'][0];messages.extend([{'role':'assistant','content':first['content'] or None,'tool_calls':first['tool_calls']},{'role':'tool','tool_call_id':tc['id'],'content':'RETRY_LIMIT = 17\n'}])
            second=chat(a.url,key,{**common,'max_tokens':128,'messages':messages,'tools':[tool]});loop.update(second=second,passed=bool(re.search(r'\b17\b',second['content'])) and not second['tool_calls'])
        report['tool_loop']=loop
    except Exception as e:report['tool_loop']={'passed':False,'error':str(e)}
    report['finished']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime());save();print(a.label,'complete',flush=True)
if __name__=='__main__':main()

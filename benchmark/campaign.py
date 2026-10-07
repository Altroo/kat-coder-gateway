import json,os,pathlib,subprocess,time,urllib.request,threading
import benchmark
import fcntl
ROOT=pathlib.Path(__file__).resolve().parent
IMAGE='ghcr.io/ggml-org/llama.cpp@sha256:33868c035b21dc63f7c60b7438774283fd99215bc319114eb03de5df4ce7cd6b'
NAME='colibri-model-comparison'
_lock = (ROOT / '.campaign.lock').open('w')
try:
 fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
 raise SystemExit('Another benchmark campaign is already running')
if os.geteuid() != 0:
 raise SystemExit('Run the campaign with sudo; it manages only the KAT service and benchmark container')
if (ROOT / 'campaign.json').exists() or any((ROOT / 'results').glob('*/report.json')):
 raise SystemExit('Archive campaign.json and results/ into a dated run before starting another campaign')
MODELS=[('tiel','Tiel-Coder-35B-A3B-UD-Q4_K_XL.gguf'),('mimo','MiMo-V2.6-Distill-Qwen-9B-Q8_0.gguf'),('qwen','Qwen3.8-27B-UD-Q4_K_XL.gguf')]
meta={'llama_image':IMAGE,'cpu':subprocess.check_output(['lscpu'],text=True),'kernel':os.uname().release,'runs':[], 'method':'One greedy pass of 3 coding contracts (10 assertions each) plus a two-turn tool loop. Thinking disabled, initial max_tokens=1024 with an unchanged-prompt 2048-token retry only on truncation, 8 CPU threads. Runtime/model stack comparison, quantizations differ. Candidate ctx=8192, production KAT ctx=65536; all actual prompts fit both.'}
(ROOT/'campaign.json').write_text(json.dumps(meta,indent=2))
def ready(url,seconds=180):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  try:
   with urllib.request.urlopen(url+'/health',timeout=2) as r:
    if r.status==200:return
  except Exception: pass
  time.sleep(1)
 raise RuntimeError('server did not become healthy: '+url)
def rss_tree(pid):
 try:
  status=pathlib.Path(f'/proc/{pid}/status').read_text();rss=next(int(x.split()[1]) for x in status.splitlines() if x.startswith('VmRSS:'))
  children=pathlib.Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
  return rss+sum(rss_tree(int(p)) for p in children)
 except Exception:return 0
def run(label,url,model,envfile=None,pid=0):
 ready(url)
 # Identical small warm-up; loading and startup are recorded separately.
 import shlex
 key=''
 if envfile:
  for line in pathlib.Path(envfile).read_text().splitlines():
   if line.startswith('KAT_GATEWAY_API_KEY='):key=shlex.split(line.split('=',1)[1])[0]
 warm=benchmark.chat(url,key,dict(model=model,messages=[{'role':'user','content':'Reply only OK.'}],temperature=0,max_tokens=16,enable_thinking=False,chat_template_kwargs={'enable_thinking':False}))
 peak=[0];halt=threading.Event()
 def monitor():
  while not halt.wait(.5):peak[0]=max(peak[0],rss_tree(pid))
 t=threading.Thread(target=monitor,daemon=True);t.start()
 args=['python3',str(ROOT/'benchmark.py'),'--label',label,'--url',url,'--model',model]
 if envfile:args+=['--env-file',envfile]
 start=time.monotonic()
 try:code=subprocess.call(args)
 finally:halt.set();t.join()
 meta['runs'].append({'label':label,'exit_code':code,'seconds':time.monotonic()-start,'peak_process_rss_mib':round(peak[0]/1024,1),'warmup':{k:v for k,v in warm.items() if k not in ('content','reasoning','tool_calls')}})
 (ROOT/'campaign.json').write_text(json.dumps(meta,indent=2))
 if code:raise RuntimeError('benchmark process failed: '+label)
try:
 pid=int(subprocess.check_output(['systemctl','show','kat-coder-gateway','-p','MainPID','--value'],text=True))
 run('kat','http://127.0.0.1:18080','kat-coder-v2.5-dev-colibri','/opt/kat-coder-gateway/.env.production',pid)
 print('KAT baseline finished; releasing its RAM for candidates',flush=True)
 subprocess.run(['systemctl','stop','kat-coder-gateway'],check=True)
 for label,file in MODELS:
  assert (ROOT/(label+'.verified.json')).exists()
  args=['docker','run','-d','--name',NAME,'--memory','32g','--memory-swap','32g','--cpuset-cpus','0-7','--cpu-shares','256','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--tmpfs','/tmp:rw,nosuid,size=64m','-p','127.0.0.1:18180:18180','-v',str(ROOT)+':/models:ro',IMAGE,'--model','/models/'+file,'--alias',label,'--host','0.0.0.0','--port','18180','--threads','8','--threads-batch','8','--ctx-size','8192','--parallel','1','--n-gpu-layers','0','--batch-size','512','--ubatch-size','128','--reasoning','off','--chat-template-kwargs','{"enable_thinking":false}','--jinja','--no-webui','--offline']
  print('Starting',label,flush=True)
  cid=subprocess.check_output(args,text=True).strip()
  try:
   pid=int(subprocess.check_output(['docker','inspect','--format','{{.State.Pid}}',NAME],text=True))
   run(label,'http://127.0.0.1:18180',label,pid=pid)
  finally:
   with (ROOT/(label+'-server.log')).open('w') as f:subprocess.run(['docker','logs',NAME],stdout=f,stderr=subprocess.STDOUT)
   subprocess.run(['docker','rm','-f',NAME],check=False,stdout=subprocess.DEVNULL)
finally:
 subprocess.run(['docker','rm','-f',NAME],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 subprocess.run(['systemctl','start','kat-coder-gateway'],check=True)
 ready('http://127.0.0.1:18080')
 print('KAT gateway restored and healthy',flush=True)
print('Campaign complete',flush=True)

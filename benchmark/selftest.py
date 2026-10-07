import benchmark
from pathlib import Path
sources=[
'''from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

def invoice_total(lines, discount_percent="0"):
    def number(x):
        try: n=Decimal(x)
        except (InvalidOperation, TypeError, ValueError): raise ValueError("invalid number")
        if not n.is_finite() or n<0: raise ValueError("invalid number")
        return n
    d=number(discount_percent)
    if d>100: raise ValueError("invalid discount")
    total_net=Decimal(0); total_tax=Decimal(0)
    for line in lines:
        try: q,p,v=(number(line[k]) for k in ("quantity","unit_price","vat_percent"))
        except KeyError: raise ValueError("missing field")
        net=(q*p*(1-d/100)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        tax=(net*v/100).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
        total_net+=net; total_tax+=tax
    return dict(net=f"{total_net:.2f}",tax=f"{total_tax:.2f}",total=f"{total_net+total_tax:.2f}")
''',
'''import heapq

def order_tasks(tasks):
    ids=[t['id'] for t in tasks]
    pos={x:i for i,x in enumerate(ids)}
    if len(pos)!=len(ids): raise ValueError('duplicate')
    followers={x:[] for x in ids}; degree={}
    for t in tasks:
        deps=set(t.get('depends_on',[]))
        if t['id'] in deps or any(d not in pos for d in deps): raise ValueError('invalid dependency')
        degree[t['id']]=len(deps)
        for d in deps: followers[d].append(t['id'])
    heap=[pos[x] for x in ids if degree[x]==0]; heapq.heapify(heap); result=[]
    while heap:
        x=ids[heapq.heappop(heap)];result.append(x)
        for y in followers[x]:
            degree[y]-=1
            if degree[y]==0: heapq.heappush(heap,pos[y])
    if len(result)!=len(ids): raise ValueError('cycle')
    return result
''',
'''function createAsyncCache(load,ttlMs,now=Date.now){
 const entries=new Map();
 function get(key){
  const existing=entries.get(key);
  if(existing&&(existing.pending||now()<existing.expiresAt))return existing.promise;
  const entry={pending:true}; entries.set(key,entry);
  entry.promise=Promise.resolve().then(()=>load(key)).then(value=>{
   entry.pending=false;entry.expiresAt=now()+ttlMs;return value;
  },error=>{if(entries.get(key)===entry)entries.delete(key);throw error;});
  return entry.promise;
 }
 return {get,invalidate:key=>entries.delete(key)};
}
module.exports={createAsyncCache};
''']
for task,source in zip(benchmark.TASKS,sources):
    result=benchmark.run_code(task,source,benchmark.ROOT/'selftest'/task['id'])
    print(task['id'],result)
    assert result['passed'],task['id']
print('All 30 benchmark assertions pass with reference implementations.')

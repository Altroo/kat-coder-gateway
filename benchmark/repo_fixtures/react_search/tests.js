const { JSDOM } = require('jsdom');
const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost' });
global.window=dom.window;global.document=dom.window.document;
Object.defineProperty(global,'navigator',{value:dom.window.navigator,configurable:true});
global.HTMLElement=dom.window.HTMLElement;global.IS_REACT_ACT_ENVIRONMENT=true;
const React=require('react');
const {renderHook,render,act,cleanup,screen}=require('@testing-library/react');
const assert=require('node:assert/strict');
const {useArticleSearch}=require('/work/useArticleSearch');
const {ArticleResults}=require('/work/ArticleResults');
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}};
const settle=async(fn=()=>{})=>act(async()=>{fn();await Promise.resolve();await Promise.resolve()});
const cases=[];const test=(n,f)=>cases.push([n,f]);
function setup(q='first',provided){const requests=[];const search=provided||((query,options)=>{const d=deferred();requests.push({query,options,...d});return d.promise});const hook=renderHook(({query,load})=>useArticleSearch(query,load),{initialProps:{query:q,load:search}});return {...hook,requests,search}}
test('empty query',async()=>{const h=setup('  ');await settle();assert.equal(h.requests.length,0);assert.deepEqual(h.result.current,{results:[],loading:false,error:null})});
test('trimmed query and success',async()=>{const h=setup('  steel  ');await settle();assert.equal(h.requests[0].query,'steel');assert.equal(h.result.current.loading,true);await settle(()=>h.requests[0].resolve([{id:1,title:'Steel'}]));assert.equal(h.result.current.results[0].title,'Steel');assert.equal(h.result.current.loading,false)});
test('old success cannot overwrite new',async()=>{const h=setup();await settle();h.rerender({query:'second',load:h.search});await settle();await settle(()=>h.requests[1].resolve([{id:2,title:'new'}]));await settle(()=>h.requests[0].resolve([{id:1,title:'old'}]));assert.equal(h.result.current.results[0].title,'new')});
test('old completion does not clear current loading',async()=>{const h=setup();await settle();h.rerender({query:'second',load:h.search});await settle();await settle(()=>h.requests[0].resolve([]));assert.equal(h.result.current.loading,true);await settle(()=>h.requests[1].resolve([]));assert.equal(h.result.current.loading,false)});
test('old rejection is ignored',async()=>{const h=setup();await settle();h.rerender({query:'second',load:h.search});await settle();await settle(()=>h.requests[1].resolve([{id:2,title:'new'}]));await settle(()=>h.requests[0].reject(Error('old')));assert.equal(h.result.current.error,null);assert.equal(h.result.current.results[0].title,'new')});
test('clear detaches active request',async()=>{const h=setup();await settle();h.rerender({query:'',load:h.search});await settle();assert.equal(h.requests.length,1);assert.deepEqual(h.result.current,{results:[],loading:false,error:null});await settle(()=>h.requests[0].resolve([{id:1,title:'stale'}]));assert.deepEqual(h.result.current,{results:[],loading:false,error:null})});
test('current error and retry reset',async()=>{const h=setup();await settle();await settle(()=>h.requests[0].reject(Error('offline')));assert.equal(h.result.current.error.message,'offline');h.rerender({query:'retry',load:h.search});await settle();assert.equal(h.result.current.error,null);assert.equal(h.result.current.loading,true);await settle(()=>h.requests[1].resolve([]))});
test('search function changes',async()=>{const h=setup();await settle();const d=deferred();let calls=0;const load=()=>{calls++;return d.promise};h.rerender({query:'first',load});await settle();assert.equal(calls,1);await settle(()=>d.resolve([{id:3,title:'replacement'}]));assert.equal(h.result.current.results[0].title,'replacement')});
test('unmount aborts active request',async()=>{const h=setup();await settle();const signal=h.requests[0].options?.signal;assert.ok(signal);assert.equal(signal.aborted,false);h.unmount();assert.equal(signal.aborted,true);await settle(()=>h.requests[0].resolve([]))});
test('component keeps loading error and list states',async()=>{const d=deferred();render(React.createElement(ArticleResults,{query:'x',search:()=>d.promise}));await settle();assert.equal(screen.getByRole('status').textContent,'Loading');await settle(()=>d.resolve([{id:1,title:'Found'}]));assert.equal(screen.getByRole('listitem').textContent,'Found')});
(async()=>{let failures=0;for(const [name,fn]of cases){let timer;try{await Promise.race([fn(),new Promise((_,rej)=>{timer=setTimeout(()=>rej(Error('test timeout')),3000)})]);console.log('PASS '+name)}catch(e){failures++;console.log('FAIL '+name+': '+e.message)}finally{clearTimeout(timer);cleanup()}}console.log(JSON.stringify({tests:cases.length,failures}));process.exitCode=failures?1:0})()

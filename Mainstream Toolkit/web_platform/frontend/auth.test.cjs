const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/xverse-auth.js','utf8').replace("import { request } from '@sats-connect/core';",'');
function app(walletResponses, merge=false, conflict=false) {
 let submit; const calls=[]; const requests=[]; const button={disabled:false}; const status={}; const redirects=[];
 const link={hidden:true};
 const form={dataset:{challengeUrl:'/challenge/',verifyUrl:'/verify/', ...(merge?{mergeAttempt:'attempt-one'}:{})},querySelector:s=>s==='button'?button:s==='[name=csrfmiddlewaretoken]'?{value:'csrf'}:s==='[name=merge_slot]'&&merge?{value:'other'}:null,addEventListener:(event,fn)=>submit=fn};
 vm.runInNewContext(source,{document:{getElementById:id=>id==='xverse-auth'?form:id==='xverse-merge-link'?link:status},URLSearchParams,
  fetch:async(url,options)=>{requests.push({url,options});return {ok:!(conflict&&url==='/verify/'),json:async()=>url==='/challenge/'?{id:'one',message:'Bound challenge',protocol:'ECDSA'}:conflict?{error:'Already linked',merge_url:'/account/merge/'}:{redirect:merge?'/account/merge/':'/account/'}};},
  request:async(method,args)=>{calls.push({method,args});return walletResponses.shift();},window:{location:{assign:url=>redirects.push(url)}}});
 return {submit:()=>submit({preventDefault(){}}),calls,requests,button,status,redirects,link};
}
test('wallet login requires server challenge and signed proof before redirect',async()=>{
 const a=app([{status:'success',result:{addresses:[{purpose:'payment',address:'3wallet'}]}},{status:'success',result:{signature:'proof'}}]);
 await a.submit();assert.deepEqual(a.calls.map(c=>c.method),['wallet_connect','signMessage']);
 assert.equal(a.calls[1].args.message,'Bound challenge');assert.equal(a.calls[1].args.protocol,'ECDSA');
 assert.equal(a.requests[1].options.body.get('signature'),'proof');assert.equal(a.requests[1].options.headers['X-CSRFToken'],'csrf');
 assert.deepEqual(a.redirects,['/account/']);
});
test('wallet rejection creates no session and sends no verification',async()=>{
 const a=app([{status:'success',result:{addresses:[{purpose:'payment',address:'3wallet'}]}},{status:'error'}]);
 await a.submit();assert.equal(a.requests.length,1);assert.equal(a.redirects.length,0);assert.equal(a.button.disabled,false);
});
test('declined connection never requests a challenge or a signature',async()=>{
 const a=app([{status:'error'}]);await a.submit();assert.equal(a.calls.length,1);assert.equal(a.requests.length,0);
});

test('merge wallet proof binds the attempt and slot without transferring funds',async()=>{
 const a=app([{status:'success',result:{addresses:[{purpose:'payment',address:'3wallet'}]}},{status:'success',result:{signature:'proof'}}],true);
 await a.submit();assert.equal(a.requests[0].options.body.get('merge_attempt'),'attempt-one');assert.equal(a.requests[0].options.body.get('merge_slot'),'other');
 assert.deepEqual(a.redirects,['/account/merge/']);assert.deepEqual(a.calls.map(c=>c.method),['wallet_connect','signMessage']);
});
test('wallet conflict reveals merge action and keeps the current session',async()=>{
 const a=app([{status:'success',result:{addresses:[{purpose:'payment',address:'3wallet'}]}},{status:'success',result:{signature:'proof'}}],false,true);
 await a.submit();assert.equal(a.link.hidden,false);assert.deepEqual(a.redirects,[]);assert.equal(a.status.textContent,'Already linked');
});

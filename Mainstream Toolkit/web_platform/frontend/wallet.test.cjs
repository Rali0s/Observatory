const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/xverse-payment.js','utf8').replace("import { request } from '@sats-connect/core';",'');
function setup(responses,expires=new Date(Date.now()+60000).toISOString()){
 const calls=[];let click;const button={disabled:false,addEventListener:(name,fn)=>click=fn};const status={textContent:''};
 const payment={textContent:JSON.stringify({address:'bc1q-example',sats:30000,expires,paid:false})};
 vm.runInNewContext(source,{document:{getElementById:id=>({'pay-xverse':button,'wallet-status':status,'bitcoin-payment':payment}[id])},Date,
 request:async(method,args)=>{calls.push({method,args});return responses.shift();}});
 return {click,button,status,calls};
}
test('connects mainnet payment address then asks for exact sats; never auto-credits',async()=>{const app=setup([{status:'success'},{status:'success',result:{txid:'abc'}}]);await app.click();assert.equal(app.calls[0].method,'wallet_connect');assert.equal(app.calls[0].args.network,'Mainnet');assert.equal(app.calls[1].method,'sendTransfer');assert.equal(app.calls[1].args.recipients[0].amount,30000);assert.match(app.status.textContent,/Transaction broadcast/);assert.equal(app.button.disabled,true);});
test('cancellation never sends a transfer',async()=>{const app=setup([{status:'error'}]);await app.click();assert.equal(app.calls.length,1);assert.match(app.status.textContent,/cancelled/);});
test('expired quote never connects a wallet',async()=>{const app=setup([],new Date(0).toISOString());await app.click();assert.equal(app.calls.length,0);assert.match(app.status.textContent,/no longer payable/);});

test('ambiguous transfer failure blocks automatic retry',async()=>{const app=setup([{status:'success'},{status:'error',error:{code:-32603}}]);await app.click();await app.click();assert.equal(app.calls.length,2);assert.equal(app.button.disabled,true);});
test('explicit wallet rejection allows retry',async()=>{const app=setup([{status:'success'},{status:'error',error:{code:-32000}}]);await app.click();assert.equal(app.button.disabled,false);});
test('connect-only page never requests a transfer',async()=>{
 const connectSource=fs.readFileSync(__dirname+'/xverse-connect.js','utf8').replace("import { request } from '@sats-connect/core';",'');let click;const calls=[];const els={'connect-xverse':{addEventListener:(name,fn)=>click=fn},'connect-status':{},'connected-wallet':{hidden:true},'connected-address':{}};
 vm.runInNewContext(connectSource,{document:{getElementById:id=>els[id]},request:async(method)=>{calls.push(method);return {status:'success',result:{addresses:[{purpose:'payment',address:'bc1q-example'}]}};}});
 await click();assert.deepEqual(calls,['wallet_connect']);assert.equal(els['connected-address'].value,'bc1q-example');assert.equal(els['connected-wallet'].hidden,false);
});

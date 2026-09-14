const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/xverse-ordinal.js','utf8').replace("import { createInscription } from '@sats-connect/core';",'');
function setup(outcome,blocked=false){
 let click;const calls=[];let walletCalls=0;let reloads=0;
 const button={disabled:false,addEventListener:(_,fn)=>click=fn};const status={textContent:''};
 const form={dataset:{url:'/ordinal/wallet/'},querySelector:()=>({value:'csrf'})};
 vm.runInNewContext(source,{URLSearchParams,document:{getElementById:id=>({'ordinal-wallet-form':form,'mint-xverse':button,'ordinal-wallet-status':status}[id])},
 window:{location:{reload:()=>reloads++}},fetch:async(url,options)=>{calls.push(options.body.get('action'));return {ok:!blocked,json:async()=>blocked?{error:'Paused'}:{content:'exact frozen edition',contentType:'text/html',payloadType:'PLAIN_TEXT'}};},
 createInscription:async options=>{walletCalls++;assert.equal(options.payload.network.type,'Mainnet');assert.equal(options.payload.content,'exact frozen edition');if(outcome==='finish')await options.onFinish({txId:'a'.repeat(64)});else if(outcome==='cancel')options.onCancel();else throw Error('Interrupted');}});
 return {click,button,status,calls,walletCalls:()=>walletCalls,reloads:()=>reloads};
}
test('mint asks for frozen mainnet content and only records broadcast',async()=>{const app=setup('finish');await app.click();assert.deepEqual(app.calls,['begin','broadcast']);assert.equal(app.reloads(),1);assert.equal(app.button.disabled,true);});
test('SDK cancellation is ambiguous and never resets the attempt',async()=>{const app=setup('cancel');await app.click();assert.deepEqual(app.calls,['begin']);assert.equal(app.button.disabled,true);assert.match(app.status.textContent,/automatic retry is disabled/);});
test('wallet transport failure remains blocked',async()=>{const app=setup('error');await app.click();assert.equal(app.button.disabled,true);assert.deepEqual(app.calls,['begin']);});
test('server kill switch prevents wallet call',async()=>{const app=setup('finish',true);await app.click();assert.equal(app.walletCalls(),0);});

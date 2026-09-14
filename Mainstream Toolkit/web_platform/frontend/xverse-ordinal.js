import { createInscription } from '@sats-connect/core';
const form=document.getElementById('ordinal-wallet-form');
if(form){
 const button=document.getElementById('mint-xverse');
 const status=document.getElementById('ordinal-wallet-status');
 async function send(action,extra={}){
  const response=await fetch(form.dataset.url,{method:'POST',headers:{'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value},body:new URLSearchParams({action,...extra})});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Unable to update mint status.');return data;
 }
 button.addEventListener('click',async()=>{
  button.disabled=true;status.textContent='Preparing your frozen edition…';
  try{
   const payload=await send('begin',{quote:form.dataset.quote||''});
   status.textContent='Review the Bitcoin fee and edition in Xverse.';
   await createInscription({payload:{network:{type:'Mainnet'},...payload},
    onFinish:async result=>{
     status.textContent='Wallet broadcast reported. Checking is still required; do not mint again.';
     try{await send('broadcast',{txid:result.txId});window.location.reload();}
     catch{status.textContent='The wallet may have broadcast. Keep the transaction ID in Xverse, refresh this page, and track the inscription once revealed. Do not mint again.';}
    },
    onCancel:()=>{
     // This SDK also invokes onCancel for transport errors after a possible broadcast.
     status.textContent='Xverse closed or the request was interrupted. Check your wallet before continuing. Refresh to track an inscription; automatic retry is disabled to prevent duplicate fees.';
    }});
  }catch(error){status.textContent=(error.message||'Wallet request interrupted.')+' Check Xverse and refresh this page before continuing. No edition has been marked as minted.';}
 });
}

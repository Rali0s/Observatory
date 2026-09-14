import { request, signTransaction } from '@sats-connect/core';
const status = document.getElementById('market-status');
async function post(form, data) {
 const response = await fetch(form.dataset.url, {method:'POST', credentials:'same-origin',
  headers:{'X-CSRFToken':form.querySelector('[name=csrfmiddlewaretoken]').value}, body:new URLSearchParams(data)});
 const result = await response.json();
 if (!response.ok) throw Error(result.error || 'The request could not be confirmed. Check this page before retrying.');
 return result;
}
async function wallet() {
 const result = await request('wallet_connect', {addresses:['payment','ordinals'], network:'Mainnet', message:'Connect to trade an Observatory ordinal edition.'});
 if(result.status !== 'success') throw Error('Wallet connection was declined or unavailable.');
 const payment = result.result.addresses.find(a=>a.purpose==='payment');
 const ordinal = result.result.addresses.find(a=>a.purpose==='ordinals');
 if(!payment || !ordinal) throw Error('Xverse must return both payment and ordinal addresses.');
 return {payment,ordinal};
}
async function signSale(form, listing) {
 status.textContent='Review the sale price in Xverse. Signing allows a buyer to purchase at this price.';
 // The legacy API exposes the explicit signature mode required for an ordinal offer.
 const signed = await new Promise((resolve,reject)=>signTransaction({payload:{network:{type:'Mainnet'},
  psbtBase64:listing.psbt, broadcast:false, inputsToSign:[{address:listing.address,signingIndexes:[0],sigHash:131}],
  message:'Authorize the sale of this Observatory edition at the listed price.'},
  onFinish:resolve, onCancel:()=>reject(Error('Listing signature was not returned. The draft is saved; resume or delist it.'))}));
 await post(form,{action:'activate',listing_id:listing.id,psbt:signed.psbtBase64});
 window.location.reload();
}
function bind(form, handler) {
 if(!form) return;
 form.addEventListener('submit',async event=>{
  event.preventDefault();
  if(form.dataset.busy) return;
  form.dataset.busy='1';
  const buttons=[...form.querySelectorAll('button')]; buttons.forEach(b=>b.disabled=true);
  try {await handler(event);} catch(error) {status.textContent=error.message || 'Xverse is unavailable.';}
  finally {delete form.dataset.busy;buttons.forEach(b=>b.disabled=false);}
 });
}
const listingForm=document.getElementById('market-listing');
bind(listingForm,async()=>{
 const {payment}=await wallet();
 const listing=await post(listingForm,{action:'prepare',price_sats:listingForm.elements.price_sats.value,payout_address:payment.address});
 await signSale(listingForm,listing);
});
for(const form of document.querySelectorAll('.market-action')) bind(form,async event=>{
 const action=event.submitter.value;
 const result=await post(form,{action,listing_id:form.elements.listing_id.value});
 if(action==='resume') await signSale(form,result); else window.location.reload();
});
const purchase=document.getElementById('market-purchase');
bind(purchase,async()=>{
 const {payment,ordinal}=await wallet();
 status.textContent='Checking ownership and funding outputs. No payment has been requested.';
 const result=await post(purchase,{payment_address:payment.address,payment_public_key:payment.publicKey,
  receive_address:ordinal.address,fee_sats:purchase.elements.fee_sats.value});
 window.location.assign(result.redirect);
});
const trade=document.getElementById('market-trade');
bind(trade,async event=>{
 const action=event.submitter.value;
 let signedPsbt='';
 if(action==='submit' && JSON.parse(document.getElementById('trade-broadcast-started').textContent)==='false') {
  await wallet();
  const signed=await request('signPsbt',{psbt:JSON.parse(document.getElementById('trade-psbt').textContent),
   signInputs:{[trade.dataset.paymentAddress]:JSON.parse(document.getElementById('trade-indexes').textContent)},broadcast:false});
  if(signed.status!=='success') throw Error('The purchase was not signed. Check Xverse before trying again.');
  signedPsbt=signed.result.psbt;
 }
 status.textContent=action==='submit'?'Submitting your exact approved transaction…':'Checking purchase…';
 try {
  await post(trade,{action,psbt:signedPsbt});window.location.reload();
 } catch(error) {
  // Reload on the next action after uncertainty; the server may have recorded a broadcast.
  if(action==='submit') {document.getElementById('trade-broadcast-started').textContent=JSON.stringify('true');}
  throw error;
 }
});

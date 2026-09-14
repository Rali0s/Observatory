import { request } from '@sats-connect/core';
const builder=document.getElementById('mint-builder');
const fees=document.getElementById('mint-fees');
const token=()=>document.querySelector('[name=csrfmiddlewaretoken]')?.value;
async function post(url,data){
 const response=await fetch(url,{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':token()},body:new URLSearchParams(data)});
 const result=await response.json();
 if(!response.ok){if(result.merge_url==='/account/merge/')document.getElementById('rare-merge-link')?.removeAttribute('hidden');throw Error(result.error||'The request could not be completed.');}
 return result;
}
if(builder){
 const rows=document.getElementById('trait-rows');
 rows.addEventListener('click',event=>{if(event.target.classList.contains('remove-trait')){event.target.closest('.trait-row').remove();document.getElementById('edition-form').dispatchEvent(new Event('input',{bubbles:true}));}});
 document.getElementById('add-trait').addEventListener('click',()=>{
  if(rows.children.length>=17){document.getElementById('trait-status').textContent='You can add up to 17 extra traits.';return;}
  const row=document.createElement('div');row.className='trait-row';
  row.innerHTML='<label>Trait name<input name="trait_name" maxlength="60" placeholder="e.g. Series"></label><label>Value<input name="trait_value" maxlength="240" placeholder="e.g. The Quiet Hours"></label><button type="button" class="quiet remove-trait" aria-label="Remove trait">Remove</button>';
  rows.append(row);row.querySelector('input').focus();
 });
 function mode(){const special=builder.querySelector('[name=sat_mode]:checked')?.value==='special';document.getElementById('special-sat-fields').hidden=!special;document.getElementById('regular-sat-note').hidden=special;document.getElementById('id_sat_choice').disabled=!special;}
 builder.querySelectorAll('[name=sat_mode]').forEach(input=>input.addEventListener('change',mode));mode();
 const address=document.getElementById('rare-wallet'),status=document.getElementById('rare-status'),select=document.getElementById('id_sat_choice'),more=document.getElementById('more-rare-sats');
 let next=0,loading=false,generation=0;
 address.addEventListener('change',()=>{generation++;select.replaceChildren(new Option('Load this wallet to choose a sat',''));more.hidden=true;status.textContent='Load this wallet’s rare sats.';});
 async function scan(append=false){
  if(loading)return;if(!address.value){status.textContent='Choose a linked wallet or connect Xverse first.';return;}
  loading=true;const scanGeneration=generation;status.textContent='Checking confirmed wallet outputs…';
  try{
   const url=new URL(builder.dataset.inventoryUrl,window.location.origin);url.searchParams.set('address',address.value);url.searchParams.set('page',append?next:0);
   const response=await fetch(url,{credentials:'same-origin'}),data=await response.json();if(!response.ok)throw Error(data.error);
   if(scanGeneration!==generation)return;
   if(!append)select.replaceChildren(new Option('Choose an available sat',''));
   for(const sat of data.items)select.add(new Option(sat.label,sat.token));
   next=data.next_page;more.hidden=next===null;
   const count=select.options.length-1;
   status.textContent=`${count} selectable ${count===1?'sat':'sats'} loaded. ${data.scanned} ${data.scanned===1?'output':'outputs'} checked on this page. ${data.excluded_outputs} bundles with other assets excluded.${data.truncated?' This page contains more sats than can be listed; use Gamma to inspect the full bundle.':''}${count===0?' No eligible rare sats found on this page.':''}`;
  }catch(error){if(scanGeneration===generation)status.textContent=error.message||'Sat lookup is unavailable. Try again.';}
  finally{loading=false;}
 }
 document.getElementById('load-rare-sats').addEventListener('click',()=>scan());more.addEventListener('click',()=>scan(true));
 const connect=document.getElementById('connect-rare-wallet');
 connect.addEventListener('click',async()=>{
  connect.disabled=true;
  try{
   status.textContent='Choose the Ordinals address in Xverse.';
   const connected=await request('wallet_connect',{addresses:['ordinals'],network:'Mainnet',message:'Connect your Ordinals address to discover rare sats.'});
   if(connected.status!=='success')throw Error('Wallet connection was declined or unavailable.');
   const chosen=connected.result?.addresses?.find(item=>item.purpose==='ordinals')?.address;if(!chosen)throw Error('Xverse did not return an Ordinals address.');
   const challenge=await post(builder.dataset.challengeUrl,{address:chosen});
   status.textContent='Verify ownership in Xverse. No sats will move.';
   const signed=await request('signMessage',{address:chosen,message:challenge.message,protocol:challenge.protocol});
   if(signed.status!=='success')throw Error('Wallet verification was declined.');
   const verified=await post(builder.dataset.verifyUrl,{challenge_id:challenge.id,signature:signed.result.signature});
   if(verified.csrf_token)document.querySelectorAll('[name=csrfmiddlewaretoken]').forEach(input=>{input.value=verified.csrf_token;});
   if(!Array.from(address.options).some(option=>option.value===chosen))address.add(new Option(chosen,chosen));
   address.value=chosen;address.dispatchEvent(new Event('change'));await scan();
  }catch(error){status.textContent=error.message||'Xverse is unavailable.';}finally{connect.disabled=false;}
 });
}
if(fees){
 const speed=document.getElementById('fee-speed'),custom=document.getElementById('fee-rate'),status=document.getElementById('mint-fee-status'),estimateButton=document.getElementById('estimate-mint-fee');
 const mintButton=document.getElementById('mint-xverse'),walletForm=document.getElementById('ordinal-wallet-form');let version=0,expiry;
 function invalidate(){version++;clearTimeout(expiry);if(walletForm)walletForm.dataset.quote='';if(mintButton)mintButton.disabled=true;status.textContent='Calculate fees again after changing the edition or fee rate.';document.getElementById('mint-fee-breakdown').hidden=true;}
 speed.addEventListener('change',()=>{document.getElementById('custom-fee-field').hidden=speed.value!=='custom';invalidate();});custom.addEventListener('input',invalidate);
 document.getElementById('edition-form')?.addEventListener('input',event=>{if(event.target.name!=='consent')invalidate();});
 estimateButton.addEventListener('click',async()=>{
  if(estimateButton.disabled)return;invalidate();estimateButton.disabled=true;const current=version;status.textContent='Calculating the edition size and current miner fees…';
  try{
   const editionForm=document.getElementById('edition-form');const data=editionForm?new URLSearchParams(new FormData(editionForm)):new URLSearchParams();data.set('speed',speed.value);data.set('fee_rate',custom.value);
   const quote=await post(fees.dataset.url,data);if(current!==version)return;
   const sats=value=>`${Number(value).toLocaleString()} sats`;
   document.getElementById('fee-content-size').textContent=`${quote.content_bytes.toLocaleString()} bytes`;
   document.getElementById('fee-miners').textContent=`${sats(quote.miner_min)} – ${sats(quote.miner_max)}`;
   document.getElementById('fee-postage').textContent=sats(quote.postage_estimate);
   document.getElementById('fee-platform').textContent=sats(quote.platform_fee);
   document.getElementById('fee-subtotal').textContent=`${sats(quote.subtotal_min)} – ${sats(quote.subtotal_max)}`;
   document.getElementById('fee-platform-address').textContent=quote.platform_fee?`Platform fee recipient: ${quote.platform_address}`:'';
   document.getElementById('mint-fee-breakdown').hidden=false;status.textContent=`Estimated at ${quote.fee_rate} sats/vB. Final fees are confirmed in your wallet.`;
   if(walletForm&&quote.quote){walletForm.dataset.quote=quote.quote;if(mintButton)mintButton.disabled=false;expiry=setTimeout(invalidate,300000);}
  }catch(error){status.textContent=error.message||'Fee estimates are unavailable.';if(walletForm)walletForm.dataset.quote='';if(mintButton)mintButton.disabled=true;}finally{estimateButton.disabled=false;}
 });
}

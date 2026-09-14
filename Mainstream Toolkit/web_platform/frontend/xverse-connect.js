import { request } from '@sats-connect/core';
const button=document.getElementById('connect-xverse');
if(button)button.addEventListener('click',async()=>{
 const status=document.getElementById('connect-status');button.disabled=true;
 try{
  const response=await request('wallet_connect',{addresses:['payment'],network:'Mainnet',message:'Connect your payment wallet to The Observatory. No payment is requested.'});
  if(response.status!=='success')throw Error('Connection was declined or unavailable. You can try again when ready.');
  const address=response.result?.addresses?.find(item=>item.purpose==='payment')?.address;
  if(!address)throw Error('Xverse did not return a Bitcoin payment address. Check the selected wallet account.');
  document.getElementById('connected-address').value=address;
  document.getElementById('connected-wallet').hidden=false;
  status.textContent='Xverse connected. No payment was requested.';button.textContent='Reconnect Xverse';
 }catch(error){status.textContent=error.message||'Xverse is unavailable in this browser.';document.getElementById('connected-wallet').hidden=true;}
 finally{button.disabled=false;}
});

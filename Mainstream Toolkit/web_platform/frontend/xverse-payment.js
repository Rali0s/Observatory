import { request } from '@sats-connect/core';
const button=document.getElementById('pay-xverse'),status=document.getElementById('wallet-status');
if(button){const payment=JSON.parse(document.getElementById('bitcoin-payment').textContent);
 const key='observatory-payment-attempt:'+payment.address;let attempted=false;
 try{attempted=!!sessionStorage.getItem(key);}catch{}
 if(attempted){button.disabled=true;status.textContent='A payment was already attempted in this tab. Check the blockchain status and your wallet history before sending again.';}
 button.addEventListener('click',async()=>{
 if(attempted)return;
 if(Date.now()>=Date.parse(payment.expires)||payment.paid){status.textContent='This quote is no longer payable. Refresh the page.';return;}
 button.disabled=true;
 try{const connected=await request('wallet_connect',{addresses:['payment'],network:'Mainnet',message:'Connect to pay The Observatory publishing membership.'});
 if(connected.status!=='success')throw Error('Wallet connection was cancelled or unavailable.');
 if(Date.now()>=Date.parse(payment.expires))throw Error('Quote expired while connecting. Request a fresh quote.');
 attempted=true;try{sessionStorage.setItem(key,'pending');}catch{}
 const response=await request('sendTransfer',{recipients:[{address:payment.address,amount:payment.sats}]});
 if(response.status==='success'){status.textContent='Transaction broadcast. Use “Check blockchain payment” to follow confirmation. Please do not send a second payment.';}
 else{if(response.error?.code===-32000){attempted=false;try{sessionStorage.removeItem(key);}catch{}}throw Error('Payment was not confirmed by the wallet. Check your wallet history before retrying.');}
 }catch(e){status.textContent=e.message||'Wallet unavailable. You can pay using the address and exact sats shown above.';button.disabled=attempted;}
});}

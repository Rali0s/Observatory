import { request } from '@sats-connect/core';
const form = document.getElementById('xverse-auth');
if (form) {
 const button = form.querySelector('button');
 const status = document.getElementById('xverse-auth-status');
 const post = async (url, data) => {
  const response = await fetch(url, {method: 'POST', credentials: 'same-origin',
   headers: {'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value},
   body: new URLSearchParams(data)});
  const result = await response.json();
  if (!response.ok) throw Error(result.error || 'Sign-in is unavailable. Please try again.');
  return result;
 };
 form.addEventListener('submit', async event => {
  event.preventDefault();
  if (button.disabled) return;
  button.disabled = true;
  try {
   status.textContent = form.dataset.purpose === 'ordinals' ? 'Choose your ordinal wallet in Xverse.' : 'Choose your payment wallet in Xverse.';
   const connected = await request('wallet_connect', {addresses: [form.dataset.purpose || 'payment'], network: 'Mainnet',
    message: 'Use your payment address to sign in to The Observatory.'});
   if (connected.status !== 'success') throw Error('Wallet connection was declined or unavailable.');
   const address = connected.result?.addresses?.find(item => item.purpose === (form.dataset.purpose || 'payment'))?.address;
   if (!address) throw Error('Xverse did not return a payment address.');
   const challenge = await post(form.dataset.challengeUrl, {address});
   status.textContent = 'Approve the sign-in message in Xverse. No payment is requested.';
   const signed = await request('signMessage', {address, message: challenge.message, protocol: challenge.protocol});
   if (signed.status !== 'success') throw Error('Message signing was declined or unavailable.');
   const result = await post(form.dataset.verifyUrl, {challenge_id: challenge.id, signature: signed.result.signature});
   window.location.assign(result.redirect);
  } catch (error) {
   status.textContent = error.message || 'Xverse is unavailable in this browser.';
   button.disabled = false;
  }
 });
}

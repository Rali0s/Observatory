(() => {
 'use strict';
 const phone=window.matchMedia('(max-width: 767px)');
 const filters=document.querySelector('.reading-filters');
 function setFilters(){if(filters) filters.open=!phone.matches||filters.hasAttribute('data-filter-active');}
 setFilters();phone.addEventListener('change',setFilters);
 if(phone.matches) {
  const next=document.querySelector('[data-mobile-login-default]');
  if(next) next.value='/';
 }
 const input=document.querySelector('#invite-entry [name=code]');
 if(input&&window.location.hash) {
  const code=new URLSearchParams(window.location.hash.slice(1)).get('code');
  if(code&&/^OBS-[A-F0-9]{32}$/i.test(code)) {
   input.value=code.toUpperCase();
   // Keep bearer codes out of the address bar and subsequent copied URLs.
   window.history.replaceState(null,'',window.location.pathname+window.location.search);
  }
 }
})();

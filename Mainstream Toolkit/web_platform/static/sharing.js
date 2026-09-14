(() => {
  'use strict';
  if (navigator.clipboard?.writeText) document.querySelectorAll('[data-copy-share]').forEach(button => { button.hidden = false; });
  if (navigator.share) document.querySelectorAll('[data-native-share]').forEach(button => { button.hidden = false; });
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-copy-share], [data-native-share]');
    if (!button) return;
    const status = button.closest('.social-share').querySelector('.share-status');
    try {
      if (button.dataset.copyShare) {
        await navigator.clipboard.writeText(button.dataset.copyShare);
        status.textContent = 'Link copied.';
      } else {
        await navigator.share({ title: button.dataset.shareTitle, url: button.dataset.nativeShare });
        status.textContent = '';
      }
    } catch (error) {
      if (error.name !== 'AbortError') status.textContent = 'Sharing is unavailable here. Use one of the social links.';
    }
  });
})();

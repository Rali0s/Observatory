(() => {
  const card = document.querySelector('[data-membership-stage]');
  if (!card) return;
  async function refresh() {
    if (document.hidden) return;
    try {
      const response = await fetch(card.dataset.statusUrl, {credentials: 'same-origin', cache: 'no-store'});
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) return;
      const state = await response.json();
      if (state.stage !== card.dataset.membershipStage) { location.reload(); return; }
      for (const [selector, value] of [['[data-blocks-remaining]', state.remaining], ['[data-estimated-days]', state.days], ['[data-block-height]', state.height]]) {
        const element = card.querySelector(selector);
        if (element && value !== null) element.textContent = String(value);
      }
    } catch (_) { /* Never invent a block height or change access in the browser. */ }
  }
  setInterval(refresh, 60000);
})();

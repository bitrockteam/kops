(() => {
  const body = document.body;
  const revisionSelect = document.querySelector('#revision-source');
  const revisionForm = document.querySelector('#revision-form');
  if (revisionSelect && revisionForm) {
    const updateAction = () => { revisionForm.action = `/sources/${revisionSelect.value}/revise`; };
    revisionSelect.addEventListener('change', updateAction);
    updateAction();
  }

  if (body.dataset.stage !== 'compile') return;
  const timeline = document.querySelector('#timeline');
  const refresh = async () => {
    try {
      const response = await fetch('/api/state', { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) return;
      const state = await response.json();
      if (timeline && state.events.length) {
        timeline.innerHTML = state.events.map((event) =>
          `<li><b>${escapeHtml(event.state)}</b> ${escapeHtml(event.detail)} <time>${escapeHtml(event.created_at)}</time></li>`
        ).join('');
      }
    } catch (_) {
      // Keep the last authoritative state on screen after a connection loss.
    }
  };
  const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
  refresh();
  window.setInterval(refresh, 3000);
})();

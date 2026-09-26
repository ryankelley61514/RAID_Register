(() => {
  const key = 'project-ledger-theme';
  const root = document.documentElement;
  let theme = 'dark';
  try {
    if (localStorage.getItem(key) === 'light') theme = 'light';
  } catch (_) {
    // The toggle still works when browser storage is unavailable.
  }
  root.dataset.theme = theme;

  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('theme-toggle');
    function updateLabel() {
      const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
      toggle.textContent = `${next === 'light' ? 'Light' : 'Dark'} mode`;
      toggle.setAttribute('aria-label', `Switch to ${next} mode`);
    }
    updateLabel();
    toggle.addEventListener('click', () => {
      root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(key, root.dataset.theme);
      } catch (_) {
        // Keep the selected theme for this page even without storage.
      }
      updateLabel();
    });
  });
})();

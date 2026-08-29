(() => {
  const toggle = document.getElementById('mobile-nav-toggle');
  const panel = document.getElementById('mobile-nav-panel');
  if (!toggle || !panel) return;

  const closeMenu = () => {
    panel.classList.add('hidden');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.dataset.open = 'false';
  };

  const openMenu = () => {
    panel.classList.remove('hidden');
    toggle.setAttribute('aria-expanded', 'true');
    toggle.dataset.open = 'true';
  };

  toggle.addEventListener('click', () => {
    const isOpen = toggle.getAttribute('aria-expanded') === 'true';
    if (isOpen) closeMenu(); else openMenu();
  });

  document.addEventListener('click', (event) => {
    if (toggle.getAttribute('aria-expanded') !== 'true') return;
    if (!panel.contains(event.target) && !toggle.contains(event.target)) {
      closeMenu();
    }
  });
})();

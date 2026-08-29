(() => {
  const toggle = document.getElementById('filters-toggle');
  const close = document.getElementById('filters-close');
  const backdrop = document.getElementById('filters-backdrop');
  const panel = document.getElementById('filters-panel');
  if (!toggle || !panel || !backdrop) return;

  const openDrawer = () => {
    panel.classList.remove('translate-x-full');
    backdrop.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  };

  const closeDrawer = () => {
    panel.classList.add('translate-x-full');
    backdrop.classList.add('hidden');
    document.body.style.overflow = '';
  };

  toggle.addEventListener('click', openDrawer);
  close?.addEventListener('click', closeDrawer);
  backdrop.addEventListener('click', closeDrawer);
})();

(() => {
  // Partager : feuille de partage native si disponible, sinon copie du lien.
  document.querySelectorAll('.js-share').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const data = { title: document.title, url: window.location.href };
      if (navigator.share) {
        try { await navigator.share(data); } catch (e) { /* partage annulé */ }
        return;
      }
      try {
        await navigator.clipboard.writeText(data.url);
        const label = btn.querySelector('.js-share-label');
        if (label) {
          const original = label.textContent;
          label.textContent = 'Lien copié';
          setTimeout(() => { label.textContent = original; }, 2000);
        }
      } catch (e) { window.prompt('Copiez le lien de cette annonce :', data.url); }
    });
  });

  // Description repliable.
  const description = document.getElementById('vehicle-description');
  const toggle = document.getElementById('vehicle-description-toggle');
  if (description && toggle) {
    if (description.scrollHeight <= description.clientHeight + 4) {
      toggle.parentElement.remove();
      description.classList.remove('max-h-48');
      const fade = document.getElementById('vehicle-description-fade');
      if (fade) fade.remove();
    } else {
      toggle.addEventListener('click', () => {
        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        description.classList.toggle('max-h-48', expanded);
        const fade = document.getElementById('vehicle-description-fade');
        if (fade) fade.classList.toggle('hidden', !expanded);
        toggle.setAttribute('aria-expanded', String(!expanded));
        toggle.querySelector('.js-toggle-label').textContent = expanded ? 'Voir plus' : 'Voir moins';
        toggle.querySelector('.material-symbols-outlined').textContent = expanded ? 'expand_more' : 'expand_less';
      });
    }
  }

  // Barre compacte : visible dès que le bloc d'action principal sort de l'écran.
  const bar = document.getElementById('detail-sticky-bar');
  const anchor = document.getElementById('detail-cta');
  if (bar && anchor && 'IntersectionObserver' in window) {
    new IntersectionObserver(([entry]) => {
      const hidden = entry.isIntersecting || entry.boundingClientRect.top > 0;
      bar.classList.toggle('-translate-y-full', hidden);
      bar.classList.toggle('opacity-0', hidden);
      bar.setAttribute('aria-hidden', String(hidden));
    }).observe(anchor);
  }
})();

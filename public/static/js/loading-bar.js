(function () {
  // Barre de progression en haut de page — visible pendant les requêtes HTMX
  // (filtres catalogue, favoris, comparateur…). Une vraie navigation complète
  // (clic sur un lien classique) remplace le document du navigateur dès que
  // la navigation démarre, avant même de recevoir la réponse : aucun script
  // ne peut donc garder cette barre visible pendant ce type de chargement —
  // le navigateur affiche son propre indicateur natif dans l'onglet.
  var bar = document.createElement('div');
  bar.id = 'djona-loading-bar';
  bar.setAttribute('aria-hidden', 'true');
  document.body.appendChild(bar);

  var style = document.createElement('style');
  style.textContent = [
    '#djona-loading-bar {',
    '  position: fixed; top: 0; left: 0; height: 3px; width: 0%;',
    '  background: linear-gradient(90deg, #865300, #fea520);',
    '  z-index: 9999; transition: width .3s ease, opacity .3s ease;',
    '  opacity: 0; pointer-events: none;',
    '}',
    '#djona-loading-bar.is-active { opacity: 1; }',
  ].join('\n');
  document.head.appendChild(style);

  var hideTimeout;
  var progressInterval;
  var current = 0;

  function start() {
    clearTimeout(hideTimeout);
    clearInterval(progressInterval);
    current = 20;
    bar.classList.add('is-active');
    bar.style.width = current + '%';
    progressInterval = setInterval(function () {
      current = Math.min(current + Math.random() * 10, 90);
      bar.style.width = current + '%';
    }, 300);
  }

  function done() {
    clearInterval(progressInterval);
    bar.style.width = '100%';
    hideTimeout = setTimeout(function () {
      bar.classList.remove('is-active');
      bar.style.width = '0%';
    }, 300);
  }

  document.body.addEventListener('htmx:beforeRequest', start);
  document.body.addEventListener('htmx:afterRequest', done);
  document.body.addEventListener('htmx:responseError', done);
  document.body.addEventListener('htmx:sendError', done);
})();

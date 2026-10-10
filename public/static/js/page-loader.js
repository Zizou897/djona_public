(function () {
  // Retire le loader dès que la page est chargée ET que l'animation du logo
  // est terminée (≈ 4 s). Le loader n'apparaît qu'une fois par session : la
  // classe `no-page-loader` est posée dans le <head> si le drapeau existe.
  var el = document.getElementById('page-loader');
  if (!el) return;

  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MIN_VISIBLE = reduced ? 600 : 4200;
  var started = Date.now();
  var done = false;

  function hide() {
    if (done) return;
    done = true;
    el.classList.add('is-done');
    try { sessionStorage.setItem('djona_loader_seen', '1'); } catch (e) { /* stockage indisponible */ }
    setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 700);
  }

  function whenReady() {
    setTimeout(hide, Math.max(0, MIN_VISIBLE - (Date.now() - started)));
  }

  if (document.readyState === 'complete') whenReady();
  else window.addEventListener('load', whenReady);

  // Un chargement anormalement long ne doit pas bloquer le site.
  setTimeout(hide, 9000);
})();

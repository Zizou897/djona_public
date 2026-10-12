(function () {
  // Fiche pièce : un clic sur une miniature affiche la photo en grand.
  var main = document.getElementById('part-gallery-main');
  if (!main) return;
  document.querySelectorAll('[data-gallery-thumb]').forEach(function (thumb) {
    thumb.addEventListener('click', function () {
      main.src = thumb.getAttribute('data-gallery-thumb');
    });
  });
})();

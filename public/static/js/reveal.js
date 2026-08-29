(function () {
  var prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initReveal() {
    var targets = document.querySelectorAll('.reveal:not(.is-visible)');
    if (!targets.length) return;

    if (prefersReduced || !('IntersectionObserver' in window)) {
      targets.forEach(function (el) { el.classList.add('is-visible'); });
      return;
    }

    var observer = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -10% 0px' });

    targets.forEach(function (el) { observer.observe(el); });
  }

  document.addEventListener('DOMContentLoaded', initReveal);
  document.body.addEventListener('htmx:afterSettle', initReveal);
})();

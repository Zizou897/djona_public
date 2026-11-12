/* Location : dates de début / retour → durée en jours et catégorie (courte, moyenne, longue durée).
 * Les seuils viennent du serveur (apps/catalog/rental.py → #rental-categories-data) : une seule règle.
 * window.rentalGate() est appelée par ouvrirModalInteret() (interest-form.js) : tant que les dates ne
 * sont pas valides, la fenêtre de demande ne s'ouvre pas et la carte « Louer avec Djona » est mise en avant. */
(function () {
  var card = document.getElementById('rental-card');
  var dataEl = document.getElementById('rental-categories-data');
  if (!card || !dataEl) return;

  var startEl = document.getElementById('rental-start');
  var endEl = document.getElementById('rental-end');
  var summary = document.getElementById('rental-summary');
  var daysEl = document.getElementById('rental-days');
  var badge = document.getElementById('rental-badge');
  var errorEl = document.getElementById('rental-error');
  var list = document.getElementById('rental-categories');
  var categories = JSON.parse(dataEl.textContent);
  var classesOn = list.dataset.on.split(' ');
  var classesOff = list.dataset.off.split(' ');
  var DAY = 86400000;

  function parse(value) {
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
    return m ? Date.UTC(+m[1], +m[2] - 1, +m[3]) : null;
  }
  function iso(ms) { return new Date(ms).toISOString().slice(0, 10); }
  function french(value) { var p = value.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }
  function categoryFor(days) {
    for (var i = 0; i < categories.length; i++) {
      var c = categories[i];
      if (days >= c.min_days && (c.max_days === null || days <= c.max_days)) return c;
    }
    return null;
  }

  function show(el, visible) { el.style.display = visible ? '' : 'none'; }

  function highlight(key) {
    Array.prototype.forEach.call(list.children, function (li) {
      var active = li.dataset.category === key;
      classesOn.forEach(function (c) { li.classList.toggle(c, active); });
      classesOff.forEach(function (c) { li.classList.toggle(c, !active); });
    });
  }

  // Met à jour l'affichage ; renvoie {valid, days, category, start, end}.
  // `strict` : signale aussi des dates manquantes (clic sur « Louer avec Djona »).
  function update(strict) {
    var start = parse(startEl.value);
    var end = parse(endEl.value);
    var today = parse(startEl.min);
    var error = '';
    var days = null;
    var category = null;

    if (start !== null) endEl.min = iso(start + DAY);

    if (start !== null && today !== null && start < today) {
      error = 'La date de début ne peut pas être dans le passé.';
    } else if (start !== null && end !== null && end <= start) {
      error = 'La date de retour doit être postérieure à la date de début.';
    } else if (start !== null && end !== null) {
      days = Math.round((end - start) / DAY);
      category = categoryFor(days);
    } else if (strict) {
      error = 'Indiquez la date de début et la date de retour de la location.';
    }

    var valid = !error && category !== null;
    if (valid) {
      daysEl.textContent = days + ' jour' + (days > 1 ? 's' : '');
      badge.textContent = category.label;
    }
    summary.style.display = valid ? 'flex' : 'none';
    errorEl.textContent = error;
    show(errorEl, !!error);
    highlight(valid ? category.key : null);
    return { valid: valid, days: days, category: category };
  }

  startEl.addEventListener('change', function () { update(false); });
  endEl.addEventListener('change', function () { update(false); });

  window.rentalGate = function () {
    var state = update(true);
    if (!state.valid) {
      var calm = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      card.scrollIntoView({ behavior: calm ? 'auto' : 'smooth', block: 'center' });
      (startEl.value ? endEl : startEl).focus({ preventScroll: true });
      return false;
    }
    document.getElementById('interest-rental-start').value = startEl.value;
    document.getElementById('interest-rental-end').value = endEl.value;
    document.getElementById('interest-rental-recap').textContent =
      'Du ' + french(startEl.value) + ' au ' + french(endEl.value) + ' · ' + daysEl.textContent;
    document.getElementById('interest-rental-badge').textContent = state.category.label;
    return true;
  };

  update(false);
})();

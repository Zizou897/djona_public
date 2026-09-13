function ouvrirModalInteret() {
  var modal = document.getElementById('modal-interet');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

function fermerModalInteret() {
  var modal = document.getElementById('modal-interet');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
}

(function () {
  var form = document.getElementById('interest-form');
  if (!form || typeof Swal === 'undefined') return;

  var ICONS = { success: 'success', error: 'error' };
  var TITLES = { success: 'Merci !', error: 'Oups' };

  form.addEventListener('submit', function (event) {
    event.preventDefault();

    var submitButton = form.querySelector('button[type="submit"]');
    submitButton.disabled = true;

    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        Swal.fire({
          icon: ICONS[data.status] || 'error',
          title: TITLES[data.status] || 'Oups',
          text: data.message,
          confirmButtonColor: '#003b5a',
        });
        if (data.status === 'success') {
          form.reset();
          fermerModalInteret();
        }
      })
      .catch(function () {
        Swal.fire({
          icon: 'error',
          title: 'Oups',
          text: 'Une erreur est survenue — réessayez.',
          confirmButtonColor: '#003b5a',
        });
      })
      .finally(function () {
        submitButton.disabled = false;
      });
  });
})();

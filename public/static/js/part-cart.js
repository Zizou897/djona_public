(() => {
  // « Ajouter au panier » : envoi en arrière-plan, confirmation SweetAlert2 et mise à jour de la pastille du menu.
  // Sans JavaScript, le formulaire s'envoie normalement et redirige vers le panier.
  const forms = document.querySelectorAll('.js-add-to-cart');
  if (!forms.length) return;

  const updateBadges = (count) => {
    document.querySelectorAll('[data-cart-count]').forEach((badge) => {
      badge.textContent = String(count);
      badge.classList.toggle('hidden', !count);
    });
  };

  forms.forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (typeof Swal === 'undefined') return;
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;

      fetch(form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
      })
        .then((response) => response.json().then((data) => ({ ok: response.ok, data })))
        .then(({ ok, data }) => {
          if (ok && data.status === 'success') {
            updateBadges(data.count);
            Swal.fire({
              icon: 'success',
              title: 'Ajouté au panier',
              text: data.message,
              showCancelButton: true,
              confirmButtonText: 'Voir mon panier',
              cancelButtonText: 'Continuer',
              confirmButtonColor: '#0c4b70',
            }).then((result) => {
              if (result.isConfirmed) window.location.href = '/pieces-detachees/panier/';
            });
          } else {
            Swal.fire({ icon: 'error', title: 'Oups', text: data.message || 'Impossible d’ajouter cette pièce.', confirmButtonColor: '#0c4b70' });
          }
        })
        .catch(() => {
          Swal.fire({ icon: 'error', title: 'Oups', text: 'Une erreur est survenue — réessayez.', confirmButtonColor: '#0c4b70' });
        })
        .finally(() => {
          if (button) button.disabled = false;
        });
    });
  });
})();

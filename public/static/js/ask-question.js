(() => {
  const modal = document.getElementById('ask-modal');
  const form = document.getElementById('ask-form');
  if (!modal || !form) return;

  const question = document.getElementById('ask-question');
  const phone = document.getElementById('ask-phone');
  const submit = document.getElementById('ask-submit');
  const error = document.getElementById('ask-error');
  const success = document.getElementById('ask-success');
  const successMessage = document.getElementById('ask-success-message');

  const digits = (value) => value.replace(/\D/g, '');
  const isValid = () => question.value.trim().length >= 5 && digits(phone.value).length >= 8;
  const refresh = () => { submit.disabled = !isValid(); };

  const showError = (message) => {
    error.textContent = message;
    error.classList.remove('hidden');
  };

  const open = () => {
    form.classList.remove('hidden');
    success.classList.add('hidden');
    success.classList.remove('flex');
    error.classList.add('hidden');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.body.style.overflow = 'hidden';
    setTimeout(() => question.focus(), 50);
  };

  const close = () => {
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    document.body.style.overflow = '';
  };

  document.querySelectorAll('.js-ask-open').forEach((btn) => btn.addEventListener('click', open));
  modal.querySelectorAll('.js-ask-close').forEach((btn) => btn.addEventListener('click', close));
  modal.addEventListener('click', (event) => { if (event.target === modal) close(); });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('flex')) close();
  });

  question.addEventListener('input', refresh);
  phone.addEventListener('input', refresh);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    if (!isValid()) return;
    error.classList.add('hidden');
    submit.disabled = true;

    fetch(form.action, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: new FormData(form),
    })
      .then((response) => response.json())
      .then((data) => {
        if (data.status === 'success') {
          form.reset();
          form.classList.add('hidden');
          successMessage.textContent = data.message;
          success.classList.remove('hidden');
          success.classList.add('flex');
        } else {
          showError(data.message || 'Une erreur est survenue — réessayez.');
        }
      })
      .catch(() => showError('Une erreur est survenue — réessayez.'))
      .finally(refresh);
  });
})();

(() => {
  const type = document.getElementById('id_requester_type');
  const wrapper = document.getElementById('transport-company-wrapper');
  if (!type || !wrapper) return;

  const sync = () => {
    wrapper.hidden = type.value !== 'entreprise';
  };
  type.addEventListener('change', sync);
  sync();
})();

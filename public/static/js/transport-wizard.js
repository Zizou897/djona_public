(() => {
  const form = document.getElementById('transport-form');
  if (!form) return;

  const steps = Array.from(form.querySelectorAll('.transport-step'));
  const nav = document.getElementById('transport-steps-nav');
  const navItems = nav ? Array.from(nav.querySelectorAll('.step-item')) : [];
  const navLines = nav ? Array.from(nav.querySelectorAll('.step-line')) : [];
  const prevBtn = document.getElementById('transport-prev');
  const nextBtn = document.getElementById('transport-next');
  const submitBtn = document.getElementById('transport-submit');
  const stepLabel = document.getElementById('transport-step-label');
  if (!steps.length || !prevBtn || !nextBtn || !submitBtn) return;

  // Si la page a été re-rendue avec des erreurs serveur, on ouvre directement
  // la première étape fautive plutôt que de recommencer à la première.
  const erroredIndex = steps.findIndex((step) => step.querySelector('.text-error'));
  let current = erroredIndex !== -1 ? erroredIndex : 0;

  const CIRCLE_STATE_CLASSES = ['bg-primary', 'text-on-primary', 'bg-primary/15', 'text-primary', 'bg-surface-container', 'text-on-surface-variant'];

  function setCircleState(circle, state) {
    circle.classList.remove(...CIRCLE_STATE_CLASSES);
    if (state === 'active') {
      circle.classList.add('bg-primary', 'text-on-primary');
    } else if (state === 'done') {
      circle.classList.add('bg-primary/15', 'text-primary');
    } else {
      circle.classList.add('bg-surface-container', 'text-on-surface-variant');
    }
  }

  function render() {
    // Les fieldsets et boutons portent des classes `flex`/`inline-flex` dont la
    // spécificité l'emporte sur l'attribut HTML `hidden` : on pilote donc
    // l'affichage via `style.display` plutôt que via `.hidden`.
    steps.forEach((step, i) => {
      step.style.display = i === current ? '' : 'none';
    });

    navItems.forEach((item, i) => {
      const circle = item.querySelector('.step-circle');
      if (circle) setCircleState(circle, i === current ? 'active' : i < current ? 'done' : 'upcoming');
    });

    navLines.forEach((line, i) => {
      line.classList.toggle('bg-primary', i < current);
      line.classList.toggle('bg-outline-variant/40', i >= current);
    });

    const isLast = current === steps.length - 1;
    prevBtn.classList.toggle('invisible', current === 0);
    nextBtn.style.display = isLast ? 'none' : '';
    submitBtn.style.display = isLast ? '' : 'none';
    if (stepLabel) stepLabel.textContent = `Étape ${current + 1} sur ${steps.length}`;
  }

  function goTo(index) {
    current = Math.max(0, Math.min(steps.length - 1, index));
    render();
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function currentStepIsValid() {
    const fields = Array.from(steps[current].querySelectorAll('input, select, textarea'));
    const invalidField = fields.find((field) => field.offsetParent !== null && !field.checkValidity());
    if (invalidField) {
      invalidField.reportValidity();
      return false;
    }
    return true;
  }

  nextBtn.addEventListener('click', () => {
    if (!currentStepIsValid()) return;
    goTo(current + 1);
  });

  prevBtn.addEventListener('click', () => goTo(current - 1));

  navItems.forEach((item, i) => {
    const circle = item.querySelector('.step-circle');
    if (!circle) return;
    circle.addEventListener('click', () => {
      if (i <= current) goTo(i);
    });
  });

  render();
})();

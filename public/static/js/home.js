(() => {
  const counters = document.querySelectorAll('.js-stat-counter');
  if (!counters.length) return;

  const animateCounter = (el) => {
    const target = Number(el.dataset.target || 0);
    const suffix = el.dataset.suffix || '';
    const duration = 2000;
    const startTime = performance.now();

    const update = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easeOutQuad = (t) => t * (2 - t);
      const currentValue = Math.floor(easeOutQuad(progress) * target);

      el.textContent = currentValue.toLocaleString('fr-FR') + suffix;

      if (progress < 1) {
        requestAnimationFrame(update);
      }
    };
    requestAnimationFrame(update);
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach((counter) => observer.observe(counter));
})();

(() => {
  const marqueSelect = document.getElementById('search-marque');
  const carburantSelect = document.getElementById('search-carburant');
  const localisationSelect = document.getElementById('search-localisation');
  const dataEl = document.getElementById('search-brand-options-data');
  if (!marqueSelect || !carburantSelect || !localisationSelect || !dataEl) return;

  const brandOptions = JSON.parse(dataEl.textContent);

  const fillOptions = (select, placeholder, items, toOption) => {
    select.innerHTML = '';
    const placeholderOption = document.createElement('option');
    placeholderOption.value = '';
    placeholderOption.textContent = placeholder;
    select.appendChild(placeholderOption);
    items.forEach((item) => select.appendChild(toOption(item)));
  };

  const updateDependentSelects = () => {
    const data = brandOptions[marqueSelect.value];

    if (!data) {
      fillOptions(carburantSelect, "Choisissez d'abord une marque", []);
      fillOptions(localisationSelect, "Choisissez d'abord une marque", []);
      carburantSelect.disabled = true;
      localisationSelect.disabled = true;
      return;
    }

    fillOptions(carburantSelect, 'Tous les carburants', data.fuel_types, (fuel) => {
      const option = document.createElement('option');
      option.value = fuel.value;
      option.textContent = fuel.label;
      return option;
    });
    fillOptions(localisationSelect, 'Toutes les villes', data.cities, (city) => {
      const option = document.createElement('option');
      option.value = city;
      option.textContent = city;
      return option;
    });
    carburantSelect.disabled = false;
    localisationSelect.disabled = false;
  };

  marqueSelect.addEventListener('change', updateDependentSelects);
  updateDependentSelects();
})();

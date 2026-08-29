(() => {
  const printBtn = document.getElementById('js-print-btn');
  if (printBtn) printBtn.addEventListener('click', () => window.print());

  const links = document.querySelectorAll('.js-toc-link');
  const progressBar = document.getElementById('toc-progress');
  if (!links.length) return;

  const linkByTarget = new Map();
  links.forEach((link) => linkByTarget.set(link.dataset.target, link));

  const setActive = (id) => {
    const linksArray = Array.from(links);
    linksArray.forEach((link) => {
      link.classList.remove('text-primary', 'font-bold', 'border-primary', 'bg-surface-container-low');
      link.classList.add('border-transparent');
    });
    const active = linkByTarget.get(id);
    if (!active) return;
    active.classList.remove('border-transparent');
    active.classList.add('text-primary', 'font-bold', 'border-primary', 'bg-surface-container-low');

    if (progressBar) {
      const index = linksArray.indexOf(active);
      const percent = (index / (linksArray.length - 1)) * 100;
      progressBar.style.height = `${percent}%`;
    }
  };

  const sections = Array.from(linkByTarget.keys())
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        setActive(entry.target.id);
      }
    });
  }, { rootMargin: '-112px 0px -70% 0px' });

  sections.forEach((section) => observer.observe(section));

  links.forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const target = document.getElementById(link.dataset.target);
      if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
})();

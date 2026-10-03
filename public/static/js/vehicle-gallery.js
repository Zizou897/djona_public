(() => {
  const mainImage = document.getElementById('gallery-main-image');
  const thumbs = Array.from(document.querySelectorAll('.js-gallery-thumb'));
  if (!mainImage || !thumbs.length) return;

  const counter = document.getElementById('gallery-counter');
  const lightbox = document.getElementById('gallery-lightbox');
  const lightboxImage = document.getElementById('lightbox-image');
  const lightboxCounter = document.getElementById('lightbox-counter');
  let current = 0;

  const isLightboxOpen = () => lightbox && !lightbox.classList.contains('hidden');

  const show = (index) => {
    current = (index + thumbs.length) % thumbs.length;
    const thumb = thumbs[current];
    const label = `${current + 1} / ${thumbs.length}`;

    mainImage.style.opacity = '0';
    setTimeout(() => {
      mainImage.src = thumb.dataset.fullSrc;
      mainImage.style.opacity = '1';
    }, 150);
    if (lightboxImage) lightboxImage.src = thumb.dataset.fullSrc;

    thumbs.forEach((t) => {
      t.classList.remove('ring-2', 'ring-primary', 'opacity-100');
      t.classList.add('opacity-60');
      t.setAttribute('aria-current', 'false');
    });
    thumb.classList.remove('opacity-60');
    thumb.classList.add('ring-2', 'ring-primary', 'opacity-100');
    thumb.setAttribute('aria-current', 'true');
    thumb.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });

    if (counter) counter.textContent = label;
    if (lightboxCounter) lightboxCounter.textContent = label;
  };

  const openLightbox = () => {
    if (!lightbox) return;
    lightboxImage.src = thumbs[current].dataset.fullSrc;
    lightboxCounter.textContent = `${current + 1} / ${thumbs.length}`;
    lightbox.classList.remove('hidden');
    lightbox.classList.add('flex');
    document.body.style.overflow = 'hidden';
  };

  const closeLightbox = () => {
    if (!lightbox) return;
    lightbox.classList.add('hidden');
    lightbox.classList.remove('flex');
    document.body.style.overflow = '';
  };

  thumbs.forEach((thumb, index) => thumb.addEventListener('click', () => show(index)));
  document.querySelectorAll('.js-gallery-prev').forEach((btn) => btn.addEventListener('click', (e) => { e.stopPropagation(); show(current - 1); }));
  document.querySelectorAll('.js-gallery-next').forEach((btn) => btn.addEventListener('click', (e) => { e.stopPropagation(); show(current + 1); }));
  document.querySelectorAll('.js-gallery-open').forEach((el) => el.addEventListener('click', openLightbox));
  document.querySelectorAll('.js-lightbox-close').forEach((el) => el.addEventListener('click', closeLightbox));

  document.addEventListener('keydown', (event) => {
    if (event.target.closest('input, textarea, select')) return;
    if (document.querySelector('#modal-interet.flex')) return;
    if (event.key === 'Escape' && isLightboxOpen()) closeLightbox();
    if (event.key === 'ArrowLeft') show(current - 1);
    if (event.key === 'ArrowRight') show(current + 1);
  });

  // Balayage tactile (galerie et visionneuse).
  [mainImage, lightboxImage].filter(Boolean).forEach((el) => {
    let startX = null;
    el.addEventListener('touchstart', (e) => { startX = e.touches[0].clientX; }, { passive: true });
    el.addEventListener('touchend', (e) => {
      if (startX === null) return;
      const dx = e.changedTouches[0].clientX - startX;
      if (Math.abs(dx) > 40) show(current + (dx < 0 ? 1 : -1));
      startX = null;
    });
  });
})();

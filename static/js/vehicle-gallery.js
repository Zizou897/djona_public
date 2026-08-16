(() => {
  const mainImage = document.getElementById('gallery-main-image');
  const thumbs = document.querySelectorAll('.js-gallery-thumb');
  if (!mainImage || !thumbs.length) return;

  thumbs.forEach((thumb) => {
    thumb.addEventListener('click', () => {
      const fullSrc = thumb.dataset.fullSrc;
      if (!fullSrc) return;

      mainImage.style.opacity = '0';
      setTimeout(() => {
        mainImage.src = fullSrc;
        mainImage.style.opacity = '1';
      }, 150);

      thumbs.forEach((t) => {
        t.classList.remove('border-2', 'border-primary', 'opacity-100');
        t.classList.add('opacity-60');
      });
      thumb.classList.remove('opacity-60');
      thumb.classList.add('border-2', 'border-primary', 'opacity-100');
    });
  });
})();

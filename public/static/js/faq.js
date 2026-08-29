(() => {
  const toggles = document.querySelectorAll('.js-faq-toggle');
  if (!toggles.length) return;

  toggles.forEach((btn) => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const content = item.querySelector('.faq-content');
      const icon = btn.querySelector('.material-symbols-outlined');
      const isOpen = content.style.height && content.style.height !== '0px';

      document.querySelectorAll('.faq-item').forEach((otherItem) => {
        otherItem.querySelector('.faq-content').style.height = '0px';
        otherItem.querySelector('.js-faq-toggle .material-symbols-outlined').style.transform = 'rotate(0deg)';
      });

      if (!isOpen) {
        content.style.height = `${content.scrollHeight}px`;
        icon.style.transform = 'rotate(180deg)';
      }
    });
  });
})();

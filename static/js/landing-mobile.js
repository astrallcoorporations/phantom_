(() => {
  const carousel = document.getElementById('carousel');
  const slides = document.getElementById('slides');
  const dots = Array.from(document.querySelectorAll('.dot'));
  if (!carousel || !slides) return;

  let currentIndex = 0;
  const totalSlides = dots.length;

  function updatePosition(index) {
    currentIndex = Math.max(0, Math.min(totalSlides - 1, index));
    slides.style.transform = `translateX(-${currentIndex * 100}vw)`;
    dots.forEach((d) => d.classList.toggle('active', Number(d.dataset.index) === currentIndex));
  }

  dots.forEach((d) => d.addEventListener('click', (e) => {
    updatePosition(Number(e.currentTarget.dataset.index));
  }));

  let startX = 0;
  let moved = false;

  carousel.addEventListener('touchstart', (ev) => {
    startX = ev.touches[0].clientX;
    moved = false;
  }, {passive: true});

  carousel.addEventListener('touchmove', (ev) => {
    const dx = ev.touches[0].clientX - startX;
    if (Math.abs(dx) > 20) {
      moved = true;
    }
  }, {passive: true});

  carousel.addEventListener('touchend', (ev) => {
    const dx = ev.changedTouches[0].clientX - startX;
    if (!moved) return;
    const threshold = Math.max(40, window.innerWidth * 0.12);
    if (dx < -threshold) {
      updatePosition(currentIndex + 1);
    } else if (dx > threshold) {
      updatePosition(currentIndex - 1);
    }
  });

  window.addEventListener('resize', () => updatePosition(currentIndex));
  updatePosition(0);
})();

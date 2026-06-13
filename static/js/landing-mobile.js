(() => {
  const carousel = document.getElementById('carousel');
  const dots = Array.from(document.querySelectorAll('.dot'));
  if (!carousel) return;

  function setActive(index){
    dots.forEach(d=>d.classList.toggle('active', Number(d.dataset.index)===index));
  }

  // click dots
  dots.forEach(d=>d.addEventListener('click', (e)=>{
    const i = Number(e.currentTarget.dataset.index);
    carousel.scrollTo({left: window.innerWidth * i, behavior: 'smooth'});
    setActive(i);
  }));

  let isTouch = false, startX = 0, currentX = 0;
  carousel.addEventListener('touchstart', (ev)=>{
    isTouch = true; startX = ev.touches[0].clientX; currentX = startX;
  }, {passive:true});
  carousel.addEventListener('touchmove', (ev)=>{ if (!isTouch) return; currentX = ev.touches[0].clientX; }, {passive:true});
  carousel.addEventListener('touchend', ()=>{
    if (!isTouch) return; isTouch = false;
    const delta = startX - currentX;
    const threshold = Math.min(120, window.innerWidth * 0.18);
    const index = Math.round(carousel.scrollLeft / window.innerWidth);
    if (delta > threshold) {
      const next = Math.min(dots.length-1, index + 1);
      carousel.scrollTo({left: next * window.innerWidth, behavior:'smooth'});
      setActive(next);
    } else if (delta < -threshold) {
      const prev = Math.max(0, index - 1);
      carousel.scrollTo({left: prev * window.innerWidth, behavior:'smooth'});
      setActive(prev);
    } else {
      // snap back to nearest
      const snap = Math.round(carousel.scrollLeft / window.innerWidth);
      carousel.scrollTo({left: snap * window.innerWidth, behavior:'smooth'});
      setActive(snap);
    }
  });

  // keep dots in sync when user scrolls manually
  let tid = null;
  carousel.addEventListener('scroll', ()=>{
    if (tid) clearTimeout(tid);
    tid = setTimeout(()=>{
      const idx = Math.round(carousel.scrollLeft / window.innerWidth);
      setActive(idx);
    }, 80);
  });

  // initial size adjust on orientation change
  window.addEventListener('orientationchange', ()=> setTimeout(()=>carousel.scrollTo({left: Math.round(carousel.scrollLeft/window.innerWidth)*window.innerWidth}), 200));
})();

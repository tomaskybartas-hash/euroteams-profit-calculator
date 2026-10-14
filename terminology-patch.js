(() => {
  function isEnglish() {
    return document.getElementById('enBtn')?.classList.contains('active');
  }

  function applyTerminology() {
    const button = document.getElementById('modeMonthly');
    if (!button) return;
    button.textContent = isEnglish()
      ? 'Fixed monthly amounts calculator'
      : 'Fiksuotos mėnesinės sumos skaičiuoklė';
  }

  document.addEventListener('click', e => {
    if (e.target.closest('#ltBtn') || e.target.closest('#enBtn') || e.target.closest('#loginLt') || e.target.closest('#loginEn')) {
      requestAnimationFrame(() => requestAnimationFrame(applyTerminology));
    }
  });

  window.addEventListener('load', applyTerminology);
  setTimeout(applyTerminology, 100);
})();

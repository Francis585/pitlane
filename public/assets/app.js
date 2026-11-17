// PITLANE — interacciones mínimas, sin dependencias.
(() => {
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // Marca el enlace activo del menú por ruta.
  const path = location.pathname.replace(/index\.html$/, "");
  $$('.nav-links a').forEach((a) => {
    const href = a.getAttribute('href').replace(/index\.html$/, "");
    if (href !== "/" && path.startsWith(href)) a.setAttribute('aria-current', 'page');
    else if (href === "/" && (path === "/" || path === "")) a.setAttribute('aria-current', 'page');
  });

  // Cuenta atrás del próximo GP.
  const cd = $('#countdown');
  if (cd) {
    const target = new Date(cd.dataset.date + 'T14:00:00Z').getTime();
    const cells = {
      d: $('[data-cd="d"]', cd), h: $('[data-cd="h"]', cd),
      m: $('[data-cd="m"]', cd), s: $('[data-cd="s"]', cd),
    };
    const pad = (n) => String(Math.max(0, n)).padStart(2, '0');
    const tick = () => {
      const diff = target - Date.now();
      if (diff <= 0) {
        cd.innerHTML = '<div style="grid-column:1/-1;padding:14px"><b>EN PISTA</b><span>FIN DE SEMANA EN CURSO</span></div>';
        clearInterval(timer);
        return;
      }
      const sec = Math.floor(diff / 1000);
      cells.d.textContent = pad(Math.floor(sec / 86400));
      cells.h.textContent = pad(Math.floor((sec % 86400) / 3600));
      cells.m.textContent = pad(Math.floor((sec % 3600) / 60));
      cells.s.textContent = pad(sec % 60);
    };
    tick();
    const timer = setInterval(tick, 1000);
  }

  // Filtro de escuderías por estilo (hub).
  $$('[data-filter]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const f = btn.dataset.filter;
      $$('[data-filter]').forEach((b) => b.classList.toggle('on', b === btn));
      $$('.hub-link').forEach((a) => {
        a.style.display = f === 'all' || a.dataset.layout === f ? '' : 'none';
      });
    });
  });

  // Compartir: copia el enlace.
  $$('[data-share]').forEach((b) => b.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(location.href); b.textContent = 'Enlace copiado'; }
    catch { b.textContent = location.href; }
  }));

  // Semana de GP: si el build es antiguo y la semana ya terminó, se retira el tema
  // y el sitio vuelve a sus colores neutros sin esperar a la siguiente compilación.
  const body = document.body;
  if (body.classList.contains('race-week') && body.dataset.gpEnd) {
    const end = new Date(body.dataset.gpEnd + 'T23:59:59');
    if (Date.now() > end.getTime()) {
      body.classList.remove('race-week');
      const ribbon = document.querySelector('.gp-ribbon');
      if (ribbon) ribbon.remove();
      document.documentElement.style.setProperty('--gp', '#ff5a1f');
      document.documentElement.style.setProperty('--gp-2', '#e8e8e8');
    }
  }
})();

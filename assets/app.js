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

  // El menú pasa de transparente a sólido al bajar.
  const nav = document.querySelector('.nav');
  if (nav) {
    const onScroll = () => nav.classList.toggle('is-solid', window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  // marcar que hay JS (permite animaciones sin romper el HTML sin JS)
  document.documentElement.classList.add('js');

  // carrusel del hero
  const hero = document.querySelector('[data-hero-slideshow]');
  if (hero) {
    const slides = [...hero.querySelectorAll('.hero-slide')];
    const idxEl = document.querySelector('[data-hero-index]');
    const labEl = document.querySelector('[data-hero-label]');
    // el resto de imágenes se cargan después, cuando la página ya está lista
    const hydrate = () => slides.forEach((s) => {
      if (s.dataset.srcset) { s.srcset = s.dataset.srcset; delete s.dataset.srcset; }
      if (s.dataset.src && !s.src) { s.src = s.dataset.src; delete s.dataset.src; }
    });
    if ('requestIdleCallback' in window) requestIdleCallback(hydrate, { timeout: 2500 });
    else setTimeout(hydrate, 1800);

    if (slides.length > 1) {
      let i = 0;
      setInterval(() => {
        slides[i].classList.remove('is-on');
        i = (i + 1) % slides.length;
        slides[i].classList.add('is-on');
        if (idxEl) idxEl.textContent = String(i + 1).padStart(2, '0');
        if (labEl) labEl.textContent = slides[i].dataset.label || '';
      }, 6000);
    }
  }

  // aparición al hacer scroll
  const reveals = [...document.querySelectorAll('[data-reveal]')];
  if (reveals.length && 'IntersectionObserver' in window) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.06 });
    reveals.forEach((el) => io.observe(el));
  } else {
    reveals.forEach((el) => el.classList.add('is-in'));
  }
  // red de seguridad: nunca dejar contenido oculto
  setTimeout(() => reveals.forEach((el) => el.classList.add('is-in')), 2500);

  // parallax suave del hero (desactivado en móvil o con movimiento reducido)
  const media = document.querySelector('.hero-media');
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (media && !reduce && window.innerWidth > 860) {
    let raf = null;
    const move = () => {
      raf = null;
      const y = Math.min(window.scrollY, 700);
      media.style.transform = `translate3d(0, ${y * -0.05}px, 0)`;
    };
    window.addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(move); }, { passive: true });
  }

  // contadores
  const counters = [...document.querySelectorAll('[data-count]')];
  counters.forEach((el) => {
    const target = Number(el.dataset.count);
    if (!Number.isFinite(target)) return;
    const dur = 1100, t0 = performance.now();
    const step = (t) => {
      const k = Math.min(1, (t - t0) / dur);
      el.textContent = Math.round(target * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
    // si el navegador se interrumpe, el valor final queda igualmente
    setTimeout(() => { el.textContent = target; }, dur + 400);
  });

  // barra de progreso de lectura
  const bar = document.createElement('div');
  bar.className = 'read-bar';
  document.body.appendChild(bar);
  const paint = () => {
    const h = document.documentElement;
    const max = h.scrollHeight - h.clientHeight;
    bar.style.transform = `scaleX(${max > 0 ? h.scrollTop / max : 0})`;
  };
  paint();
  window.addEventListener('scroll', paint, { passive: true });
  window.addEventListener('resize', paint);

  // entrada escalonada de las rejillas
  const grids = [...document.querySelectorAll('.drivers-grid, .tiles, .moments, .circ-grid, .news-grid, .roster')];
  grids.forEach((g) => {
    [...g.children].forEach((child, i) => {
      child.style.transitionDelay = `${Math.min(i, 9) * 55}ms`;
      g.classList.add('stagger-init');
    });
    const io = new IntersectionObserver((es) => {
      es.forEach((e) => {
        if (e.isIntersecting) { g.classList.remove('stagger-init'); g.classList.add('stagger-in'); io.unobserve(g); }
      });
    }, { rootMargin: '0px 0px -6% 0px' });
    io.observe(g);
    setTimeout(() => { g.classList.remove('stagger-init'); g.classList.add('stagger-in'); }, 2600);
  });

  // inclinación suave de las tarjetas de piloto (solo ratón)
  if (window.matchMedia('(hover: hover) and (min-width: 900px)').matches && !reduce) {
    document.querySelectorAll('.dcard, .circ-card, .tile').forEach((card) => {
      card.addEventListener('mousemove', (e) => {
        const r = card.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width - 0.5;
        const y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = `translateY(-6px) rotateX(${(-y * 3).toFixed(2)}deg) rotateY(${(x * 3).toFixed(2)}deg)`;
      });
      card.addEventListener('mouseleave', () => { card.style.transform = ''; });
    });
  }

  // parallax de la cabecera de escudería
  const th = document.querySelector('.team-hero-photo');
  if (th && !reduce && window.innerWidth > 860) {
    let rafT = null;
    window.addEventListener('scroll', () => {
      if (rafT) return;
      rafT = requestAnimationFrame(() => {
        rafT = null;
        const y = Math.min(window.scrollY, 600);
        th.style.transform = `translate3d(0, ${y * -0.06}px, 0) scale(1.04)`;
      });
    }, { passive: true });
  }

  // si una imagen de noticia falla, la tarjeta muestra el patrón de marca
  document.querySelectorAll('img[data-fallback]').forEach((img) => {
    img.addEventListener('error', () => {
      const box = img.parentElement;
      if (box) { box.classList.add('ncard-img--empty'); img.remove(); }
    });
  });

  // tema claro / oscuro
  const toggle = document.querySelector('.theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const root = document.documentElement;
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('pitlane-theme', next); } catch (e) {}
    });
  }
  // ------- comparador de pilotos -------
  const cmpData = document.getElementById('cmp-data');
  if (cmpData) {
    const rows = JSON.parse(cmpData.textContent);
    const A = document.getElementById('cmp-a');
    const B = document.getElementById('cmp-b');
    const out = document.getElementById('cmp-out');
    const norm = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    rows.sort((a, b) => a.pos - b.pos);
    const opts = rows.map((r, i) => `<option value="${i}">${r.name} · ${r.team}</option>`).join('');
    A.innerHTML = opts; B.innerHTML = opts;
    A.value = '0'; B.value = rows.length > 1 ? '1' : '0';

    const metrics = [
      ['Posición', 'pos', true], ['Puntos', 'points'], ['Victorias', 'wins'], ['Podios', 'podiums'],
      ['Poles', 'poles'], ['Vueltas rápidas', 'fl'], ['Carreras', 'races'], ['Abandonos', 'dnf', true],
    ];

    const render = () => {
      const a = rows[+A.value], b = rows[+B.value];
      if (!a || !b) return;
      const head = `
        <div class="cmp-head">
          <div class="cmp-side" style="--c:${a.brand}"><b>${a.name}</b><span>${a.team}</span></div>
          <span class="cmp-vs-sm">vs</span>
          <div class="cmp-side cmp-side--r" style="--c:${b.brand}"><b>${b.name}</b><span>${b.team}</span></div>
        </div>`;
      const body = metrics.map(([label, key, lowerWins]) => {
        const va = a[key] ?? 0, vb = b[key] ?? 0;
        const total = Math.max(va, vb, 1);
        const aWins = lowerWins ? va < vb : va > vb;
        const bWins = lowerWins ? vb < va : vb > va;
        return `<div class="cmp-row">
          <span class="cmp-val ${aWins ? 'is-win' : ''}">${va}</span>
          <span class="cmp-track cmp-track--l"><i style="--w:${(va / total * 100).toFixed(1)}%;background:${a.brand}"></i></span>
          <span class="cmp-label">${label}</span>
          <span class="cmp-track cmp-track--r"><i style="--w:${(vb / total * 100).toFixed(1)}%;background:${b.brand}"></i></span>
          <span class="cmp-val ${bWins ? 'is-win' : ''}">${vb}</span>
        </div>`;
      }).join('');
      out.innerHTML = head + body;
    };
    A.addEventListener('change', render); B.addEventListener('change', render);
    render();
  }

  // ------- buscador -------
  const searchData = document.getElementById('search-data');
  if (searchData) {
    const items = JSON.parse(searchData.textContent);
    const input = document.getElementById('site-search');
    const out = document.getElementById('search-out');
    const count = document.getElementById('search-count');
    const strip = (s) => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    items.forEach((i) => { i._k = strip(i.t + ' ' + i.s + ' ' + i.k); });

    const draw = () => {
      const q = strip(input.value.trim());
      const found = q ? items.filter((i) => i._k.includes(q)).slice(0, 24) : items.slice(0, 12);
      count.textContent = q ? `${found.length} resultados` : '';
      out.innerHTML = found.length
        ? found.map((i) => `<a class="search-item" href="${i.u}">
             <span class="s-kind">${i.k}</span>
             <b>${i.t}</b>
             <span class="s-sub">${i.s}</span>
           </a>`).join('')
        : `<p class="dim">Nada con «${input.value}». Prueba con un apellido, una escudería o un circuito.</p>`;
    };
    let t; input.addEventListener('input', () => { clearTimeout(t); t = setTimeout(draw, 90); });
    draw();
  }
})();
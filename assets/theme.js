// Tema claro/oscuro. Se carga en el <head> para evitar el parpadeo.
(function () {
  try {
    var saved = localStorage.getItem('pitlane-theme');
    var prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches;
    var theme = saved || (prefersLight ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', theme);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();

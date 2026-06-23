(function () {
  const host = location.hostname;
  window.IS_GITHUB_PAGES = host.endsWith("github.io");
  window.API_BASE = window.IS_GITHUB_PAGES ? "https://zamanai.onrender.com" : "";
})();
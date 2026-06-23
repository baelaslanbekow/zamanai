(function () {
  const host = location.hostname;
  if (host.endsWith("github.io")) {
    window.API_BASE = "https://zamanai.onrender.com";
    return;
  }
  window.API_BASE = "";
})();
(() => {
  const key = "mizzac-color-theme";
  const root = document.documentElement;

  function preferredTheme() {
    try {
      const saved = localStorage.getItem(key);
      if (saved === "light" || saved === "dark") return saved;
    } catch (error) {
      // Storage can be disabled; the operating-system preference remains usable.
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme) {
    const previousTheme = root.getAttribute("data-bs-theme");
    root.setAttribute("data-bs-theme", theme);
    const toggle = document.getElementById("themeToggle");
    if (toggle) {
      const isDark = theme === "dark";
      toggle.setAttribute("aria-pressed", String(isDark));
      toggle.setAttribute(
        "aria-label",
        isDark ? "Activer le thème clair" : "Activer le thème sombre",
      );
      toggle.querySelector("[data-theme-light]").hidden = !isDark;
      toggle.querySelector("[data-theme-dark]").hidden = isDark;
    }
    if (previousTheme && previousTheme !== theme) {
      document.dispatchEvent(new CustomEvent("mizzac:themechange", { detail: { theme } }));
    }
  }

  applyTheme(preferredTheme());

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(root.getAttribute("data-bs-theme") || preferredTheme());
    document.getElementById("themeToggle")?.addEventListener("click", () => {
      const theme = root.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(key, theme);
      } catch (error) {
        // The selected theme still applies for the current page.
      }
      applyTheme(theme);
    });
  });
})();

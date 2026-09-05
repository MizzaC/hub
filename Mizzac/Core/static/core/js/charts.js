(() => {
  "use strict";

  const charts = new Map();
  const palette = Object.freeze([
    "#206bc4",
    "#6f42c1",
    "#2fb344",
    "#f59f00",
    "#d63939",
    "#0ca678",
    "#4299e1",
    "#ae3ec9",
  ]);

  function isPlainObject(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function merge(target, source) {
    const output = { ...target };
    Object.entries(source || {}).forEach(([key, value]) => {
      output[key] = isPlainObject(value) && isPlainObject(output[key])
        ? merge(output[key], value)
        : value;
    });
    return output;
  }

  function elementFor(target) {
    return typeof target === "string" ? document.querySelector(target) : target;
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light";
  }

  function foregroundColor() {
    return getComputedStyle(document.body).getPropertyValue("--tblr-body-color").trim()
      || (currentTheme() === "dark" ? "#e5e7eb" : "#1f2937");
  }

  function defaults() {
    return {
      chart: {
        animations: {
          enabled: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
        },
        background: "transparent",
        fontFamily: "inherit",
        foreColor: foregroundColor(),
        toolbar: { show: false },
      },
      colors: palette,
      dataLabels: { enabled: false },
      legend: {
        fontFamily: "inherit",
        position: "bottom",
      },
      noData: { text: "Aucune donnée disponible" },
      theme: { mode: currentTheme() },
      tooltip: { theme: currentTheme() },
    };
  }

  function destroy(target) {
    const element = elementFor(target);
    const chart = element ? charts.get(element) : null;
    if (!chart) return;
    chart.destroy();
    charts.delete(element);
  }

  function mount(target, options) {
    const element = elementFor(target);
    if (!element) throw new Error("Conteneur ApexCharts introuvable.");
    if (typeof window.ApexCharts !== "function") {
      throw new Error("ApexCharts n'est pas chargé par le layout Core.");
    }
    destroy(element);
    const chart = new window.ApexCharts(element, merge(defaults(), options));
    charts.set(element, chart);
    chart.render();
    return chart;
  }

  function destroyAll() {
    [...charts.keys()].forEach(destroy);
  }

  function updateTheme(theme) {
    charts.forEach((chart) => {
      chart.updateOptions(
        {
          chart: { foreColor: foregroundColor() },
          theme: { mode: theme },
          tooltip: { theme },
        },
        false,
        true,
      );
    });
  }

  function formatNumber(value, options = {}) {
    return new Intl.NumberFormat("fr-FR", options).format(value);
  }

  document.addEventListener("mizzac:themechange", (event) => {
    updateTheme(event.detail.theme);
  });
  window.addEventListener("pagehide", destroyAll);

  window.MizzacCharts = Object.freeze({
    destroy,
    destroyAll,
    formatNumber,
    mount,
    palette,
  });
})();

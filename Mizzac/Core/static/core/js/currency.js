(() => {
  "use strict";

  const validModes = new Set(["DEFAULT", "EUR", "USD"]);
  let mode = "DEFAULT";

  function amountFor(element, currency) {
    const raw = currency === "EUR" ? element.dataset.amountEur : element.dataset.amountUsd;
    if (!raw) return null;
    const amount = Number(raw);
    return Number.isFinite(amount) ? amount : null;
  }

  function formatMoney(amount, currency, decimals) {
    return new Intl.NumberFormat("fr-FR", {
      style: "currency",
      currency,
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(amount);
  }

  function renderValue(element) {
    const preferred = mode === "DEFAULT" ? element.dataset.defaultCurrency : mode;
    let currency = preferred;
    let amount = amountFor(element, currency);
    if (amount === null) {
      currency = element.dataset.originalCurrency;
      amount = Number(element.dataset.originalAmount);
      element.title = "Conversion indisponible : valeur affichée dans sa devise d’origine.";
    } else {
      element.title = element.dataset.rateDescription || "";
    }
    const decimals = Number.parseInt(element.dataset.decimals || "2", 10);
    element.textContent = formatMoney(amount, currency, decimals);
    element.dataset.currentCurrency = currency;
  }

  function applyMode(nextMode) {
    mode = validModes.has(nextMode) ? nextMode : "DEFAULT";
    document.querySelectorAll("[data-currency-value]").forEach(renderValue);
    document.querySelectorAll("[data-currency-mode]").forEach((button) => {
      const active = button.dataset.currencyMode === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    document.dispatchEvent(new CustomEvent("mizzac:currencychange", { detail: { mode } }));
  }

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-currency-mode]");
    if (button) applyMode(button.dataset.currencyMode);
  });
  document.addEventListener("DOMContentLoaded", () => applyMode("DEFAULT"));

  window.MizzacCurrency = Object.freeze({ applyMode });
})();

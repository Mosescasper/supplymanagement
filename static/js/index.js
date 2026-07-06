/* ==========================================================================
   SupplyLink — index.js
   Vanilla JS: dynamic line items (POs / Requisitions), confirmation dialogs,
   flash message auto-dismiss, and low-stock row highlighting.

   NOTE: This version uses no addEventListener calls anywhere. Interactions
   are wired via inline HTML attributes (onclick, oninput) and on-property
   assignment (window.onload) instead. Templates must call the functions
   below directly, e.g.:

     <button type="button" onclick="dismissFlash(this.closest('.flash'))">✕</button>
     <button type="button" onclick="addLineItem()">+ Add line</button>
     <button type="button" onclick="removeLineItem(this)">✕</button>
     <input data-qty oninput="recalcLineTotals()">
     <input data-unit-cost oninput="recalcLineTotals()">
     <a href="/items/5/delete" onclick="return confirmAction('Delete this item?')">Delete</a>
   ========================================================================== */

window.onload = function () {
  initFlashMessages();
  initLineItems();
  initLowStockHighlight();
};

/* ---------------------------------------------------------------------- *
 * Flash messages — auto-dismiss + manual close
 * Close button in HTML should call: onclick="dismissFlash(this.closest('.flash'))"
 * ---------------------------------------------------------------------- */
function initFlashMessages() {
  const AUTO_DISMISS_MS = 4000;

  document.querySelectorAll(".flash").forEach((flash) => {
    setTimeout(() => dismissFlash(flash), AUTO_DISMISS_MS);
  });
}

function dismissFlash(flash) {
  if (!flash || !flash.parentNode) return;
  flash.style.transition = "opacity 0.2s ease, transform 0.2s ease";
  flash.style.opacity = "0";
  flash.style.transform = "translateY(-6px)";
  setTimeout(() => flash.remove(), 200);
}

/**
 * Programmatically show a flash message (e.g. after an async action).
 * type: "success" | "error" | "warning" | "info"
 */
function showFlash(message, type = "info") {
  let container = document.querySelector(".flash-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "flash-container";
    document.body.appendChild(container);
  }

  const flash = document.createElement("div");
  flash.className = `flash flash-${type}`;
  flash.innerHTML = `
    <span>${message}</span>
    <button type="button" class="flash-close" aria-label="Dismiss"
            onclick="dismissFlash(this.closest('.flash'))">✕</button>
  `;
  container.appendChild(flash);

  setTimeout(() => dismissFlash(flash), 4000);
}

/* ---------------------------------------------------------------------- *
 * Confirmation dialogs — destructive / state-changing actions
 * (delete item, cancel PO, reject requisition, etc.)
 * Usage in HTML: onclick="return confirmAction('Are you sure?')"
 * For a <form>, use: onsubmit="return confirmAction('Are you sure?')"
 * ---------------------------------------------------------------------- */
function confirmAction(message) {
  return window.confirm(message || "Are you sure?");
}

/* ---------------------------------------------------------------------- *
 * Dynamic line items — Purchase Orders & Requisitions
 * Expects a container: <div class="line-items" id="line-items">
 * Each row: <div class="line-item-row"> with inputs named item[], qty[], etc.
 * "Add line" button in HTML: onclick="addLineItem()"
 * "Remove line" button in each row: onclick="removeLineItem(this)"
 * Qty / unit-cost inputs: oninput="recalcLineTotals()"
 * ---------------------------------------------------------------------- */
function initLineItems() {
  // Nothing to wire up here now — row buttons and inputs call their
  // handlers directly via inline attributes. This just does the
  // initial total calculation on page load.
  recalcLineTotals();
}

function addLineItem() {
  const container = document.getElementById("line-items");
  if (!container) return;

  const template = container.querySelector(".line-item-row");
  if (!template) return;

  const newRow = template.cloneNode(true);
  newRow.querySelectorAll("input, select").forEach((field) => {
    if (field.tagName === "SELECT") {
      field.selectedIndex = 0;
    } else {
      field.value = "";
    }
  });
  container.appendChild(newRow);
  recalcLineTotals();
}

function removeLineItem(buttonEl) {
  const row = buttonEl.closest(".line-item-row");
  const container = row ? row.parentElement : null;
  if (!row || !container) return;

  // Keep at least one line item row
  if (container.querySelectorAll(".line-item-row").length > 1) {
    row.remove();
    recalcLineTotals();
  } else {
    showFlash("At least one line item is required.", "warning");
  }
}

function recalcLineTotals() {
  const container = document.getElementById("line-items");
  if (!container) return;

  let grandTotal = 0;

  container.querySelectorAll(".line-item-row").forEach((row) => {
    const qtyField = row.querySelector("[data-qty]");
    const costField = row.querySelector("[data-unit-cost]");
    const lineTotalField = row.querySelector("[data-line-total]");

    const qty = qtyField ? parseFloat(qtyField.value) || 0 : 0;
    const cost = costField ? parseFloat(costField.value) || 0 : 0;
    const lineTotal = qty * cost;

    if (lineTotalField) {
      lineTotalField.textContent = formatCurrency(lineTotal);
    }
    grandTotal += lineTotal;
  });

  const grandTotalField = document.getElementById("grand-total");
  if (grandTotalField) {
    grandTotalField.textContent = formatCurrency(grandTotal);
  }
}

function formatCurrency(amount) {
  return "KES " + amount.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/* ---------------------------------------------------------------------- *
 * Low-stock highlighting — rows with data-qty-on-hand <= data-reorder-level
 * ---------------------------------------------------------------------- */
function initLowStockHighlight() {
  document.querySelectorAll("tr[data-qty-on-hand]").forEach((row) => {
    const onHand = parseFloat(row.getAttribute("data-qty-on-hand"));
    const reorderLevel = parseFloat(row.getAttribute("data-reorder-level"));
    if (!isNaN(onHand) && !isNaN(reorderLevel) && onHand <= reorderLevel) {
      row.classList.add("row-low-stock");
    }
  });
}
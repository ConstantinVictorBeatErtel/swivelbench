/* Live bridge for the bundled showcase.  The visual design is intentionally
 * static, but its score field must never drift from the strict verifier. */
(function () {
  "use strict";

  var state = { env: "banking", model: "nemotron", runs: {}, busy: false };
  var fallback = {
    banking: {
      oracle: { passed: 35, total: 35, criteria: [] },
      nemotron: { passed: 24, total: 35, criteria: [] },
      poolside: { passed: 26, total: 35, criteria: [] }
    },
    grading: {
      oracle: { passed: 26, total: 26, criteria: [] },
      nemotron: { passed: 22, total: 26, criteria: [] },
      poolside: { passed: 26, total: 26, criteria: [] }
    }
  };

  function modelKey(model) {
    return /poolside/i.test(model || "") ? "poolside" : "nemotron";
  }

  function taskKey(task) {
    return /^GR-/.test(task || "") ? "grading" : "banking";
  }

  function visualGroups(env) {
    return env === "grading" ? [7, 10, 4, 5] : [8, 9, 10, 8];
  }

  function criteriaFor(env, model) {
    if (model === "oracle") {
      var n = fallback[env].oracle.total;
      return Array.from({ length: n }, function () { return { passed: true }; });
    }
    return (state.runs[env] && state.runs[env][model] && state.runs[env][model].criteria) || fallback[env][model].criteria;
  }

  function currentResult() {
    if (state.model === "oracle") return fallback[state.env].oracle;
    return (state.runs[state.env] && state.runs[state.env][state.model]) || fallback[state.env][state.model];
  }

  function setText(selector, text) {
    var el = document.querySelector(selector);
    if (!el) return;
    var child = el.querySelector(".sc-interp") || el;
    child.textContent = text;
  }

  function clickableLabel(label) {
    return Array.from(document.querySelectorAll("*")).filter(function (node) {
      return node.children.length === 0 && (node.textContent || "").trim() === label;
    }).map(function (node) {
      var parent = node.parentElement;
      return parent && /cursor\s*:\s*pointer/i.test(parent.getAttribute("style") || "") ? parent : null;
    }).filter(Boolean);
  }

  function scoreNode() {
    return Array.from(document.querySelectorAll("*")).find(function (node) {
      return /font-size\s*:\s*82px/i.test(node.getAttribute("style") || "") && node.querySelector(".sc-interp");
    });
  }

  function countNode() {
    return Array.from(document.querySelectorAll("*")).find(function (node) {
      return /text-align\s*:\s*right/i.test(node.getAttribute("style") || "") &&
        /criteria\s+met/i.test(node.textContent || "") && node.querySelector(".sc-interp");
    });
  }

  function progressNode() {
    return Array.from(document.querySelectorAll("*")).find(function (node) {
      return /position\s*:\s*absolute/i.test(node.getAttribute("style") || "") &&
        /width\s*:/i.test(node.getAttribute("style") || "") &&
        /background/i.test(node.getAttribute("style") || "");
    });
  }

  function verdictNode() {
    return Array.from(document.querySelectorAll("*")).find(function (node) {
      return /margin-top\s*:\s*16px/i.test(node.getAttribute("style") || "") && node.querySelector(".sc-interp");
    });
  }

  function cellNodes() {
    return Array.from(document.querySelectorAll("*")).filter(function (node) {
      var style = node.getAttribute("style") || "";
      return /aspect-ratio\s*:\s*1\s*\/\s*1/i.test(style) && node.children.length === 0;
    });
  }

  function legendRows() {
    return Array.from(document.querySelectorAll("*")).filter(function (node) {
      var style = node.getAttribute("style") || "";
      return /display\s*:\s*flex/i.test(style) &&
        /padding\s*:\s*11px 14px/i.test(style) &&
        node.querySelectorAll(".sc-interp").length >= 2;
    });
  }

  function syncModelStyles() {
    var modelNodes = clickableLabel("Oracle").concat(clickableLabel("Nemotron 3 Super"));
    var pool = document.querySelector("[data-swivel-poolside]");
    if (pool) modelNodes.push(pool);
    modelNodes.forEach(function (node) {
      var label = (node.innerText || "").trim();
      var key = node.hasAttribute("data-swivel-poolside")
        ? "poolside"
        : (/Oracle/i.test(label) ? "oracle" : "nemotron");
      var selected = key === state.model;
      node.style.background = selected ? "#111110" : "transparent";
      node.style.color = selected ? "#ffffff" : "#33332e";
      node.style.borderColor = selected ? "#111110" : "rgba(17,17,16,0.18)";
      node.setAttribute("aria-pressed", selected ? "true" : "false");
    });
  }

  function hideVerifierButton() {
    // The generated page includes this demo-only action. Find its clickable
    // wrapper by its rendered label so the bridge remains resilient to bundle
    // template-id changes.
    var label = Array.from(document.querySelectorAll("*")).find(function (node) {
      var text = (node.textContent || "").trim();
      return node.children.length === 0 && (text === "Run verifier" || text === "Check the work");
    });
    if (!label) return;
    var button = label.parentElement;
    while (button && button !== document.body) {
      if (/cursor\s*:\s*pointer/i.test(button.getAttribute("style") || "")) break;
      button = button.parentElement;
    }
    if (button && button !== document.body) button.style.display = "none";
  }

  function render() {
    if (state.busy) return;
    state.busy = true;
    try {
      var result = currentResult();
      var total = result.total || fallback[state.env][state.model].total;
      var passed = result.passed == null ? total : result.passed;
      var pct = Math.round((passed / total) * 100);
      var score = scoreNode();
      if (score) score.querySelector(".sc-interp").textContent = String(pct);
      var count = countNode();
      if (count) count.querySelector(".sc-interp").textContent = String(passed) + " / " + String(total);
      var bar = progressNode();
      if (bar) bar.style.width = pct + "%";
      var verdict = verdictNode();
      verdict = verdict && verdict.querySelector(".sc-interp");
      if (verdict) verdict.textContent = passed === total
        ? "Whole field filled. The task passes."
        : "Partial credit trains and diagnoses well, but it never becomes a pass: one unmet criterion fails the task.";

      var cells = cellNodes();
      var criteria = criteriaFor(state.env, state.model);
      cells.forEach(function (cell, i) {
        var ok = criteria[i] ? !!criteria[i].passed : i < passed;
        cell.style.background = ok ? "rgb(27, 27, 24)" : "transparent";
        cell.style.borderColor = ok ? "transparent" : "rgba(17, 17, 16, 0.42)";
        cell.style.animation = ok ? "none" : "swv-pulse 3.2s ease-in-out infinite";
      });

      var sizes = visualGroups(state.env);
      var offset = 0;
      legendRows().forEach(function (row, gi) {
        var n = sizes[gi] || 0;
        var groupCriteria = criteria.slice(offset, offset + n);
        var ok = groupCriteria.filter(function (c) { return c && c.passed; }).length;
        var values = row.querySelectorAll(".sc-interp");
        if (values.length > 1) values[values.length - 1].textContent = ok + " / " + n;
        offset += n;
      });
      syncModelStyles();
      hideVerifierButton();
    } finally {
      state.busy = false;
    }
  }

  function bindTabs() {
    var envNodes = clickableLabel("Commercial banking").concat(clickableLabel("Grading"));
    envNodes.forEach(function (node) {
      var label = (node.innerText || "").trim();
      if (node.dataset.swivelBound) return;
      node.dataset.swivelBound = "1";
      node.addEventListener("click", function () {
        state.env = label === "Grading" ? "grading" : "banking";
        setTimeout(render, 30);
      });
    });

    var modelNodes = clickableLabel("Oracle").concat(clickableLabel("Nemotron 3 Super"));
    modelNodes.forEach(function (node) {
      var label = (node.innerText || "").trim();
      if (node.dataset.swivelBound) return;
      node.dataset.swivelBound = "1";
      node.addEventListener("click", function () {
        state.model = /Oracle/i.test(label) ? "oracle" : "nemotron";
        setTimeout(render, 30);
      });
    });
    var nem = modelNodes.find(function (node) { return /Nemotron/i.test((node.innerText || "").trim()); });
    if (nem && !document.querySelector("[data-swivel-poolside]")) {
      var pool = nem.cloneNode(true);
      pool.dataset.swivelPoolside = "1";
      pool.removeAttribute("data-dc-tpl");
      var labelNode = pool.querySelector(".sc-interp") || pool;
      labelNode.textContent = "Poolside Laguna XS 2.1";
      pool.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        state.model = "poolside";
        render();
      });
      nem.parentElement.appendChild(pool);
    }
    syncModelStyles();
    hideVerifierButton();
  }

  async function load() {
    try {
      var listing = await (await fetch("/api/runs", { cache: "no-store" })).json();
      var canonical = (listing.runs || []).filter(function (r) { return r.canonical && r.task && r.model; });
      await Promise.all(canonical.map(async function (row) {
        var env = taskKey(row.task), model = modelKey(row.model);
        if (state.runs[env] && state.runs[env][model]) return;
        var detail = await (await fetch("/api/run/" + encodeURIComponent(row.run_id), { cache: "no-store" })).json();
        var criteria = (detail.graph || []).flatMap(function (step) { return step.grades || []; });
        state.runs[env] = state.runs[env] || {};
        state.runs[env][model] = {
          passed: row.criteria_passed,
          total: row.criteria_total,
          criteria: criteria
        };
      }));
    } catch (error) {
      // The bundled page remains useful offline via the last known fallback.
      console.warn("SwivelBench live score unavailable", error);
    }
    bindTabs();
    render();
  }

  function boot() {
    load();
    setInterval(function () { bindTabs(); render(); }, 1500);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { setTimeout(boot, 450); });
  else setTimeout(boot, 450);
}());

"use strict";
const element = (id) => document.getElementById(id);
let lastResponse = null;
let history = [];
let querying = false;
let reindexing = false;
let runtimeConfig = null;
let applying = false;
let refreshing = false;

function scoreHelp(value, config) {
  const explanations = {
    hybrid: `RRF combines BM25 and semantic ranks: each branch contributes 1 / (${config?.rrf_c ?? 60} + rank), starting at rank 1. A missing branch contributes zero. Raw BM25 and cosine scores are not added.`,
    semantic: "Cosine similarity between the normalized question and chunk embeddings. A higher value means greater vector similarity, not that the source answers the question.",
    bm25: "BM25 rewards matching terms, accounting for their rarity, frequency and chunk length. This score has no percentage scale.",
    overlap: "Token overlap with bonuses for matches in the title, path and tags. A higher value means more weighted lexical matches.",
  };
  return `Score: ${value}. ${explanations[config?.retriever] || "Retrieval ranking score; the scoring method for this response is unavailable."} Higher scores rank first within the same query and configuration. This is not confidence, probability or proof of relevance: 0.03 does not mean 3%. Scores from different retrievers are not comparable. Branch ranks are not included in this response.`;
}

function scoreBadge(value, index, config) {
  const wrapper = textNode("span", "", "score-help");
  const badge = textNode("span", `Score ${value.toFixed(6)}`, "score");
  const tooltip = textNode("span", scoreHelp(value, config), "score-tooltip");
  tooltip.id = `score-tooltip-${index}`;
  tooltip.setAttribute("role", "tooltip");
  badge.tabIndex = 0;
  badge.setAttribute("aria-describedby", tooltip.id);
  badge.addEventListener("keydown", (event) => {
    if (event.key === "Escape") wrapper.classList.add("dismissed");
  });
  wrapper.addEventListener("mouseenter", () => wrapper.classList.remove("dismissed"));
  badge.addEventListener("focus", () => wrapper.classList.remove("dismissed"));
  wrapper.append(badge, tooltip);
  return wrapper;
}

async function request(path, options = {}, withRuntime = false) {
  const mutation = options.method === "POST" && path !== "/query";
  const response = await fetch(path, { ...options, signal: mutation ? undefined : AbortSignal.timeout(180000) });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error(`HTTP ${response.status}: invalid server response`);
  }
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(Array.isArray(detail) ? detail.map((item) => item.msg).join("; ") : detail || `HTTP ${response.status}`);
  }
  return withRuntime ? { payload, runtime: JSON.parse(response.headers.get("X-RAG-Runtime") || "null") } : payload;
}

function showError(id, error) {
  element(id).textContent = error ? error.message : "";
  element(id).hidden = !error;
}

function textNode(tag, text, className) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function list(id, values) {
  element(id).replaceChildren(...values.map((value) => textNode("li", value)));
}

function runtimeLabel(config) {
  if (!config) return "Runtime unavailable for this response";
  const parts = [config.retriever, `candidates x${config.candidate_multiplier}`];
  if (["bm25", "hybrid"].includes(config.retriever)) parts.push(`k1=${config.bm25_k1}`, `b=${config.bm25_b}`);
  if (config.rrf_c) parts.push(`RRF c=${config.rrf_c}, weights 1:1`);
  return parts.join(" / ");
}

function updateRuntimeFields() {
  const lexical = ["bm25", "hybrid"].includes(element("retriever").value);
  element("bm25-k1").disabled = !lexical;
  element("bm25-b").disabled = !lexical;
}

function renderRuntime(config) {
  runtimeConfig = config;
  element("active-runtime").textContent = `Active: ${runtimeLabel(config)}`;
  element("retriever").value = config.retriever;
  element("bm25-k1").value = config.bm25_k1;
  element("bm25-b").value = config.bm25_b;
  element("candidate-multiplier").value = config.candidate_multiplier;
  for (const option of element("retriever").options) {
    option.disabled = ["semantic", "hybrid"].includes(option.value) && !config.model_configured;
  }
  const settings = { Model: config.model || "None" };
  if (config.rrf_c) settings["RRF c / weights"] = `${config.rrf_c} / 1:1`;
  element("config").replaceChildren(...Object.entries(settings).flatMap(([name, value]) => [textNode("dt", name), textNode("dd", value)]));
  element("retriever-label").textContent = config.retriever;
  updateRuntimeFields();
}

async function refresh() {
  refreshing = true;
  updateBusy();
  showError("index-error", null);
  try {
    const [health, info, config] = await Promise.all([request("/healthz"), request("/info"), request("/ui/config")]);
    renderRuntime(config);
    element("health").textContent = health.status === "ok" ? "Online" : health.status;
    element("health").className = health.status === "ok" ? "online" : "";
    element("documents").textContent = info.indexed_documents;
    element("chunks").textContent = info.indexed_chunks;
    element("docs-dir").textContent = info.docs_dir;
    list("includes", info.include_folders.length ? info.include_folders : ["All folders"]);
    list("excludes", info.exclude_folders.length ? info.exclude_folders : ["None"]);
  } catch (error) {
    element("health").textContent = "Unavailable";
    element("health").className = "";
    showError("index-error", error);
  } finally {
    refreshing = false;
    updateBusy();
  }
}

function renderHistory() {
  element("history").replaceChildren(...history.map((entry) => {
    const item = document.createElement("li");
    const button = textNode("button", `${entry.question} [${entry.runtime?.retriever || "unknown"}]`);
    button.title = runtimeLabel(entry.runtime);
    button.type = "button";
    button.addEventListener("click", () => {
      element("question").value = entry.question;
      element("top-k").value = entry.top_k;
      element("question").focus();
    });
    item.append(button);
    return item;
  }));
}

function updateBusy() {
  const busy = querying || reindexing || applying || refreshing;
  element("search").disabled = busy || !runtimeConfig;
  element("reindex").disabled = busy || !runtimeConfig;
  element("refresh").disabled = busy;
  element("runtime-fields").disabled = busy || !runtimeConfig;
}

element("query-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (querying || reindexing || applying || refreshing) return;
  const question = element("question").value.trim();
  if (question.length < 3) {
    showError("query-error", new Error("Question must contain at least 3 characters."));
    return;
  }
  const body = { question, top_k: Number(element("top-k").value) };
  querying = true;
  updateBusy();
  element("search").textContent = "Searching...";
  element("results").hidden = true;
  element("empty").hidden = false;
  element("empty").textContent = "Searching...";
  element("timing").textContent = "";
  showError("query-error", null);
  const started = performance.now();
  try {
    const { payload: response, runtime } = await request("/query", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, true);
    lastResponse = { request: body, runtime, response };
    element("result-runtime").textContent = `Result: ${runtimeLabel(runtime)}`;
    element("timing").textContent = `${response.sources.length} sources / ${Math.round(performance.now() - started)} ms HTTP`;
    element("summary").textContent = response.summary;
    element("sources").replaceChildren(...response.sources.map((source, index) => {
      const article = textNode("article", "", "source");
      const heading = textNode("div", "", "source-head");
      heading.append(textNode("h3", `${index + 1}. ${source.title}`), scoreBadge(source.score, index, runtime));
      article.append(heading, textNode("p", source.path, "path"), textNode("p", source.snippet));
      return article;
    }));
    list("actions", response.recommended_actions);
    list("evidence", response.evidence);
    element("raw").textContent = JSON.stringify(response, null, 2);
    element("empty").hidden = true;
    element("results").hidden = false;
    history = [{ ...body, runtime }, ...history].slice(0, 8);
    renderHistory();
  } catch (error) {
    element("empty").textContent = "Query failed";
    showError("query-error", error);
  } finally {
    querying = false;
    updateBusy();
    element("search").textContent = "Search sources \u2192";
  }
});

element("reindex").addEventListener("click", async () => {
  if (querying || reindexing || applying || refreshing) return;
  reindexing = true;
  updateBusy();
  showError("index-error", null);
  element("index-status").textContent = "Reindexing...";
  try {
    const result = await request("/reindex", { method: "POST" });
    lastResponse = null;
    element("results").hidden = true;
    element("empty").hidden = false;
    element("empty").textContent = "Index updated";
    element("timing").textContent = "";
    element("index-status").textContent = `Indexed ${result.indexed_documents} documents / ${result.indexed_chunks} chunks`;
    await refresh();
  } catch (error) {
    element("index-status").textContent = "Reindex failed";
    showError("index-error", error);
  } finally {
    reindexing = false;
    updateBusy();
  }
});
element("retriever").addEventListener("change", updateRuntimeFields);
element("runtime-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (querying || reindexing || applying || refreshing) return;
  const settings = {
    retriever: element("retriever").value,
    bm25_k1: Number(element("bm25-k1").value),
    bm25_b: Number(element("bm25-b").value),
    candidate_multiplier: Number(element("candidate-multiplier").value),
  };
  applying = true;
  updateBusy();
  element("apply-runtime").textContent = "Applying...";
  element("runtime-status").textContent = "Building index...";
  showError("runtime-error", null);
  try {
    renderRuntime(await request("/ui/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) }));
    element("runtime-status").textContent = "Settings applied";
    await refresh();
  } catch (error) {
    element("runtime-status").textContent = "Apply not confirmed";
    showError("runtime-error", error);
  } finally {
    applying = false;
    updateBusy();
    element("apply-runtime").textContent = "Apply settings";
  }
});
element("refresh").addEventListener("click", refresh);
element("clear-history").addEventListener("click", () => { history = []; renderHistory(); });
element("download").addEventListener("click", () => {
  if (!lastResponse) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastResponse, null, 2)], { type: "application/json" }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "rag-query.json";
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
refresh();
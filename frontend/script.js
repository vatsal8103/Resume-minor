const state = {
  candidates: [], // { id, name, resumeText, source, parseError }
  results: null,
};

let nextId = 1;

// Only run recruitment functionality on index.html
if (document.getElementById('jdInput')) {
  // ---------------------------------------------------------------- status
  async function checkStatus() {
    const el = document.getElementById("statusLine");
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      el.textContent = `model ready · ${data.categories.length} role categories`;
    } catch (e) {
      el.textContent = "backend unreachable";
    }
  }
  checkStatus();

  // ---------------------------------------------------------------- dropzone
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileListEl = document.getElementById("fileList");

  dropzone.addEventListener("click", () => fileInput.click());

  ["dragover", "dragenter"].forEach(evt =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach(evt =>
    dropzone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    })
  );
  dropzone.addEventListener("drop", (e) => {
    handleFiles(e.dataTransfer.files);
  });
  fileInput.addEventListener("change", (e) => {
    handleFiles(e.target.files);
    fileInput.value = "";
  });

  function handleFiles(fileListRaw) {
    Array.from(fileListRaw).forEach(uploadFile);
  }

  async function uploadFile(file) {
    const id = nextId++;
    const candidate = {
      id,
      name: file.name.replace(/\.[^/.]+$/, ""),
      resumeText: "",
      source: file.name,
      status: "parsing",
    };
    state.candidates.push(candidate);
    renderFileList();

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/parse-file", { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "parse failed");
      candidate.resumeText = data.text;
      candidate.status = "ready";
    } catch (err) {
      candidate.status = "error";
      candidate.errorMsg = err.message;
    }
    renderFileList();
    updateAnalyzeState();
  }

  function renderFileList() {
    fileListEl.innerHTML = "";
    state.candidates.forEach((c) => {
      const li = document.createElement("li");
      const stateLabel = c.status === "ready" ? "parsed"
                        : c.status === "error" ? "failed"
                        : "reading…";
      const stateClass = c.status === "ready" ? "ready" : c.status === "error" ? "error" : "";
      li.innerHTML = `
        <span class="fname">${escapeHtml(c.name)}</span>
        <span style="display:flex; align-items:center; gap:8px;">
          <span class="fstate ${stateClass}">${stateLabel}</span>
          <button class="file-remove" data-id="${c.id}" aria-label="Remove">×</button>
        </span>
      `;
      fileListEl.appendChild(li);
    });
    fileListEl.querySelectorAll(".file-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = Number(btn.dataset.id);
        state.candidates = state.candidates.filter((c) => c.id !== id);
        renderFileList();
        updateAnalyzeState();
      });
    });
  }

  // ---------------------------------------------------------------- manual add
  document.getElementById("addManualBtn").addEventListener("click", () => {
    const nameEl = document.getElementById("manualName");
    const textEl = document.getElementById("manualText");
    const name = nameEl.value.trim() || `Candidate ${state.candidates.length + 1}`;
    const text = textEl.value.trim();
    if (!text) return;

    state.candidates.push({
      id: nextId++,
      name,
      resumeText: text,
      source: "pasted",
      status: "ready",
    });
    nameEl.value = "";
    textEl.value = "";
    renderFileList();
    updateAnalyzeState();
  });

  // ---------------------------------------------------------------- analyze
  const jdInput = document.getElementById("jdInput");
  const analyzeBtn = document.getElementById("analyzeBtn");
  const hintEl = document.getElementById("hint");

  jdInput.addEventListener("input", updateAnalyzeState);

  function updateAnalyzeState() {
    const hasJd = jdInput.value.trim().length > 0;
    const readyCandidates = state.candidates.filter((c) => c.status === "ready");
    analyzeBtn.disabled = !(hasJd && readyCandidates.length > 0);

    if (!hasJd) {
      hintEl.textContent = "Add a job description and at least one candidate to begin.";
    } else if (readyCandidates.length === 0) {
      hintEl.textContent = "Add at least one parsed candidate to begin.";
    } else {
      hintEl.textContent = `Ready to review ${readyCandidates.length} candidate(s).`;
    }
  }

  analyzeBtn.addEventListener("click", async () => {
    const jd_text = jdInput.value.trim();
    const candidates = state.candidates
      .filter((c) => c.status === "ready")
      .map((c) => ({ name: c.name, resume_text: c.resumeText }));

    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Reviewing…";

    try {
      const res = await fetch("/api/rank", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text, candidates }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "ranking failed");
      state.results = data.candidates;
      renderResults();
    } catch (err) {
      alert("Something went wrong: " + err.message);
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Review candidates →";
    }
  });

  // ---------------------------------------------------------------- results
  function scoreTier(score) {
    if (score >= 70) return "good";
    if (score >= 45) return "mid";
    return "low";
  }

  function renderResults() {
    const listEl = document.getElementById("candidateList");
    const emptyEl = document.getElementById("resultsEmpty");
    const countEl = document.getElementById("resultsCount");

    if (!state.results || state.results.length === 0) {
      emptyEl.hidden = false;
      listEl.innerHTML = "";
      countEl.textContent = "";
      return;
    }

    emptyEl.hidden = true;
    countEl.textContent = `${state.results.length} reviewed`;
    listEl.innerHTML = "";

    state.results.forEach((r) => {
      const tier = scoreTier(r.final_score);
      const card = document.createElement("div");
      card.className = "candidate-card";
      card.tabIndex = 0;

      const matchChips = (r.matched_skills || []).slice(0, 4)
        .map((s) => `<span class="chip match">${escapeHtml(s)}</span>`).join("");
      const missingChips = (r.missing_skills || []).slice(0, 3)
        .map((s) => `<span class="chip missing">${escapeHtml(s)}</span>`).join("");

      card.innerHTML = `
        <span class="candidate-rank">${String(r.rank).padStart(2, "0")}</span>
        <div class="candidate-main">
          <p class="candidate-name">${escapeHtml(r.name)}</p>
          <p class="candidate-meta">${escapeHtml(r.predicted_category)} · ${Math.round(r.category_confidence * 100)}% role-fit confidence</p>
          <div class="candidate-skills">${matchChips}${missingChips}</div>
        </div>
        <div class="stamp ${tier}">
          <span class="pct">${Math.round(r.final_score)}%</span>
          <span class="label">MATCH</span>
        </div>
      `;
      card.addEventListener("click", () => openDrawer(r));
      card.addEventListener("keypress", (e) => { if (e.key === "Enter") openDrawer(r); });
      listEl.appendChild(card);
    });
  }

  // ---------------------------------------------------------------- drawer
  const overlay = document.getElementById("drawerOverlay");
  const drawerContent = document.getElementById("drawerContent");

  function openDrawer(r) {
    const tier = scoreTier(r.final_score);
    const keywordChips = (r.keywords || []).slice(0, 10)
      .map((k) => `<span class="keyword-chip">${escapeHtml(k.term)}</span>`).join("");

    drawerContent.innerHTML = `
      <h2>${escapeHtml(r.name)}</h2>
      <p class="drawer-role">Predicted role: ${escapeHtml(r.predicted_category)}</p>

      <div class="score-breakdown">
        <div class="score-row"><span>Final score</span><span class="val">${r.final_score}/100</span></div>
        <div class="score-row"><span>JD similarity</span><span class="val">${r.jd_similarity !== null ? Math.round(r.jd_similarity * 100) + "%" : "—"}</span></div>
        <div class="score-row"><span>Skill overlap</span><span class="val">${r.skill_overlap !== null ? Math.round(r.skill_overlap * 100) + "%" : "—"}</span></div>
        <div class="score-row"><span>Role-fit confidence</span><span class="val">${Math.round(r.category_confidence * 100)}%</span></div>
      </div>

      <div class="drawer-section-title">Matched skills</div>
      <div class="keyword-list">
        ${(r.matched_skills || []).map(s => `<span class="chip match">${escapeHtml(s)}</span>`).join("") || '<span class="candidate-meta">None detected</span>'}
      </div>

      <div class="drawer-section-title">Missing skills (in JD, not in résumé)</div>
      <div class="keyword-list">
        ${(r.missing_skills || []).map(s => `<span class="chip missing">${escapeHtml(s)}</span>`).join("") || '<span class="candidate-meta">None — full coverage</span>'}
      </div>

      <div class="drawer-section-title">Top résumé keywords</div>
      <div class="keyword-list">${keywordChips}</div>
    `;
    overlay.hidden = false;
  }

  document.getElementById("drawerClose").addEventListener("click", () => overlay.hidden = true);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.hidden = true; });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") overlay.hidden = true; });
}

// ---------------------------------------------------------------- utils
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------------------------------------------------------------- dropzone
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const fileListEl = document.getElementById("fileList");

dropzone.addEventListener("click", () => fileInput.click());

["dragover", "dragenter"].forEach(evt =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach(evt =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  handleFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", (e) => {
  handleFiles(e.target.files);
  fileInput.value = "";
});

function handleFiles(fileListRaw) {
  Array.from(fileListRaw).forEach(uploadFile);
}

async function uploadFile(file) {
  const id = nextId++;
  const candidate = {
    id,
    name: file.name.replace(/\.[^/.]+$/, ""),
    resumeText: "",
    source: file.name,
    status: "parsing",
  };
  state.candidates.push(candidate);
  renderFileList();

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/parse-file", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "parse failed");
    candidate.resumeText = data.text;
    candidate.status = "ready";
  } catch (err) {
    candidate.status = "error";
    candidate.errorMsg = err.message;
  }
  renderFileList();
  updateAnalyzeState();
}

function renderFileList() {
  fileListEl.innerHTML = "";
  state.candidates.forEach((c) => {
    const li = document.createElement("li");
    const stateLabel = c.status === "ready" ? "parsed"
                      : c.status === "error" ? "failed"
                      : "reading…";
    const stateClass = c.status === "ready" ? "ready" : c.status === "error" ? "error" : "";
    li.innerHTML = `
      <span class="fname">${escapeHtml(c.name)}</span>
      <span style="display:flex; align-items:center; gap:8px;">
        <span class="fstate ${stateClass}">${stateLabel}</span>
        <button class="file-remove" data-id="${c.id}" aria-label="Remove">×</button>
      </span>
    `;
    fileListEl.appendChild(li);
  });
  fileListEl.querySelectorAll(".file-remove").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.dataset.id);
      state.candidates = state.candidates.filter((c) => c.id !== id);
      renderFileList();
      updateAnalyzeState();
    });
  });
}

// ---------------------------------------------------------------- manual add
document.getElementById("addManualBtn").addEventListener("click", () => {
  const nameEl = document.getElementById("manualName");
  const textEl = document.getElementById("manualText");
  const name = nameEl.value.trim() || `Candidate ${state.candidates.length + 1}`;
  const text = textEl.value.trim();
  if (!text) return;

  state.candidates.push({
    id: nextId++,
    name,
    resumeText: text,
    source: "pasted",
    status: "ready",
  });
  nameEl.value = "";
  textEl.value = "";
  renderFileList();
  updateAnalyzeState();
});

// ---------------------------------------------------------------- analyze
const jdInput = document.getElementById("jdInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const hintEl = document.getElementById("hint");

jdInput.addEventListener("input", updateAnalyzeState);

function updateAnalyzeState() {
  const hasJd = jdInput.value.trim().length > 0;
  const readyCandidates = state.candidates.filter((c) => c.status === "ready");
  analyzeBtn.disabled = !(hasJd && readyCandidates.length > 0);

  if (!hasJd) {
    hintEl.textContent = "Add a job description and at least one candidate to begin.";
  } else if (readyCandidates.length === 0) {
    hintEl.textContent = "Add at least one parsed candidate to begin.";
  } else {
    hintEl.textContent = `Ready to review ${readyCandidates.length} candidate(s).`;
  }
}

analyzeBtn.addEventListener("click", async () => {
  const jd_text = jdInput.value.trim();
  const candidates = state.candidates
    .filter((c) => c.status === "ready")
    .map((c) => ({ name: c.name, resume_text: c.resumeText }));

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = "Reviewing…";

  try {
    const res = await fetch("/api/rank", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ jd_text, candidates }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "ranking failed");
    state.results = data.candidates;
    renderResults();
  } catch (err) {
    alert("Something went wrong: " + err.message);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = "Review candidates →";
  }
});

// ---------------------------------------------------------------- results
function scoreTier(score) {
  if (score >= 70) return "good";
  if (score >= 45) return "mid";
  return "low";
}

function renderResults() {
  const listEl = document.getElementById("candidateList");
  const emptyEl = document.getElementById("resultsEmpty");
  const countEl = document.getElementById("resultsCount");

  if (!state.results || state.results.length === 0) {
    emptyEl.hidden = false;
    listEl.innerHTML = "";
    countEl.textContent = "";
    return;
  }

  emptyEl.hidden = true;
  countEl.textContent = `${state.results.length} reviewed`;
  listEl.innerHTML = "";

  state.results.forEach((r) => {
    const tier = scoreTier(r.final_score);
    const card = document.createElement("div");
    card.className = "candidate-card";
    card.tabIndex = 0;

    const matchChips = (r.matched_skills || []).slice(0, 4)
      .map((s) => `<span class="chip match">${escapeHtml(s)}</span>`).join("");
    const missingChips = (r.missing_skills || []).slice(0, 3)
      .map((s) => `<span class="chip missing">${escapeHtml(s)}</span>`).join("");

    card.innerHTML = `
      <span class="candidate-rank">${String(r.rank).padStart(2, "0")}</span>
      <div class="candidate-main">
        <p class="candidate-name">${escapeHtml(r.name)}</p>
        <p class="candidate-meta">${escapeHtml(r.predicted_category)} · ${Math.round(r.category_confidence * 100)}% role-fit confidence</p>
        <div class="candidate-skills">${matchChips}${missingChips}</div>
      </div>
      <div class="stamp ${tier}">
        <span class="pct">${Math.round(r.final_score)}%</span>
        <span class="label">MATCH</span>
      </div>
    `;
    card.addEventListener("click", () => openDrawer(r));
    card.addEventListener("keypress", (e) => { if (e.key === "Enter") openDrawer(r); });
    listEl.appendChild(card);
  });
}

// ---------------------------------------------------------------- drawer
const overlay = document.getElementById("drawerOverlay");
const drawerContent = document.getElementById("drawerContent");

function openDrawer(r) {
  const tier = scoreTier(r.final_score);
  const keywordChips = (r.keywords || []).slice(0, 10)
    .map((k) => `<span class="keyword-chip">${escapeHtml(k.term)}</span>`).join("");

  drawerContent.innerHTML = `
    <h2>${escapeHtml(r.name)}</h2>
    <p class="drawer-role">Predicted role: ${escapeHtml(r.predicted_category)}</p>

    <div class="score-breakdown">
      <div class="score-row"><span>Final score</span><span class="val">${r.final_score}/100</span></div>
      <div class="score-row"><span>JD similarity</span><span class="val">${r.jd_similarity !== null ? Math.round(r.jd_similarity * 100) + "%" : "—"}</span></div>
      <div class="score-row"><span>Skill overlap</span><span class="val">${r.skill_overlap !== null ? Math.round(r.skill_overlap * 100) + "%" : "—"}</span></div>
      <div class="score-row"><span>Role-fit confidence</span><span class="val">${Math.round(r.category_confidence * 100)}%</span></div>
    </div>

    <div class="drawer-section-title">Matched skills</div>
    <div class="keyword-list">
      ${(r.matched_skills || []).map(s => `<span class="chip match">${escapeHtml(s)}</span>`).join("") || '<span class="candidate-meta">None detected</span>'}
    </div>

    <div class="drawer-section-title">Missing skills (in JD, not in résumé)</div>
    <div class="keyword-list">
      ${(r.missing_skills || []).map(s => `<span class="chip missing">${escapeHtml(s)}</span>`).join("") || '<span class="candidate-meta">None — full coverage</span>'}
    </div>

    <div class="drawer-section-title">Top résumé keywords</div>
    <div class="keyword-list">${keywordChips}</div>
  `;
  overlay.hidden = false;
}

document.getElementById("drawerClose").addEventListener("click", () => overlay.hidden = true);
overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.hidden = true; });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") overlay.hidden = true; });

// ---------------------------------------------------------------- utils
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

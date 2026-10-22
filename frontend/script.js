// Simplified script for main index.html functionality
// Handles resume upload, analysis, and results display

// State management for the main page
const state = {
  candidates: [], // { id, name, resumeText, source, parseError }
  results: null,
};

let nextId = 1;

// Utility function
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ===================================================================
// ENTERPRISE AUTHENTICATION & SESSION MANAGER
// Solves cross-tab multi-role isolation (Recruiter vs Candidate)
// ===================================================================
const Auth = {
  // Determine role required by current page
  getPageRole() {
    const page = window.location.pathname.split('/').pop() || 'index.html';
    const recruiterPages = [
      'recruiter-dashboard.html',
      'manage-jobs.html',
      'manage-candidates.html',
      'interview-questions.html',
      'analytics.html',
      'document-authenticator.html'
    ];
    const candidatePages = [
      'candidate-dashboard.html',
      'my-profile.html',
      'resume-checker.html',
      'job-search.html',
      'my-applications.html',
      'roadmap.html'
    ];

    if (recruiterPages.includes(page)) return 'recruiter';
    if (candidatePages.includes(page)) return 'candidate';

    // For login, signup, settings, index, check tab's active role
    return sessionStorage.getItem('active_role') || null;
  },

  // Save session with role-based namespacing & tab binding
  saveSession(data) {
    const role = (data.role === 'recruiter' || data.role === 'admin') ? 'recruiter' : 'candidate';
    const sessionKey = role + '_session';
    const sessionObj = {
      id: strVal(data.id || data.userId),
      userId: strVal(data.id || data.userId),
      username: data.username || '',
      fullName: data.full_name || data.fullName || 'User',
      email: data.email || '',
      role: data.role || role
    };

    // 1. Save in role-isolated persistent storage (does not overwrite other role)
    localStorage.setItem(sessionKey, JSON.stringify(sessionObj));

    // 2. Bind current browser tab to this specific role and session
    sessionStorage.setItem('active_role', role);
    sessionStorage.setItem('current_session', JSON.stringify(sessionObj));

    // 3. Sync to legacy storage for current page context
    this.syncToLegacy(sessionObj);

    return sessionObj;
  },

  // Retrieve user session for a specific role or the current page
  getUser(targetRole) {
    const role = targetRole || this.getPageRole();
    let session = null;

    // A. Check tab's sessionStorage if role matches current tab
    const tabRole = sessionStorage.getItem('active_role');
    const tabSession = sessionStorage.getItem('current_session');
    if (tabSession) {
      try {
        const parsed = JSON.parse(tabSession);
        if (!role || tabRole === role || parsed.role === role) {
          session = parsed;
        }
      } catch (e) {}
    }

    // B. Check role-namespaced localStorage
    if (!session && role) {
      const raw = localStorage.getItem(role + '_session');
      if (raw) {
        try {
          session = JSON.parse(raw);
          // Bind this tab to this role
          sessionStorage.setItem('active_role', role);
          sessionStorage.setItem('current_session', raw);
        } catch (e) {}
      }
    }

    // C. Fallback: check other role if not strictly locked
    if (!session) {
      const otherRole = role === 'recruiter' ? 'candidate' : 'recruiter';
      const otherRaw = localStorage.getItem(otherRole + '_session');
      if (otherRaw && !role) {
        try {
          session = JSON.parse(otherRaw);
        } catch (e) {}
      }
    }

    // D. Fallback to generic localStorage
    if (!session) {
      const genericId = localStorage.getItem('userId');
      if (genericId) {
        session = {
          id: genericId,
          userId: genericId,
          username: localStorage.getItem('username') || '',
          fullName: localStorage.getItem('fullName') || 'User',
          email: localStorage.getItem('email') || '',
          role: localStorage.getItem('role') || role || 'user'
        };
      }
    }

    // Always keep current tab's legacy keys synchronized with the resolved session
    if (session) {
      this.syncToLegacy(session);
    }

    return session;
  },

  // Sync session to legacy top-level keys for backward compatibility
  syncToLegacy(session) {
    if (!session) return;
    localStorage.setItem('userId', session.userId || session.id || '');
    localStorage.setItem('fullName', session.fullName || '');
    localStorage.setItem('username', session.username || '');
    localStorage.setItem('role', session.role || '');
    if (session.email) localStorage.setItem('email', session.email);
  },

  // Logout only the role associated with the current page or tab
  logout(targetRole) {
    const role = targetRole || this.getPageRole();
    if (role) {
      localStorage.removeItem(role + '_session');
    }
    sessionStorage.removeItem('active_role');
    sessionStorage.removeItem('current_session');

    // Only clear legacy keys if they matched this role
    if (localStorage.getItem('role') === role) {
      localStorage.removeItem('userId');
      localStorage.removeItem('fullName');
      localStorage.removeItem('username');
      localStorage.removeItem('role');
      localStorage.removeItem('email');
    }

    window.location.href = 'index.html';
  },

  // Check auth and handle redirects with strict role boundary
  checkAuth(requiredRole) {
    const pageRole = requiredRole || this.getPageRole();
    let user = this.getUser(pageRole);

    if (!user || !user.userId) {
      window.location.href = 'login.html';
      return false;
    }

    // Strict role isolation
    const userRole = (user.role === 'recruiter' || user.role === 'admin') ? 'recruiter' : 'candidate';
    if (pageRole === 'recruiter' && userRole === 'candidate') {
      window.location.href = 'candidate-dashboard.html';
      return false;
    }
    if (pageRole === 'candidate' && userRole === 'recruiter') {
      window.location.href = 'recruiter-dashboard.html';
      return false;
    }

    return true;
  }
};

function strVal(v) {
  return v ? String(v) : '';
}

// Page-specific initialization
document.addEventListener('DOMContentLoaded', function() {
  const pageRole = Auth.getPageRole();
  if (pageRole) {
    // Automatically resolve and sync the correct role's session for this page
    const user = Auth.getUser(pageRole);
    if (user && user.fullName) {
      // Auto-update any topbar elements if present
      const nameEl = document.getElementById('userFullName');
      if (nameEl) nameEl.textContent = user.fullName;
    }
  }

  // Check if current page is protected
  if (isAuthProtectedPage()) {
    if (!Auth.checkAuth()) return;
  }

  // Wire topbar logo navigation to the appropriate dashboard
  const wordmarks = document.querySelectorAll('.topbar .wordmark');
  wordmarks.forEach(wm => {
    wm.style.cursor = 'pointer';
    wm.addEventListener('click', () => {
      const curRole = Auth.getPageRole();
      const curUser = Auth.getUser(curRole);
      if (curUser && curUser.userId) {
        if (curUser.role === 'recruiter' || curUser.role === 'admin') {
          window.location.href = 'recruiter-dashboard.html';
        } else {
          window.location.href = 'candidate-dashboard.html';
        }
      } else {
        window.location.href = 'index.html';
      }
    });
  });

  // Initialize recruitment features if on index.html
  initRecruitmentFeatures();

  // Update status line
  updateStatusLine();
});

// Check if current page requires authentication
function isAuthProtectedPage() {
  const protectedPages = [
    'recruiter-dashboard.html',
    'manage-jobs.html',
    'manage-candidates.html',
    'candidate-dashboard.html',
    'my-profile.html',
    'resume-checker.html',
    'my-applications.html',
    'document-authenticator.html',
    'analytics.html',
    'interview-questions.html'
  ];
  const currentPage = window.location.pathname.split('/').pop() || 'index.html';
  return protectedPages.includes(currentPage);
}

// Legacy checkAuth wrapper
function checkAuth() {
  return Auth.checkAuth();
}

// Update status line with model info
async function updateStatusLine() {
  const el = document.getElementById("statusLine");
  if (!el) return;

  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    el.textContent = `model ready · ${data.categories.length} role categories`;
    if (data.model_loaded) {
      el.style.animation = 'pulse 2s infinite';
      el.style.color = 'var(--primary)';
    }
  } catch (e) {
    el.textContent = "backend unreachable";
    el.style.color = 'var(--error)';
  }
}

// Main recruitment features (upload, analyze, results)
function initRecruitmentFeatures() {
  // Status check
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

  // Dropzone functionality
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const fileListEl = document.getElementById("fileList");

  if (dropzone) {
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
      e.preventDefault();
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

    // Manual add
    const manualAddBtn = document.getElementById("addManualBtn");
    if (manualAddBtn) {
      manualAddBtn.addEventListener("click", () => {
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
    }

    // Analyze button
    const jdInput = document.getElementById("jdInput");
    const analyzeBtn = document.getElementById("analyzeBtn");
    const hintEl = document.getElementById("hint");

    if (jdInput && analyzeBtn && hintEl) {
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
    }

    // Results rendering
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

        const matchChips = (r.matched_skills || []).slice(0, 4)
          .map((s) => `<span class="chip match">${escapeHtml(s)}</span>`).join("");
        const missingChips = (r.missing_skills || []).slice(0, 3)
          .map((s) => `<span class="chip missing">${escapeHtml(s)}</span>`).join("");

        card.innerHTML = `
          <div class="candidate-rank">${String(r.rank).padStart(2, "0")}</div>
          <div class="candidate-main">
            <h3 class="candidate-name">${escapeHtml(r.name)}</h3>
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

    // Candidate detail drawer
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

        <div class="drawer-section-actions">
          <button id="backgroundCheckBtn" class="btn-primary btn-wide">
            Run Background Check
          </button>
        </div>
      `;
      overlay.hidden = false;

      // Add event listener for background check button
      const backgroundCheckBtn = document.getElementById('backgroundCheckBtn');
      if (backgroundCheckBtn) {
        backgroundCheckBtn.addEventListener('click', () => {
          initiateBackgroundCheck(r);
        });
      }
    }

    const drawerClose = document.getElementById("drawerClose");
    if (drawerClose) {
      drawerClose.addEventListener("click", () => overlay.hidden = true);
    }
    const drawerOverlay = document.getElementById("drawerOverlay");
    if (drawerOverlay) {
      drawerOverlay.addEventListener("click", (e) => { if (e.target === drawerOverlay) overlay.hidden = true; });
    }
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") {
      const overlay = document.getElementById("drawerOverlay");
      if (overlay) overlay.hidden = true;
    }});
  }
}

// Background check functionality
async function initiateBackgroundCheck(candidateData) {
  // Find candidate ID from our state or search for it
  let candidateId = null;

  // Try to find candidate by name in our state
  for (const candidate of state.candidates) {
    if (candidate.name === candidateData.name) {
      candidateId = candidate.id;
      break;
    }
  }

  // If not found in state, we need to search via API
  if (!candidateId) {
    try {
      const response = await fetch(`/api/candidates?search=${encodeURIComponent(candidateData.name)}`);
      const data = await response.json();
      if (data.candidates && data.candidates.length > 0) {
        candidateId = data.candidates[0].id;
      }
    } catch (error) {
      console.error('Failed to search for candidate:', error);
    }
  }

  if (!candidateId) {
    alert('Unable to find candidate ID for background check. Please try again.');
    return;
  }

  try {
    // Show loading state
    const drawerContent = document.getElementById('drawerContent');
    drawerContent.innerHTML += `
      <div class="background-check-loading">
        <p>Running background check...</p>
        <div class="spinner"></div>
      </div>
    `;

    // Call background check API
    const response = await fetch('/api/background-check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        candidate_id: candidateId,
        check_type: 'standard'
      })
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || 'Background check failed');
    }

    // Display results
    displayBackgroundCheckResults(result, candidateData);

  } catch (error) {
    alert('Background check failed: ' + error.message);
    // Reset to normal view
    openDrawer(candidateData);
  }
}

function displayBackgroundCheckResults(results, candidateData) {
  const drawerContent = document.getElementById('drawerContent');

  const riskLevelClass = results.risk_level === 'low' ? 'risk-low' :
                        results.risk_level === 'medium' ? 'risk-medium' : 'risk-high';

  drawerContent.innerHTML = `
    <h2>${escapeHtml(candidateData.name)}</h2>
    <p class="drawer-role">Background Check Results</p>

    <div class="background-check-results">
      <div class="risk-indicator ${riskLevelClass}">
        <span class="risk-label">Risk Level: ${results.risk_level.toUpperCase()}</span>
        <span class="risk-score">${results.overall_score}%</span>
      </div>

      <div class="check-details">
        ${Object.entries(results.checks).map(([checkName, checkData]) => `
          <div class="check-item">
            <h4>${checkName.replace('_', ' ').toUpperCase()}</h4>
            <div class="check-score">${checkData.status} (${checkData.score}%)</div>
            <p class="check-details">${checkData.details}</p>
          </div>
        `).join('')}
      </div>

      <div class="recommendations">
        <h3>Recommendations</h3>
        <ul>
          ${results.recommendations.map(rec => `<li>${escapeHtml(rec)}</li>`).join('')}
        </ul>
      </div>

      <button onclick="openDrawer(${JSON.stringify(candidateData)})" class="btn-ghost">
        Back to Candidate Profile
      </button>
    </div>
  `;
}
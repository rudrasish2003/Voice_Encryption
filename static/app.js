"use strict";

/* ===================== Config & state ===================== */
const API_BASE = window.location.origin; // same origin as this page, served by the FastAPI app
const LOW_QUALITY_THRESHOLD = 0.8; // library "low-confidence" stat cutoff, not a backend setting

let token = localStorage.getItem("vb_token") || null;
let currentUsername = localStorage.getItem("vb_username") || "";

let peopleCache = [];
let regSelectedFile = null; // File or Blob chosen for registration
let identifySelectedFile = null;
let lastJobResult = null; // for JSON export

let mediaRecorder = null;
let recordedChunks = [];
let recordTimerInterval = null;
let recordStartTime = 0;

/* ===================== Component loading (zero-CORS fallback) ===================== */
const TEMPLATE_FOR_SLOT = {
  "slot-header": "tpl-header",
  "slot-login": "tpl-login",
  "slot-upload": "tpl-upload",
  "slot-library": "tpl-library",
  "slot-analysis": "tpl-analysis",
  "slot-footer": "tpl-footer",
};

async function loadComponents() {
  const slots = document.querySelectorAll("[data-component]");
  await Promise.all(
    Array.from(slots).map(async (slot) => {
      const path = slot.getAttribute("data-component");
      try {
        const res = await fetch(path);
        if (!res.ok) throw new Error("HTTP " + res.status);
        slot.innerHTML = await res.text();
      } catch (err) {
        const tplId = TEMPLATE_FOR_SLOT[slot.id];
        const tpl = tplId ? document.getElementById(tplId) : null;
        if (tpl) {
          slot.innerHTML = "";
          slot.appendChild(tpl.content.cloneNode(true));
        } else {
          console.error("Failed to load component and no fallback template for", slot.id, err);
        }
      }
    })
  );
}

/* ===================== Toasts ===================== */
function toast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = "toast " + type;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => el.remove(), 4500);
}

/* ===================== API helper ===================== */
async function apiFetch(path, options = {}) {
  const headers = Object.assign({}, options.headers || {});
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API_BASE + path, { ...options, headers });
  if (res.status === 401) {
    toast("Session expired — please sign in again.", "error");
    logout();
    throw new Error("unauthorized");
  }
  return res;
}

function extractErrorMessage(detail, fallback) {
  if (!detail) return fallback;
  if (typeof detail === "string") return detail;
  if (typeof detail === "object") return detail.message || JSON.stringify(detail);
  return fallback;
}

/* ===================== Auth ===================== */
function setLoggedInUI(username) {
  document.getElementById("user-badge")?.classList.remove("hidden");
  document.getElementById("user-badge-desktop")?.classList.remove("hidden");
  document.getElementById("main-nav-tabs")?.classList.remove("hidden");
  const nameEls = [
    document.getElementById("user-display-name"),
    document.getElementById("user-display-name-desktop"),
  ];
  nameEls.forEach((el) => el && (el.textContent = username || "User"));

  document.getElementById("tab-login")?.classList.remove("active");
  switchTab("tab-upload");
}

function setLoggedOutUI() {
  document.getElementById("user-badge")?.classList.add("hidden");
  document.getElementById("user-badge-desktop")?.classList.add("hidden");
  document.getElementById("main-nav-tabs")?.classList.add("hidden");
  document.querySelectorAll(".tab-view").forEach((el) => el.classList.remove("active"));
  document.getElementById("tab-login")?.classList.add("active");
}

function logout() {
  token = null;
  currentUsername = "";
  localStorage.removeItem("vb_token");
  localStorage.removeItem("vb_username");
  setLoggedOutUI();
}

function wireLogin() {
  const form = document.getElementById("login-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;
    const submitBtn = document.getElementById("btn-submit-login");
    submitBtn.disabled = true;
    try {
      const body = new URLSearchParams();
      body.set("username", username);
      body.set("password", password);
      const res = await fetch(API_BASE + "/api/v1/token", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(extractErrorMessage(data?.detail, "Invalid credentials"));

      token = data.access_token;
      currentUsername = username;
      localStorage.setItem("vb_token", token);
      localStorage.setItem("vb_username", username);
      toast("Signed in as " + username, "success");
      setLoggedInUI(username);
      await refreshLibrary();
    } catch (err) {
      toast("Sign-in failed: " + err.message, "error");
    } finally {
      submitBtn.disabled = false;
    }
  });

  document.getElementById("toggle-password")?.addEventListener("click", () => {
    const input = document.getElementById("login-password");
    const eyeOpen = document.querySelector("#toggle-password .eye-open");
    const eyeClosed = document.querySelector("#toggle-password .eye-closed");
    const show = input.type === "password";
    input.type = show ? "text" : "password";
    eyeOpen?.classList.toggle("hidden", show);
    eyeClosed?.classList.toggle("hidden", !show);
  });

  // Only fills the username -- the real admin password lives in the server's .env
  // and must never be embedded in client-side JS.
  document.getElementById("btn-fill-demo")?.addEventListener("click", () => {
    document.getElementById("login-username").value = "admin";
    document.getElementById("login-password").focus();
    toast("Username filled — enter the ADMIN_PASSWORD from your .env", "info");
  });

  document.querySelectorAll("#btn-logout-mobile, #btn-logout-desktop").forEach((btn) => {
    btn.addEventListener("click", () => {
      logout();
      toast("Signed out", "info");
    });
  });
}

/* ===================== Tabs ===================== */
function switchTab(tabId) {
  document.querySelectorAll(".tab-view").forEach((el) => {
    el.classList.toggle("active", el.id === tabId);
  });
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  if (tabId === "tab-library") refreshLibrary();
}

function wireTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  document.getElementById("btn-go-to-upload")?.addEventListener("click", () => switchTab("tab-upload"));
  document.getElementById("btn-empty-upload-action")?.addEventListener("click", () => switchTab("tab-upload"));
}

/* ===================== Shared helpers ===================== */
function formatBytes(bytes) {
  if (!bytes && bytes !== 0) return "unknown size";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Wires a drop-zone + hidden file input + browse button as one reusable control. */
function attachDropZone({ dropZoneId, fileInputId, browseButtonId, onFile }) {
  const dropZone = document.getElementById(dropZoneId);
  const fileInput = document.getElementById(fileInputId);
  const browseBtn = document.getElementById(browseButtonId);
  if (!dropZone || !fileInput) return;

  browseBtn?.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });
  dropZone.addEventListener("click", () => fileInput.click());

  ["dragenter", "dragover"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    })
  );
  dropZone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files?.[0];
    if (file) onFile(file);
  });
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) onFile(file);
  });
}

/* ===================== Register Voice tab ===================== */
function wireRegisterTab() {
  attachDropZone({
    dropZoneId: "reg-drop-zone",
    fileInputId: "reg-file-input",
    browseButtonId: "reg-btn-browse-file",
    onFile: setRegFile,
  });

  document.getElementById("reg-btn-clear-file")?.addEventListener("click", (e) => {
    e.stopPropagation();
    clearRegFile();
  });

  document.getElementById("mode-pill-upload")?.addEventListener("click", () => setRegMode("upload"));
  document.getElementById("mode-pill-record")?.addEventListener("click", () => setRegMode("record"));

  document.getElementById("btn-toggle-record")?.addEventListener("click", toggleRecording);

  document.getElementById("voice-upload-form")?.addEventListener("submit", submitRegistration);
}

function setRegMode(mode) {
  document.getElementById("mode-pill-upload")?.classList.toggle("active", mode === "upload");
  document.getElementById("mode-pill-record")?.classList.toggle("active", mode === "record");
  document.getElementById("upload-panel")?.classList.toggle("hidden", mode !== "upload");
  document.getElementById("record-panel")?.classList.toggle("hidden", mode !== "record");
}

function setRegFile(file) {
  regSelectedFile = file;
  document.getElementById("reg-drop-zone").classList.add("hidden");
  const card = document.getElementById("reg-file-preview-card");
  card.classList.remove("hidden");
  document.getElementById("reg-preview-filename").textContent = file.name || "recording.webm";
  document.getElementById("reg-preview-meta").textContent = formatBytes(file.size) + " • Ready";

  const player = document.getElementById("reg-audio-preview-player");
  if (player) {
    player.src = URL.createObjectURL(file);
    player.classList.remove("hidden");
  }
}

function clearRegFile() {
  regSelectedFile = null;
  document.getElementById("reg-drop-zone").classList.remove("hidden");
  document.getElementById("reg-file-preview-card").classList.add("hidden");
  const fileInput = document.getElementById("reg-file-input");
  if (fileInput) fileInput.value = "";
  const player = document.getElementById("reg-audio-preview-player");
  if (player) {
    player.pause();
    player.removeAttribute("src");
    player.classList.add("hidden");
  }
}

async function toggleRecording() {
  const btn = document.getElementById("btn-toggle-record");
  const label = document.getElementById("btn-record-label");
  const visualizer = document.getElementById("record-visualizer");
  const status = document.getElementById("record-status");

  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(recordTimerInterval);
      visualizer?.classList.remove("recording");
      btn.classList.remove("active");
      label.textContent = "Start Recording";
      status.textContent = "Recording captured — ready to register.";

      const blob = new Blob(recordedChunks, { type: "audio/webm" });
      const file = new File([blob], "live_recording.webm", { type: "audio/webm" });
      setRegFile(file);
    };

    mediaRecorder.start();
    recordStartTime = Date.now();
    document.getElementById("record-timer").textContent = "00:00";
    recordTimerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
      document.getElementById("record-timer").textContent = formatTime(elapsed);
    }, 250);

    visualizer?.classList.add("recording");
    btn.classList.add("active");
    label.textContent = "Stop Recording";
    status.textContent = "Recording… speak clearly, aim for at least 30 seconds.";
  } catch (err) {
    toast("Microphone access failed: " + err.message, "error");
  }
}

async function submitRegistration(e) {
  e.preventDefault();
  const name = document.getElementById("reg-name").value.trim();
  const consentBy = document.getElementById("reg-consent-by").value.trim();
  const consentMethod = document.getElementById("reg-consent-method").value;
  const submitBtn = document.getElementById("btn-save-to-library");

  if (!name || !consentBy) {
    toast("Please fill in person name and consent fields.", "error");
    return;
  }
  if (!regSelectedFile) {
    toast("Please upload or record an audio clip first.", "error");
    return;
  }

  const form = new FormData();
  form.set("name", name);
  form.set("consent_given_by", consentBy);
  form.set("consent_method", consentMethod);
  form.append("files", regSelectedFile, regSelectedFile.name || "clip.webm");

  submitBtn.disabled = true;
  submitBtn.querySelector("span").textContent = "Registering…";
  try {
    const res = await apiFetch("/api/v1/people", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(extractErrorMessage(data?.detail, "Registration failed"));

    toast(`Registered "${data.name}" (quality ${(data.quality_score * 100).toFixed(0)}%).`, "success");
    document.getElementById("voice-upload-form").reset();
    clearRegFile();
    switchTab("tab-library");
  } catch (err) {
    toast("Registration failed: " + err.message, "error");
  } finally {
    submitBtn.disabled = false;
    submitBtn.querySelector("span").textContent = "Register Voice";
  }
}

/* ===================== Library tab ===================== */
async function refreshLibrary() {
  if (!token) return;
  try {
    const res = await apiFetch("/api/v1/people");
    if (!res.ok) throw new Error("HTTP " + res.status);
    peopleCache = await res.json();
  } catch (err) {
    console.error("Failed to load library", err);
    return;
  }
  renderLibrary();
  updateLibraryBadge();
}

function updateLibraryBadge() {
  const badge = document.getElementById("library-count-badge");
  if (badge) badge.textContent = String(peopleCache.length);
}

function renderLibrary() {
  const grid = document.getElementById("voice-cards-grid");
  const emptyState = document.getElementById("library-empty-state");
  const searchTerm = (document.getElementById("library-search")?.value || "").toLowerCase();
  if (!grid) return;

  const filtered = peopleCache.filter((p) => p.name.toLowerCase().includes(searchTerm));

  document.getElementById("stat-total-voices").textContent = String(peopleCache.length);
  const avgQuality = peopleCache.length
    ? peopleCache.reduce((sum, p) => sum + p.quality_score, 0) / peopleCache.length
    : 0;
  document.getElementById("stat-total-size").textContent = (avgQuality * 100).toFixed(0) + "%";
  const lowConfidenceCount = peopleCache.filter((p) => p.quality_score < LOW_QUALITY_THRESHOLD).length;
  document.getElementById("stat-analyzed-count").textContent = String(lowConfidenceCount);

  if (peopleCache.length === 0) {
    grid.innerHTML = "";
    emptyState?.classList.remove("hidden");
    return;
  }
  emptyState?.classList.add("hidden");

  if (filtered.length === 0) {
    grid.innerHTML = `<p class="subtitle">No matches for "${escapeHtml(searchTerm)}".</p>`;
    return;
  }

  grid.innerHTML = filtered
    .map(
      (p) => `
    <div class="voice-card">
      <div class="voice-card-top">
        <span class="voice-card-name">${escapeHtml(p.name)}</span>
        <span class="metric-badge ${p.quality_score >= LOW_QUALITY_THRESHOLD ? "success" : ""}">${(p.quality_score * 100).toFixed(0)}% quality</span>
      </div>
      <div class="voice-card-meta">
        <span>Registered ${escapeHtml(formatDate(p.created_at))}</span>
        <span>${escapeHtml(p.consent.given_by)} • ${escapeHtml(p.consent.method)}</span>
      </div>
      <div class="voice-card-actions">
        <button class="btn btn-secondary btn-sm" data-person-id="${p.id}" data-person-name="${escapeHtml(p.name)}">Delete</button>
      </div>
    </div>
  `
    )
    .join("");

  grid.querySelectorAll("button[data-person-id]").forEach((btn) => {
    btn.addEventListener("click", () => deletePerson(btn.dataset.personId, btn.dataset.personName));
  });
}

async function deletePerson(id, name) {
  if (!confirm(`Delete "${name}" and withdraw consent? This cannot be undone.`)) return;
  try {
    const res = await apiFetch("/api/v1/people/" + id, { method: "DELETE" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    toast(`Deleted "${name}".`, "success");
    await refreshLibrary();
  } catch (err) {
    toast("Delete failed: " + err.message, "error");
  }
}

function wireLibraryTab() {
  document.getElementById("library-search")?.addEventListener("input", renderLibrary);
}

/* ===================== Identify Speakers tab ===================== */
function wireIdentifyTab() {
  attachDropZone({
    dropZoneId: "identify-drop-zone",
    fileInputId: "identify-file-input",
    browseButtonId: "identify-btn-browse-file",
    onFile: setIdentifyFile,
  });

  document.getElementById("identify-btn-clear-file")?.addEventListener("click", (e) => {
    e.stopPropagation();
    clearIdentifyFile();
  });

  document.getElementById("btn-start-analysis")?.addEventListener("click", startIdentification);
  document.getElementById("btn-export-results")?.addEventListener("click", exportResults);
}

function setIdentifyFile(file) {
  identifySelectedFile = file;
  document.getElementById("identify-drop-zone").classList.add("hidden");
  const card = document.getElementById("identify-file-preview-card");
  card.classList.remove("hidden");
  document.getElementById("identify-preview-filename").textContent = file.name;
  document.getElementById("identify-preview-meta").textContent = formatBytes(file.size) + " • Ready";
  document.getElementById("btn-start-analysis").disabled = false;
  document.getElementById("analysis-results-container")?.classList.add("hidden");
}

function clearIdentifyFile() {
  identifySelectedFile = null;
  document.getElementById("identify-drop-zone").classList.remove("hidden");
  document.getElementById("identify-file-preview-card").classList.add("hidden");
  document.getElementById("btn-start-analysis").disabled = true;
  const fileInput = document.getElementById("identify-file-input");
  if (fileInput) fileInput.value = "";
}

async function startIdentification() {
  if (!identifySelectedFile) return;
  const startBtn = document.getElementById("btn-start-analysis");
  const loader = document.getElementById("analysis-loader");
  const resultsContainer = document.getElementById("analysis-results-container");
  const loaderStep = document.getElementById("analysis-loader-step");

  startBtn.disabled = true;
  resultsContainer?.classList.add("hidden");
  loader?.classList.remove("hidden");
  loaderStep.textContent = "Uploading file…";

  try {
    const form = new FormData();
    form.append("files", identifySelectedFile);
    const res = await apiFetch("/api/v1/identify", { method: "POST", body: form });
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(extractErrorMessage(data?.detail, "Submit failed"));

    const jobId = data.job_ids[0];
    await pollJob(jobId, loaderStep);
  } catch (err) {
    loader?.classList.add("hidden");
    toast("Identification failed: " + err.message, "error");
  } finally {
    startBtn.disabled = false;
  }
}

async function pollJob(jobId, loaderStep) {
  const loader = document.getElementById("analysis-loader");
  const started = Date.now();
  const STATUS_TEXT = {
    queued: "Queued — waiting for a worker to pick this up…",
    processing: "Diarizing and matching speakers against your library…",
  };

  while (true) {
    const res = await apiFetch("/api/v1/identify/jobs/" + jobId);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const job = await res.json();

    const elapsed = Math.floor((Date.now() - started) / 1000);
    loaderStep.textContent = (STATUS_TEXT[job.status] || job.status) + ` (${elapsed}s elapsed)`;

    if (job.status === "done") {
      loader?.classList.add("hidden");
      renderIdentifyResults(job, identifySelectedFile);
      return;
    }
    if (job.status === "failed") {
      loader?.classList.add("hidden");
      toast("Job failed: " + JSON.stringify(job.results), "error");
      return;
    }
    await new Promise((r) => setTimeout(r, 2500));
  }
}

function renderIdentifyResults(job, file) {
  lastJobResult = job;
  const results = job.results || [];
  document.getElementById("analysis-results-container")?.classList.remove("hidden");
  document.getElementById("result-voice-heading").textContent = file?.name || "Uploaded file";
  document.getElementById("result-timestamp").textContent = "Processed just now";

  const matchedCount = results.filter((r) => r.match.decision === "matched").length;
  const cannotRecognizeCount = results.filter((r) => r.match.decision === "insufficient_speech").length;
  const unidentifiedCount = results.length - matchedCount - cannotRecognizeCount;

  document.getElementById("summary-cards-grid").innerHTML = `
    ${summaryCard("Speakers Detected", results.length, "")}
    ${summaryCard("Identified", matchedCount, "success")}
    ${summaryCard("Unidentified", unidentifiedCount, unidentifiedCount > 0 ? "" : "success")}
    ${summaryCard("Cannot Recognize", cannotRecognizeCount, cannotRecognizeCount > 0 ? "" : "success")}
  `;

  const tbody = document.getElementById("speaker-table-body");
  if (results.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="subtitle">No speakers detected in this file.</td></tr>`;
  } else {
    tbody.innerHTML = results.map((r) => renderSpeakerRow(job.id, r)).join("");
    wireAddToLibraryButtons(tbody);
    wirePlayButtons(tbody);
  }

  const recParts = [];
  if (results.length === 0) {
    recParts.push("No speakers were detected in this recording.");
  } else {
    recParts.push(`${matchedCount} of ${results.length} speaker(s) identified.`);
    if (unidentifiedCount > 0) recParts.push(`${unidentifiedCount} unidentified — use "Add to Library" below to name them.`);
    if (cannotRecognizeCount > 0) recParts.push(`${cannotRecognizeCount} speaker(s) had too little audio to analyze at all.`);
    if (results.some((r) => r.match.decision === "claimed_unverified")) {
      recParts.push("Some speakers named themselves on the call — review and confirm with \"Add to Library\" if correct.");
    }
  }
  document.getElementById("rec-text-dynamic").textContent = recParts.join(" ");
}

function renderTranscriptCell(transcript) {
  if (!transcript || transcript.length === 0) {
    return `<span class="speaker-raw-label">—</span>`;
  }
  return `<div class="transcript-lines">${transcript
    .map(
      (t) =>
        `<div class="transcript-line"><span class="transcript-time">${formatTime(t.start)}</span> ${escapeHtml(t.text)}</div>`
    )
    .join("")}</div>`;
}

function renderPlayButton(jobId, speakerLabel, playable) {
  if (!playable) return "";
  return `<button type="button" class="btn-icon btn-play-speaker" data-job-id="${escapeHtml(jobId)}" data-speaker-label="${escapeHtml(speakerLabel)}" title="Play this speaker's voice">▶</button>`;
}

function renderSpeakerRow(jobId, r) {
  const m = r.match;
  const decisionLabel = m.decision.replace(/_/g, " ");
  const segs = r.segments.map((s) => `${formatTime(s.start)}–${formatTime(s.end)}`).join(", ");
  const transcriptCell = renderTranscriptCell(r.transcript);
  const playButton = renderPlayButton(jobId, r.speaker_label, r.playable);

  if (m.decision === "insufficient_speech") {
    return `
      <tr>
        <td><div class="speaker-name-row"><strong>${escapeHtml(r.display_name || r.speaker_label)}</strong>${playButton}</div><div class="speaker-raw-label">${escapeHtml(r.speaker_label)}</div></td>
        <td>${r.total_speech_sec.toFixed(1)}s</td>
        <td class="speaker-raw-label">${segs}</td>
        <td>
          <span class="decision-badge ${m.decision}">Cannot recognize</span>
          <div class="speaker-raw-label">Not enough audio to analyze this speaker.</div>
        </td>
        <td>${transcriptCell}</td>
      </tr>`;
  }

  let note = "";
  if (m.decision === "claimed_unverified") note = "spoken name — not yet saved, confirm below";
  else if (m.claimed_name && m.decision === "matched") note = `spoken name: ${escapeHtml(m.claimed_name)}`;

  const scoreLine = `score ${m.score.toFixed(2)}${m.runner_up_score ? ", runner-up " + m.runner_up_score.toFixed(2) : ""}${note ? " — " + note : ""}`;

  let actionHtml = "";
  if (r.embeddable) {
    const suggestedName = m.claimed_name || "";
    actionHtml = `
      <div class="add-to-library-row" data-job-id="${escapeHtml(jobId)}" data-speaker-label="${escapeHtml(r.speaker_label)}">
        <input type="text" class="add-to-library-name" placeholder="Name this voice…" value="${escapeHtml(suggestedName)}" />
        <button type="button" class="btn btn-secondary btn-sm btn-add-to-library">Add to Library</button>
      </div>`;
  }

  return `
    <tr>
      <td><div class="speaker-name-row"><strong>${escapeHtml(r.display_name || r.speaker_label)}</strong>${playButton}</div><div class="speaker-raw-label">${escapeHtml(r.speaker_label)}</div></td>
      <td>${r.total_speech_sec.toFixed(1)}s</td>
      <td class="speaker-raw-label">${segs}</td>
      <td>
        <span class="decision-badge ${m.decision}">${escapeHtml(decisionLabel)}</span>
        <div class="speaker-raw-label">${scoreLine}</div>
        ${actionHtml}
      </td>
      <td>${transcriptCell}</td>
    </tr>`;
}

function wireAddToLibraryButtons(tbody) {
  tbody.querySelectorAll(".btn-add-to-library").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const row = btn.closest(".add-to-library-row");
      const jobId = row.dataset.jobId;
      const speakerLabel = row.dataset.speakerLabel;
      const nameInput = row.querySelector(".add-to-library-name");
      const name = nameInput.value.trim();
      if (!name) {
        toast("Enter a name before adding to the library.", "error");
        return;
      }

      btn.disabled = true;
      nameInput.disabled = true;
      const originalLabel = btn.textContent;
      btn.textContent = "Adding…";
      try {
        const res = await apiFetch("/api/v1/identify/speakers/enroll", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            job_id: jobId,
            speaker_label: speakerLabel,
            name,
            consent_given_by: currentUsername || "studio reviewer",
            consent_method: "Confirmed via Identify tab review",
          }),
        });
        const data = await res.json().catch(() => null);
        if (!res.ok) throw new Error(extractErrorMessage(data?.detail, "Add to library failed"));

        toast(`Added "${data.name}" to the library.`, "success");
        row.outerHTML = `<div class="speaker-raw-label">Added as "${escapeHtml(data.name)}" ✓</div>`;
        refreshLibrary();
      } catch (err) {
        toast("Add to library failed: " + err.message, "error");
        btn.disabled = false;
        nameInput.disabled = false;
        btn.textContent = originalLabel;
      }
    });
  });
}

const audioCache = new Map(); // cacheKey -> HTMLAudioElement
let currentlyPlayingKey = null;
let currentlyPlayingBtn = null;

function wirePlayButtons(tbody) {
  tbody.querySelectorAll(".btn-play-speaker").forEach((btn) => {
    btn.addEventListener("click", () => togglePlaySpeaker(btn));
  });
}

function stopCurrentlyPlaying() {
  if (currentlyPlayingKey) {
    audioCache.get(currentlyPlayingKey)?.pause();
    if (currentlyPlayingBtn) currentlyPlayingBtn.textContent = "▶";
  }
  currentlyPlayingKey = null;
  currentlyPlayingBtn = null;
}

async function togglePlaySpeaker(btn) {
  const jobId = btn.dataset.jobId;
  const speakerLabel = btn.dataset.speakerLabel;
  const cacheKey = jobId + "::" + speakerLabel;

  if (currentlyPlayingKey === cacheKey) {
    stopCurrentlyPlaying();
    return;
  }
  stopCurrentlyPlaying();

  let audio = audioCache.get(cacheKey);
  if (audio) {
    audio.currentTime = 0;
    audio.play();
    btn.textContent = "⏸";
    currentlyPlayingKey = cacheKey;
    currentlyPlayingBtn = btn;
    return;
  }

  btn.disabled = true;
  btn.textContent = "…";
  try {
    const res = await apiFetch(`/api/v1/identify/jobs/${jobId}/speakers/${encodeURIComponent(speakerLabel)}/audio`);
    if (!res.ok) throw new Error(res.status === 404 ? "Clip expired or unavailable" : "HTTP " + res.status);
    const blob = await res.blob();
    audio = new Audio(URL.createObjectURL(blob));
    audio.addEventListener("ended", () => {
      if (currentlyPlayingKey === cacheKey) stopCurrentlyPlaying();
    });
    audioCache.set(cacheKey, audio);
    audio.play();
    btn.textContent = "⏸";
    currentlyPlayingKey = cacheKey;
    currentlyPlayingBtn = btn;
  } catch (err) {
    toast("Couldn't load audio: " + err.message, "error");
    btn.textContent = "▶";
  } finally {
    btn.disabled = false;
  }
}

function summaryCard(title, value, badgeClass) {
  return `
    <div class="metric-card">
      <div class="metric-card-top">
        <span class="metric-title">${title}</span>
        ${badgeClass ? `<span class="metric-badge ${badgeClass}">OK</span>` : ""}
      </div>
      <div class="metric-number-row">
        <span class="metric-huge">${value}</span>
      </div>
    </div>`;
}

function exportResults() {
  if (!lastJobResult) return;
  const blob = new Blob([JSON.stringify(lastJobResult, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `identification-${lastJobResult.id || "result"}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/* ===================== Bootstrap ===================== */
async function init() {
  await loadComponents();

  wireLogin();
  wireTabs();
  wireRegisterTab();
  wireLibraryTab();
  wireIdentifyTab();

  if (token) {
    setLoggedInUI(currentUsername);
    await refreshLibrary();
  } else {
    setLoggedOutUI();
  }
}

document.addEventListener("DOMContentLoaded", init);

// Bundle of Authorities (BOA) Autobot - Frontend Controller

let currentAuthorities = [];
let currentGroupOrder = [
  "Singapore Cases",
  "Singapore Statutes",
  "Regulations / Statutory Instruments",
  "Foreign Cases",
  "Foreign Statutes",
  "Secondary Sources",
  "Miscellaneous"
];
let currentMetadata = {};
let selectedFile = null;

// DOM Elements
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const selectedFileName = document.getElementById("selectedFileName");
const btnProcessDoc = document.getElementById("btnProcessDoc");
const btnLoadExample = document.getElementById("btnLoadExample");

const resultsContainer = document.getElementById("resultsContainer");
const statTotalFootnotes = document.getElementById("statTotalFootnotes");
const statFilteredEvidence = document.getElementById("statFilteredEvidence");
const statUniqueAuthorities = document.getElementById("statUniqueAuthorities");

const groupListContainer = document.getElementById("groupListContainer");
const chkMergeForeign = document.getElementById("chkMergeForeign");
const chkMergeStatutes = document.getElementById("chkMergeStatutes");

const authoritiesTableBody = document.getElementById("authoritiesTableBody");
const btnRunRetrieval = document.getElementById("btnRunRetrieval");
const btnGenerateBOA = document.getElementById("btnGenerateBOA");

// Metadata Form Inputs
const metaCourt = document.getElementById("metaCourt");
const metaCaseNo = document.getElementById("metaCaseNo");
const metaMatter = document.getElementById("metaMatter");
const metaClaimant = document.getElementById("metaClaimant");
const metaClaimantUEN = document.getElementById("metaClaimantUEN");
const metaRespondent = document.getElementById("metaRespondent");
const metaRespondentUEN = document.getElementById("metaRespondentUEN");
const metaDocTitle = document.getElementById("metaDocTitle");
const metaDate = document.getElementById("metaDate");
const metaClaimantSol = document.getElementById("metaClaimantSol");
const metaRespondentSol = document.getElementById("metaRespondentSol");


// 1. File Selection & Drag-and-Drop
dropZone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    handleFileSelected(e.target.files[0]);
  }
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("border-amber-500", "bg-amber-50/20");
});

dropZone.addEventListener("dragleave", () => {
  dropZone.classList.remove("border-amber-500", "bg-amber-50/20");
});

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("border-amber-500", "bg-amber-50/20");
  if (e.dataTransfer.files.length > 0) {
    handleFileSelected(e.dataTransfer.files[0]);
  }
});

function handleFileSelected(file) {
  if (!file.name.endsWith(".docx")) {
    alert("Please upload a .docx file.");
    return;
  }
  selectedFile = file;
  selectedFileName.textContent = `Selected: ${file.name}`;
  selectedFileName.classList.remove("hidden");
  btnProcessDoc.disabled = false;
}


// 2. Load Bundled Example Memo
btnLoadExample.addEventListener("click", async () => {
  btnLoadExample.disabled = true;
  btnLoadExample.innerHTML = `<span class="animate-spin">⌛</span> Loading Example Memo...`;

  try {
    const resp = await fetch("/api/load-example");
    if (!resp.ok) throw new Error("Failed to load example memo");
    const data = await resp.json();
    populateData(data);
  } catch (err) {
    alert("Error loading example memo: " + err.message);
  } finally {
    btnLoadExample.disabled = false;
    btnLoadExample.innerHTML = `
      <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
      Load Bundled Example Memo (104 Footnotes)
    `;
  }
});


// 3. Process Uploaded Document
btnProcessDoc.addEventListener("click", async () => {
  if (!selectedFile) return;

  btnProcessDoc.disabled = true;
  btnProcessDoc.innerHTML = `<span class="animate-spin">⌛</span> Processing Footnotes...`;

  const formData = new FormData();
  formData.append("file", selectedFile);

  try {
    const resp = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Upload failed");
    }
    const data = await resp.json();
    populateData(data);
  } catch (err) {
    alert("Error processing document: " + err.message);
  } finally {
    btnProcessDoc.disabled = false;
    btnProcessDoc.innerHTML = `
      <span>Process & Extract Footnotes</span>
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
    `;
  }
});


// 4. Populate Extracted Data into UI
function populateData(data) {
  currentAuthorities = data.authorities || [];
  currentMetadata = data.detected_metadata || {};

  // Stats
  statTotalFootnotes.textContent = data.total_footnotes;
  statFilteredEvidence.textContent = data.filtered_evidence_count;
  statUniqueAuthorities.textContent = currentAuthorities.length;

  // Metadata Form
  metaCourt.value = currentMetadata.court_name || "";
  metaCaseNo.value = currentMetadata.case_number || "";
  metaMatter.value = currentMetadata.matter_description || "";
  metaClaimant.value = currentMetadata.claimant_name || "";
  metaClaimantUEN.value = currentMetadata.claimant_uen || "";
  metaRespondent.value = currentMetadata.respondent_name || "";
  metaRespondentUEN.value = currentMetadata.respondent_uen || "";
  metaDocTitle.value = currentMetadata.document_title || "CLAIMANT'S BUNDLE OF AUTHORITIES";
  metaDate.value = currentMetadata.dated_date || "";
  metaClaimantSol.value = currentMetadata.claimant_solicitors || "";
  metaRespondentSol.value = currentMetadata.respondent_solicitors || "";

  // Render Groups & Table
  renderGroupList();
  renderAuthoritiesTable();

  // Show results
  resultsContainer.classList.remove("hidden");
  resultsContainer.scrollIntoView({ behavior: "smooth" });
}


// 5. Render Group Ordering List
function renderGroupList() {
  groupListContainer.innerHTML = "";

  currentGroupOrder.forEach((groupName, index) => {
    const div = document.createElement("div");
    div.className = "group-item flex items-center justify-between p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-xs";

    div.innerHTML = `
      <div class="flex items-center space-x-2">
        <span class="w-5 h-5 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center font-bold text-[10px]">
          ${index + 1}
        </span>
        <span class="font-semibold text-slate-800">${groupName}</span>
      </div>
      <div class="flex items-center space-x-1">
        <button class="btn-up px-2 py-1 bg-white border border-slate-200 rounded text-slate-600 hover:bg-slate-100 disabled:opacity-30" ${index === 0 ? "disabled" : ""}>
          ▲
        </button>
        <button class="btn-down px-2 py-1 bg-white border border-slate-200 rounded text-slate-600 hover:bg-slate-100 disabled:opacity-30" ${index === currentGroupOrder.length - 1 ? "disabled" : ""}>
          ▼
        </button>
      </div>
    `;

    // Move Up
    div.querySelector(".btn-up").addEventListener("click", () => {
      if (index > 0) {
        const temp = currentGroupOrder[index - 1];
        currentGroupOrder[index - 1] = currentGroupOrder[index];
        currentGroupOrder[index] = temp;
        renderGroupList();
      }
    });

    // Move Down
    div.querySelector(".btn-down").addEventListener("click", () => {
      if (index < currentGroupOrder.length - 1) {
        const temp = currentGroupOrder[index + 1];
        currentGroupOrder[index + 1] = currentGroupOrder[index];
        currentGroupOrder[index] = temp;
        renderGroupList();
      }
    });

    groupListContainer.appendChild(div);
  });
}


// 6. Render Authorities Table
// Footnote text comes from the uploaded draft, so it is only ever inserted with textContent, never as HTML.
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const WARNING_ICON = `<svg class="w-3 h-3 mr-1 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`;
const CHECK_ICON = `<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>`;

function statusPill(icon, label, className) {
  const pill = el("span", `inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium border ${className}`);
  pill.innerHTML = icon;  // a fixed icon, never text from the draft
  pill.append(label);
  return pill;
}

function statusCell(auth) {
  const note = (text) => el("p", "text-[10px] text-slate-500 mt-1 leading-tight", text);
  if (auth.retrieval_status === "VERIFIED_MATCH") {
    return [
      statusPill(CHECK_ICON, "Verified on eLitigation", "bg-emerald-100 text-emerald-800 border-emerald-300"),
      note(auth.retrieval_note || "Found on eLitigation.")
    ];
  }
  if (auth.retrieval_status === "PENDING") {
    return [
      statusPill("", "Not checked yet", "bg-slate-100 text-slate-700 border-slate-300"),
      note("Gets a placeholder sheet unless the check verifies it.")
    ];
  }
  return [
    statusPill(WARNING_ICON, "Placeholder sheet", "bg-amber-50 text-amber-800 border-amber-300"),
    note(auth.retrieval_note || "Not found on a free official source. Insert it by hand.")
  ];
}

function renderAuthoritiesTable() {
  authoritiesTableBody.replaceChildren();

  const allCategories = [
    "Singapore Cases",
    "Singapore Statutes",
    "Regulations / Statutory Instruments",
    "Foreign Cases",
    "Foreign Statutes",
    "Secondary Sources",
    "Miscellaneous"
  ];

  currentAuthorities.forEach((auth) => {
    const tr = el("tr", "hover:bg-slate-50/70 transition-colors");

    // Include checkbox
    const tdInclude = el("td", "py-3 px-4 text-center");
    const chk = el("input", "auth-chk rounded border-slate-300 text-slate-900 focus:ring-slate-900");
    chk.type = "checkbox";
    chk.checked = auth.included !== false;
    chk.addEventListener("change", (e) => {
      auth.included = e.target.checked;
    });
    tdInclude.append(chk);

    // Category select
    const tdCategory = el("td", "py-3 px-4");
    const select = el("select", "auth-category-select text-xs border border-slate-200 rounded px-2 py-1 bg-white focus:ring-1 focus:ring-slate-900 w-full");
    allCategories.forEach((cat) => {
      const option = el("option", null, cat);
      option.value = cat;
      option.selected = auth.category === cat;
      select.append(option);
    });
    select.addEventListener("change", (e) => {
      auth.category = e.target.value;
    });
    tdCategory.append(select);

    // Title & citation
    const tdTitle = el("td", "py-3 px-4");
    tdTitle.append(
      el("p", "font-semibold text-slate-900 leading-snug", auth.title),
      el("p", "text-[11px] text-slate-500 font-mono mt-0.5", auth.citation || auth.raw_citation)
    );
    if (auth.relevance) {
      tdTitle.append(el("p", "text-[11px] text-slate-600 italic mt-1 bg-slate-50 p-1 rounded border border-slate-100", `Relevance: ${auth.relevance}`));
    }

    // Pinpoint badges
    const tdPins = el("td", "py-3 px-4");
    if (auth.pinpoints && auth.pinpoints.length > 0) {
      auth.pinpoints.forEach((p) => {
        tdPins.append(el("span", "inline-block bg-amber-100 text-amber-900 border border-amber-300 font-mono text-[10px] px-1.5 py-0.5 rounded mr-1 mb-1 font-semibold", p));
      });
    } else {
      tdPins.append(el("span", "text-slate-400 italic", "Entire source"));
    }

    // Status
    const tdStatus = el("td", "py-3 px-4");
    tdStatus.append(...statusCell(auth));

    tr.append(tdInclude, tdCategory, tdTitle, tdPins, tdStatus);
    authoritiesTableBody.appendChild(tr);
  });
}


// 7. Check Singapore judgments on eLitigation
btnRunRetrieval.addEventListener("click", async () => {
  btnRunRetrieval.disabled = true;
  btnRunRetrieval.innerHTML = `<span class="animate-spin">⌛</span> Checking eLitigation...`;

  try {
    const resp = await fetch("/api/retrieve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        authorities: currentAuthorities,
        use_live_network: true
      })
    });
    if (!resp.ok) throw new Error("Retrieval request failed");
    const data = await resp.json();
    currentAuthorities = data.authorities;
    renderAuthoritiesTable();
  } catch (err) {
    alert("Retrieval error: " + err.message);
  } finally {
    btnRunRetrieval.disabled = false;
    btnRunRetrieval.innerHTML = `
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
      <span>Check Singapore Judgments on eLitigation</span>
    `;
  }
});


// 8. Generate & Download Bundle of Authorities (.docx)
btnGenerateBOA.addEventListener("click", async () => {
  btnGenerateBOA.disabled = true;
  btnGenerateBOA.innerHTML = `<span class="animate-spin">⌛</span> Compiling .docx Bundle...`;

  // Collect updated metadata from form
  const metadata = {
    court_name: metaCourt.value.trim(),
    case_number: metaCaseNo.value.trim(),
    matter_description: metaMatter.value.trim(),
    claimant_name: metaClaimant.value.trim(),
    claimant_uen: metaClaimantUEN.value.trim() || null,
    respondent_name: metaRespondent.value.trim(),
    respondent_uen: metaRespondentUEN.value.trim() || null,
    document_title: metaDocTitle.value.trim(),
    dated_date: metaDate.value.trim(),
    claimant_solicitors: metaClaimantSol.value.trim(),
    respondent_solicitors: metaRespondentSol.value.trim()
  };

  // Determine merged groups
  const mergedGroups = {};
  if (chkMergeForeign.checked) {
    mergedGroups["Foreign Statutes"] = "Foreign Authorities";
    mergedGroups["Foreign Cases"] = "Foreign Authorities";
  }
  if (chkMergeStatutes.checked) {
    mergedGroups["Singapore Statutes"] = "Statutes & Statutory Instruments";
    mergedGroups["Regulations / Statutory Instruments"] = "Statutes & Statutory Instruments";
  }

  try {
    const resp = await fetch("/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        metadata: metadata,
        authorities: currentAuthorities,
        custom_order: currentGroupOrder,
        merged_groups: mergedGroups
      })
    });

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || "Generation failed");
    }

    // Trigger file download in browser
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${metadata.document_title.replace(/\s+/g, "_")}.docx`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

  } catch (err) {
    alert("Error generating document: " + err.message);
  } finally {
    btnGenerateBOA.disabled = false;
    btnGenerateBOA.innerHTML = `
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
      <span>Download Bundle of Authorities (.docx)</span>
    `;
  }
});


// 9. Check Local Model Health on Load
async function checkModelStatus() {
  const badge = document.getElementById("localModelBadge");
  if (!badge) return;

  try {
    const resp = await fetch("/api/model-status");
    if (resp.ok) {
      const data = await resp.json();
      if (data.status === "online") {
        badge.className = "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/30";
        badge.innerHTML = `<span class="w-1.5 h-1.5 mr-1.5 bg-emerald-400 rounded-full animate-pulse"></span> Local LLM: Online (${data.model})`;
      } else {
        badge.className = "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700";
        badge.innerHTML = `<span class="w-1.5 h-1.5 mr-1.5 bg-slate-500 rounded-full"></span> Local LLM: Port 11434 (Standby)`;
      }
    }
  } catch (e) {
    badge.className = "inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700";
    badge.innerHTML = `<span class="w-1.5 h-1.5 mr-1.5 bg-slate-500 rounded-full"></span> Local LLM: Port 11434 (Standby)`;
  }
}

checkModelStatus();


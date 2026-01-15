// Load runtime config from server into `window.APP_CONFIG`
window.APP_CONFIG = {};
window.APP_CONFIG_READY = (async function loadAppConfig() {
  try {
    const resp = await fetch("/config");
    if (resp.ok) window.APP_CONFIG = await resp.json();
  } catch (e) {
    /* ignore, fall back to defaults */
  }
})();

// Tab switching
function switchTab(index) {
  const tabs = document.querySelectorAll(".tab");
  const contents = document.querySelectorAll(".tab-content");

  tabs.forEach((tab, i) => {
    if (i === index) {
      tab.classList.add("active");
      contents[i].classList.add("active");
    } else {
      tab.classList.remove("active");
      contents[i].classList.remove("active");
    }
  });
}

// File input handlers - Pivot Service
const scoresFile = document.getElementById("scoresFile");
const disciplinesFile = document.getElementById("disciplinesFile");
const scoresLabel = document.getElementById("scoresLabel");
const disciplinesLabel = document.getElementById("disciplinesLabel");
const scoresName = document.getElementById("scoresName");
const disciplinesName = document.getElementById("disciplinesName");

scoresFile.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    scoresLabel.classList.add("has-file");
    scoresName.textContent = e.target.files[0].name;
  }
});

disciplinesFile.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    disciplinesLabel.classList.add("has-file");
    disciplinesName.textContent = e.target.files[0].name;
  }
});

// File input handlers - XML Service
const pivotTableFile = document.getElementById("pivotTableFile");
const studentInfoFile = document.getElementById("studentInfoFile");
// const curriculumFile = document.getElementById("curriculumFile");
const pivotTableLabel = document.getElementById("pivotTableLabel");
const studentInfoLabel = document.getElementById("studentInfoLabel");
const curriculumLabel = document.getElementById("curriculumLabel");
const pivotTableName = document.getElementById("pivotTableName");
const studentInfoName = document.getElementById("studentInfoName");
const curriculumName = document.getElementById("curriculumName");

pivotTableFile.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    pivotTableLabel.classList.add("has-file");
    pivotTableName.textContent = e.target.files[0].name;
  }
});

studentInfoFile.addEventListener("change", (e) => {
  if (e.target.files.length > 0) {
    studentInfoLabel.classList.add("has-file");
    studentInfoName.textContent = e.target.files[0].name;
  }
});

// curriculumFile.addEventListener("change", (e) => {
//   if (e.target.files.length > 0) {
//     curriculumLabel.classList.add("has-file");
//     curriculumName.textContent = e.target.files[0].name;
//   }
// });

// Pivot form submission
const pivotForm = document.getElementById("pivotForm");
const pivotStatus = document.getElementById("pivotStatus");
const pivotSubmitBtn = document.getElementById("pivotSubmitBtn");

pivotForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Wait for config to load before proceeding
  await window.APP_CONFIG_READY;

  if (!scoresFile.files[0] || !disciplinesFile.files[0]) {
    showStatus("pivotStatus", "error", "Please select both files");
    return;
  }

  pivotSubmitBtn.disabled = true;
  showStatus(
    "pivotStatus",
    "loading",
    '<span class="spinner"></span>Processing files, please wait...',
  );

  const formData = new FormData();
  formData.append("scores_xlsx", scoresFile.files[0]);
  formData.append("disciplines_xlsx", disciplinesFile.files[0]);

  try {
    // Use configured pivot service URL from runtime config
    // const apiBase = (window.APP_CONFIG && window.APP_CONFIG.PIVOT_ENGINE_BASE_URL) ? window.APP_CONFIG.PIVOT_ENGINE_BASE_URL : '';
    // const pivotPath = (window.APP_CONFIG && window.APP_CONFIG.PIVOT_API_PATH) ? window.APP_CONFIG.PIVOT_API_PATH : '/pivot';
    // const pivotUrl = apiBase ? (apiBase.replace(/\/$/, '') + pivotPath) : '/pivot';
    const pivotUrl = "/pivot";

    const response = await fetch(pivotUrl, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || "Processing failed");
    }

    const blob = await response.blob();
    downloadFile(blob, `pivot_report_${Date.now()}.xlsx`);

    showStatus(
      "pivotStatus",
      "success",
      "✓ Report generated successfully! Download started.",
    );

    setTimeout(() => {
      pivotForm.reset();
      scoresLabel.classList.remove("has-file");
      disciplinesLabel.classList.remove("has-file");
      scoresName.textContent = "Файл не выбран";
      disciplinesName.textContent = "Файл не выбран";
    }, 2000);
  } catch (error) {
    showStatus("pivotStatus", "error", `✗ Error: ${error.message}`);
  } finally {
    pivotSubmitBtn.disabled = false;
  }
});

// XML form submission
const xmlForm = document.getElementById("xmlForm");
const xmlStatus = document.getElementById("xmlStatus");
const xmlSubmitBtn = document.getElementById("xmlSubmitBtn");

xmlForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  // Wait for config to load before proceeding
  await window.APP_CONFIG_READY;

  if (!pivotTableFile.files[0] || !studentInfoFile.files[0]) {
    showStatus("xmlStatus", "error", "Please select required files");
    return;
  }

  xmlSubmitBtn.disabled = true;
  showStatus(
    "xmlStatus",
    "loading",
    '<span class="spinner"></span>Generating XML, please wait...',
  );

  const formData = new FormData();
  formData.append("pivot_table", pivotTableFile.files[0]);
  formData.append("student_info", studentInfoFile.files[0]);

  // Add configuration
  formData.append("edu_term", document.getElementById("eduTerm").value);
  formData.append(
    "qualification",
    document.getElementById("qualification").value,
  );
  formData.append("edu_form", document.getElementById("eduForm").value);
  formData.append("speciality", document.getElementById("speciality").value);
  formData.append(
    "edu_progr_vol",
    document.getElementById("eduProgrVol").value,
  );
  formData.append(
    "edu_progr_vol_contact",
    document.getElementById("eduProgrVolContact").value,
  );
  formData.append(
    "pract_total_z_e",
    document.getElementById("practTotalZe").value,
  );
  formData.append("gia_z_e", document.getElementById("giaZe").value);
  formData.append("gek_chairman", document.getElementById("gekChairman").value);
  formData.append(
    "state_exam_credits",
    document.getElementById("stateExamCredits").value,
  );

  try {
    const xmlUrl = "/generate-xml";

    const response = await fetch(xmlUrl, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || "XML generation failed");
    }

    const blob = await response.blob();
    
    // ===== MODIFIED: Get speciality value for filename =====
    const speciality = document.getElementById("speciality").value;
    
    // Create a safe filename by removing special characters
    const safeSpeciality = speciality
      .replace(/[^a-zA-Zа-яА-ЯёЁ0-9\s]/g, '') // Remove special chars, keep Cyrillic
      .replace(/\s+/g, '_') // Replace spaces with underscores
      .substring(0, 50); // Limit length to 50 chars
    
    // Use speciality in filename if available
    const filename = safeSpeciality 
      ? `${safeSpeciality}_${Date.now()}.xml`
      : `diploma_${Date.now()}.xml`;
    
    downloadFile(blob, filename);
    // ===== END MODIFICATION =====

    showStatus(
      "xmlStatus",
      "success",
      "✓ XML generated successfully! Download started.",
    );
  } catch (error) {
    showStatus("xmlStatus", "error", `✗ Error: ${error.message}`);
  } finally {
    xmlSubmitBtn.disabled = false;
  }
});

function showStatus(elementId, type, message) {
  const status = document.getElementById(elementId);
  status.className = `status ${type}`;
  status.innerHTML = message;
  status.style.display = "block";

  if (type !== "loading") {
    setTimeout(() => {
      status.style.display = "none";
    }, 5000);
  }
}

function downloadFile(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

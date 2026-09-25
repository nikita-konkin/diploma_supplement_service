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

  if (!scoresFile.files[0] || !disciplinesFile.files[0]) {
    showStatus("pivotStatus", "error", "Выберите оба файла: ведомость и список дисциплин");
    return;
  }

  pivotSubmitBtn.disabled = true;
  showStatus(
    "pivotStatus",
    "loading",
    '<span class="spinner"></span>Обработка файлов, пожалуйста, подождите...',
  );

  const formData = new FormData();
  formData.append("scores_xlsx", scoresFile.files[0]);
  formData.append("disciplines_xlsx", disciplinesFile.files[0]);

  try {
    const response = await fetch("/pivot", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await responseError(response, "Не удалось построить сводную таблицу"));
    }

    const blob = await response.blob();
    downloadFile(blob, `pivot_report_${Date.now()}.xlsx`);

    showStatus(
      "pivotStatus",
      "success",
      "✓ Таблица создана успешно! Загрузка файла начата.",
    );

    setTimeout(() => {
      pivotForm.reset();
      scoresLabel.classList.remove("has-file");
      disciplinesLabel.classList.remove("has-file");
      scoresName.textContent = "Файл не выбран";
      disciplinesName.textContent = "Файл не выбран";
    }, 2000);
  } catch (error) {
    showStatus("pivotStatus", "error", `✗ Ошибка: ${error.message}`);
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

  if (!pivotTableFile.files[0] || !studentInfoFile.files[0]) {
    showStatus("xmlStatus", "error", "Выберите оба файла: сводную таблицу и сведения о студентах");
    return;
  }

  xmlSubmitBtn.disabled = true;
  showStatus(
    "xmlStatus",
    "loading",
    '<span class="spinner"></span>Генерация XML, пожалуйста, подождите...',
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
  formData.append("direction", document.getElementById("direction").value);
  formData.append("profile", document.getElementById("profile").value);
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
    const response = await fetch("/generate-xml", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(await responseError(response, "Не удалось сформировать XML"));
    }

    const blob = await response.blob();

    const direction = document.getElementById("direction").value;

    // Create a safe filename by removing special characters
    const safeSpeciality = direction
      .replace(/[^a-zA-Zа-яА-ЯёЁ0-9\s]/g, '') // Remove special chars, keep Cyrillic
      .replace(/\s+/g, '_') // Replace spaces with underscores
      .substring(0, 50); // Limit length to 50 chars
    
    // Use the direction in filename if available
    const filename = safeSpeciality 
      ? `${safeSpeciality}_${Date.now()}.xml`
      : `diploma_${Date.now()}.xml`;
    
    downloadFile(blob, filename);

    showStatus(
      "xmlStatus",
      "success",
      "✓ XML сгенерирован успешно! Загрузка файла начата.",
    );
  } catch (error) {
    showStatus("xmlStatus", "error", `✗ Ошибка: ${error.message}`);
  } finally {
    xmlSubmitBtn.disabled = false;
  }
});

function showStatus(elementId, type, message) {
  const status = document.getElementById(elementId);
  status.className = `status ${type}`;
  if (type === "loading") {
    status.innerHTML = message;
  } else {
    status.textContent = message;
  }
  status.style.display = "block";

  if (type === "success") {
    setTimeout(() => {
      status.style.display = "none";
    }, 5000);
  }
}

async function responseError(response, fallback) {
  if (response.status === 413) {
    // A proxy in front of the gateway may answer with its own HTML page
    const body = await response.text();
    try {
      return JSON.parse(body).error || "Файлы слишком большие для загрузки";
    } catch (error) {
      return "Файлы слишком большие для загрузки";
    }
  }
  const body = await response.text();
  if (!body) {
    return fallback;
  }
  try {
    const payload = JSON.parse(body);
    const message = payload.detail || payload.error || payload.message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    if (message) {
      return JSON.stringify(message);
    }
  } catch (error) {
    // Plain text errors from reverse proxies are still useful to the user.
  }
  return body;
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

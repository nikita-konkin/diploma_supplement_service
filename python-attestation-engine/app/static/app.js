"use strict";

// Страница сервиса аттестации: выбор кафедры и групп, запуск задачи, опрос её состояния, показ отчёта.
const BASE = "/attestation";
const STATUS_CLASSES = { "●": "s-ok", "▲": "s-warn", "✕": "s-crit", "○": "s-none" };
const LEVEL_TITLES = { "б": "Бакалавриат", "м": "Магистратура" };
const LAST_DEPARTMENT = "attestation.department";
let csrf = "";
let faculties = [];
let reportData = null;  // данные графиков из attestation_report.json; без них — только таблицы

function escapeHtml(text) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function inline(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
}

function renderTable(lines) {
  const rows = lines.filter((line, index) => index !== 1).map(line => line.replace(/^\||\|$/g, "").split("|").map(cell => cell.trim()));
  const [head, ...body] = rows;
  const th = head.map(cell => `<th>${inline(cell)}</th>`).join("");
  const tr = body.map(cells => "<tr>" + cells.map(cell => {
    const status = STATUS_CLASSES[cell.charAt(0)];
    const numeric = /^[−+\-–]?[\d,]+( %| из \d+)?$|^\d+ из \d+$/.test(cell);
    const kind = status || (numeric ? "num" : cell.length > 30 ? "wide" : "");
    return `<td class="${kind}">${inline(cell)}</td>`;
  }).join("") + "</tr>").join("");
  return `<div class="table-wrap"><table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table></div>`;
}

// Разбор того подмножества Markdown, которое пишет build_markdown_report.py
function renderMarkdown(markdown) {
  const html = [];
  const lines = markdown.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("|")) {
      const block = [];
      while (i < lines.length && lines[i].startsWith("|")) block.push(lines[i++]);
      i--;
      html.push(renderTable(block));
    } else if (line.startsWith("- ")) {
      const items = [];
      while (i < lines.length && lines[i].startsWith("- ")) items.push(`<li>${inline(lines[i++].slice(2))}</li>`);
      i--;
      html.push(`<ul>${items.join("")}</ul>`);
    } else if (line.startsWith("### ")) {
      html.push(`<h3>${inline(line.slice(4))}</h3>`);
    } else if (line.trim()) {
      html.push(`<p>${inline(line)}</p>`);
    }
  }
  return html.join("");
}

function splitSections(markdown) {
  const [header, ...parts] = markdown.split(/^## /m);
  const headerLines = header.trim().split("\n");
  return {
    title: headerLines[0].replace(/^# /, ""),
    intro: headerLines.slice(1).join(" ").trim(),
    sections: parts.map(part => {
      const [name, ...rest] = part.split("\n");
      const body = rest.join("\n");
      const cards = body.split(/^(?=### )/m).filter(chunk => chunk.trim());
      return { name: name.trim(), body, cards };
    }),
  };
}

function showSection(section) {
  const toolbar = document.getElementById("toolbar");
  const target = document.getElementById("report-body");
  toolbar.innerHTML = "";
  const isCards = section.name === "Группы" || section.name === "Преподаватели";
  if (!isCards) {
    // плитки заменяют строку «Студентов: … · групп: …», дальше — выводы и таблицы как есть
    const body = reportData && section.name === "Сводка"
      ? section.body.split("\n").filter(line => !line.startsWith("Студентов: ")).join("\n")
      : section.body;
    target.innerHTML = renderMarkdown(body);
    if (reportData && section.name === "Сводка") {
      target.prepend(renderSummaryTiles(reportData), renderGroupChart(reportData));
    }
    if (section.name === "Дисциплины") addStatusFilter(toolbar, target);
    return;
  }
  const cards = section.cards.map(chunk => `<div class="card">${renderMarkdown(chunk)}</div>`);
  target.innerHTML = cards.join("");
  if (reportData && section.name === "Группы") addHeatmaps(target);
  const control = section.name === "Группы" ? document.createElement("select") : document.createElement("input");
  if (section.name === "Группы") {
    control.innerHTML = `<option value="">Все группы</option>` +
      section.cards.map((chunk, index) => `<option value="${index}">${escapeHtml(chunk.split("\n")[0].replace("### ", ""))}</option>`).join("");
    control.onchange = () => target.querySelectorAll(".card").forEach((card, index) => {
      card.hidden = control.value !== "" && Number(control.value) !== index;
    });
  } else {
    control.type = "search";
    control.placeholder = "Фамилия или кафедра";
    control.oninput = () => target.querySelectorAll(".card").forEach(card => {
      card.hidden = !card.querySelector("h3").textContent.toLowerCase().includes(control.value.toLowerCase());
    });
  }
  toolbar.appendChild(control);
}

function addStatusFilter(toolbar, target) {
  const active = new Set(["s-ok", "s-warn", "s-crit", "s-none"]);
  const chips = [["s-crit", "✕ критично"], ["s-warn", "▲ внимание"], ["s-ok", "● норма"]];
  if (target.querySelector("td.s-none")) chips.push(["s-none", "○ не выставлено"]);
  chips.forEach(([cls, label]) => {
    const chip = document.createElement("button");
    chip.className = "chip on";
    chip.textContent = label;
    chip.onclick = () => {
      active.has(cls) ? active.delete(cls) : active.add(cls);
      chip.classList.toggle("on");
      target.querySelectorAll("tbody tr").forEach(row => {
        const statusCell = row.querySelector("td.s-ok, td.s-warn, td.s-crit, td.s-none");
        row.hidden = statusCell && !active.has(statusCell.className);
      });
    };
    toolbar.appendChild(chip);
  });
}

function addHeatmaps(target) {
  const byName = new Map(reportData.groups.map(group => [group.name, group]));
  target.querySelectorAll(".card").forEach(card => {
    const title = card.querySelector("h3");
    const group = title && byName.get(title.textContent.split(" · ")[0].trim());
    if (!group || !group.students_scores.length) return;
    const stats = title.nextElementSibling;
    (stats || title).after(renderHeatmap(group, reportData));
  });
}

function showReport(markdown, downloads, data) {
  reportData = data || null;
  const report = splitSections(markdown);
  document.getElementById("report-title").textContent = report.title;
  document.getElementById("report-intro").textContent = report.intro;
  document.getElementById("downloads").innerHTML = downloads.map(item => `<a href="${item.href}" download>⬇ ${escapeHtml(item.label)}</a>`).join("");
  const tabs = document.getElementById("report-tabs");
  tabs.innerHTML = "";
  report.sections.forEach((section, index) => {
    const button = document.createElement("button");
    button.textContent = section.name;
    button.onclick = () => {
      tabs.querySelectorAll("button").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      showSection(section);
    };
    tabs.appendChild(button);
    if (index === 0) button.click();
  });
  document.getElementById("result").hidden = false;
  document.getElementById("result").scrollIntoView({ behavior: "smooth" });
}

function fillYears(current) {
  const select = document.getElementById("year");
  for (let year = current; year >= current - 4; year--) select.add(new Option(`${year}-${year + 1}`, year));
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrf;
  if (options.body) headers["Content-Type"] = "application/json";
  const response = await fetch(BASE + path, { ...options, headers, credentials: "same-origin" });
  if (response.status === 401) {
    window.location.href = BASE + "?error=expired";
    throw new Error("Сеанс завершён.");
  }
  const data = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || "Сервер не смог выполнить запрос.");
  return data;
}

function remembered(key) {
  try { return window.localStorage.getItem(key) || ""; } catch (exc) { return ""; }
}

function remember(key, value) {
  try { window.localStorage.setItem(key, value); } catch (exc) { /* only a convenience */ }
}

const $ = id => document.getElementById(id);
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

function periodQuery() {
  return new URLSearchParams({
    year: $("year").value,
    odd_semester: $("semester").value === "odd",
    attestation: $("att").value,
  });
}

function showError(exc) {
  $("form-error").textContent = exc.message;
}

function fillSelect(select, items, placeholder, selected) {
  select.innerHTML = "";
  select.add(new Option(placeholder, ""));
  items.forEach(item => select.add(new Option(item.label, item.value)));
  select.value = items.some(item => item.value === selected) ? selected : "";
}

async function loadPeriodLists() {
  const query = periodQuery();
  const department = $("department").value || remembered(LAST_DEPARTMENT);
  const faculty = $("faculty").value;
  $("department").innerHTML = '<option value="">загрузка списка кафедр…</option>';
  const [facultyList, departments] = await Promise.all([
    api(`/api/faculties?${query}`),
    api(`/api/departments?${query}`),
  ]);
  faculties = facultyList;
  fillSelect($("faculty"), faculties.map(item => ({ value: item.id, label: item.label })), "выберите факультет", faculty);
  fillSelect($("department"), departments.map(name => ({ value: name, label: name })), "выберите кафедру", department);
  if ($("department").value && !faculty) await applyPreset();
  else await loadDirections(checkedCodes());
}

function checkedCodes() {
  return Array.from(document.querySelectorAll("#directions input:checked")).map(input => input.value);
}

async function applyPreset() {
  const department = $("department").value;
  if (!department) return;
  remember(LAST_DEPARTMENT, department);
  const preset = await api(`/api/preset?${new URLSearchParams({ department })}`);
  if (preset) {
    if (faculties.some(item => item.id === preset.faculty)) $("faculty").value = preset.faculty;
    $("faculty-title").value = preset.faculty_title || "";
    $("head-name").value = preset.head_name || "";
  } else {
    $("head-name").value = "";
  }
  await loadDirections(preset ? preset.codes : []);
}

async function loadDirections(codes) {
  const target = $("directions");
  const faculty = $("faculty").value;
  if (!faculty) {
    target.innerHTML = '<p class="hint">Сначала выберите факультет.</p>';
    return;
  }
  if (!$("faculty-title").value) {
    const item = faculties.find(entry => entry.id === faculty);
    $("faculty-title").value = item ? item.label : "";
  }
  target.innerHTML = '<p class="hint">Загружаю группы факультета…</p>';
  const query = periodQuery();
  query.set("faculty", faculty);
  const directions = await api(`/api/groups?${query}`);
  if (!directions.length) {
    target.innerHTML = '<p class="hint">У факультета нет групп с аттестацией за этот период.</p>';
    return;
  }
  const wanted = new Set(codes);
  target.innerHTML = "";
  ["б", "м"].forEach(level => {
    const items = directions.filter(item => item.level === level);
    if (!items.length) return;
    const title = document.createElement("h4");
    title.textContent = LEVEL_TITLES[level];
    const list = document.createElement("div");
    list.className = "direction-list";
    items.forEach(item => {
      const row = document.createElement("label");
      row.className = "direction";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.value = item.code;
      box.checked = wanted.has(item.code);
      const name = document.createElement("b");
      name.textContent = item.code;
      const groups = document.createElement("small");
      groups.textContent = item.groups.join(", ");
      row.append(box, name, groups);
      list.appendChild(row);
    });
    target.append(title, list);
  });
}

async function waitForJob(job) {
  const progress = $("progress");
  progress.hidden = false;
  while (job.status === "running") {
    progress.textContent = job.progress.length ? job.progress.join("\n") : "Начинаю выгрузку…";
    await sleep(2000);
    job = await api(`/api/jobs/${encodeURIComponent(job.id)}`);
  }
  progress.textContent = job.progress.join("\n");
  if (job.status === "failed") throw new Error(job.error || "Не удалось сформировать отчёт.");
  return job;
}

async function requestReport(event) {
  event.preventDefault();
  $("form-error").textContent = "";
  const codes = checkedCodes();
  if (!$("department").value || !$("faculty").value) {
    $("form-error").textContent = "Выберите кафедру и факультет.";
    return;
  }
  if (!codes.length) {
    $("form-error").textContent = "Отметьте хотя бы одно направление групп.";
    return;
  }
  const body = {
    year: Number($("year").value),
    odd_semester: $("semester").value === "odd",
    attestation: Number($("att").value),
    faculty: $("faculty").value,
    department: $("department").value,
    codes,
    faculty_title: $("faculty-title").value.trim(),
    head_name: $("head-name").value.trim(),
  };
  const button = $("submit");
  button.disabled = true;
  button.textContent = "Формирую отчёт, это займёт несколько минут…";
  $("result").hidden = true;
  try {
    const job = await waitForJob(await api("/api/jobs", { method: "POST", body: JSON.stringify(body) }));
    showReport(job.markdown, job.downloads, job.data);
  } catch (exc) {
    showError(exc);
  } finally {
    button.disabled = false;
    button.textContent = "Сформировать отчёт";
  }
}

async function logout() {
  try {
    await api("/logout", { method: "POST" });
  } finally {
    window.location.href = BASE;
  }
}

function guarded(action) {
  return () => {
    $("form-error").textContent = "";
    action().catch(showError);
  };
}

async function start() {
  // the login redirect leaves «?error=none» behind; it only matters when the cookie is lost
  if (window.location.search) window.history.replaceState(null, "", BASE);
  const me = await api("/api/me");
  csrf = me.csrf;
  $("who").textContent = me.login;
  fillYears(me.year);
  $("semester").value = me.odd_semester ? "odd" : "even";
  ["year", "semester", "att"].forEach(id => $(id).addEventListener("change", guarded(loadPeriodLists)));
  $("department").addEventListener("change", guarded(applyPreset));
  $("faculty").addEventListener("change", () => {
    $("faculty-title").value = "";
    guarded(() => loadDirections(checkedCodes()))();
  });
  $("logout").addEventListener("click", logout);
  $("report-form").addEventListener("submit", requestReport);
  await loadPeriodLists();
}

document.addEventListener("DOMContentLoaded", () => {
  start().catch(showError);
});

"use strict";

// Страница сервиса аттестации: запуск задачи, опрос её состояния и показ отчёта по разделам.
const BASE = "/attestation";
const STATUS_CLASSES = { "●": "s-ok", "▲": "s-warn", "✕": "s-crit" };
let csrf = "";

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
    target.innerHTML = renderMarkdown(section.body);
    if (section.name === "Дисциплины") addStatusFilter(toolbar, target);
    return;
  }
  const cards = section.cards.map(chunk => `<div class="card">${renderMarkdown(chunk)}</div>`);
  target.innerHTML = cards.join("");
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
  const active = new Set(["s-ok", "s-warn", "s-crit"]);
  [["s-crit", "✕ критично"], ["s-warn", "▲ внимание"], ["s-ok", "● норма"]].forEach(([cls, label]) => {
    const chip = document.createElement("button");
    chip.className = "chip on";
    chip.textContent = label;
    chip.onclick = () => {
      active.has(cls) ? active.delete(cls) : active.add(cls);
      chip.classList.toggle("on");
      target.querySelectorAll("tbody tr").forEach(row => {
        const statusCell = row.querySelector("td.s-ok, td.s-warn, td.s-crit");
        row.hidden = statusCell && !active.has(statusCell.className);
      });
    };
    toolbar.appendChild(chip);
  });
}

function showReport(markdown, downloads) {
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

function showSaved(login) {
  document.getElementById("saved").hidden = !login;
  document.getElementById("saved-login").textContent = login || "";
  toggleCredentials();
}

function usingSaved() {
  return !document.getElementById("saved").hidden && document.getElementById("use-saved").checked;
}

function toggleCredentials() {
  const saved = usingSaved();
  document.getElementById("credentials").hidden = saved;
  document.getElementById("remember-row").hidden = saved;
}

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function waitForJob(job) {
  const progress = document.getElementById("progress");
  progress.hidden = false;
  while (job.status === "running") {
    progress.textContent = job.progress.length ? job.progress.join("\n") : "Вход в РИТМ…";
    await sleep(2000);
    job = await api(`/api/jobs/${encodeURIComponent(job.id)}`);
  }
  progress.textContent = job.progress.join("\n");
  if (job.status === "failed") throw new Error(job.error || "Не удалось сформировать отчёт.");
  return job;
}

async function requestReport(event) {
  event.preventDefault();
  const error = document.getElementById("form-error");
  error.textContent = "";
  const level = document.getElementById("level").value;
  const body = {
    use_saved: usingSaved(),
    year: Number(document.getElementById("year").value),
    odd_semester: document.getElementById("semester").value === "odd",
    attestation: Number(document.getElementById("att").value),
    levels: level === "all" ? ["б", "м"] : [level],
  };
  if (!body.use_saved) {
    body.login = document.getElementById("login").value.trim();
    body.password = document.getElementById("password").value;
    body.remember = document.getElementById("remember").checked;
    if (!body.login || !body.password) {
      error.textContent = "Введите логин и пароль РИТМ.";
      return;
    }
  }
  const button = document.getElementById("submit");
  button.disabled = true;
  button.textContent = "Формирую отчёт, это займёт несколько минут…";
  document.getElementById("result").hidden = true;
  try {
    const started = await api("/api/jobs", { method: "POST", body: JSON.stringify(body) });
    document.getElementById("password").value = "";
    if (body.remember) showSaved(body.login);
    const job = await waitForJob(started);
    showReport(job.markdown, job.downloads);
  } catch (exc) {
    error.textContent = exc.message;
  } finally {
    document.getElementById("password").value = "";
    button.disabled = false;
    button.textContent = "Сформировать отчёт";
  }
}

async function forgetPassword() {
  try {
    await api("/api/vault/forget", { method: "POST" });
    showSaved(null);
  } catch (exc) {
    document.getElementById("form-error").textContent = exc.message;
  }
}

async function logout() {
  try {
    await api("/logout", { method: "POST" });
  } finally {
    window.location.href = BASE;
  }
}

async function start() {
  const me = await api("/api/me");
  csrf = me.csrf;
  fillYears(me.year);
  document.getElementById("semester").value = me.odd_semester ? "odd" : "even";
  showSaved(me.remembered_login);
  document.getElementById("use-saved").addEventListener("change", toggleCredentials);
  document.getElementById("forget").addEventListener("click", forgetPassword);
  document.getElementById("logout").addEventListener("click", logout);
  document.getElementById("report-form").addEventListener("submit", requestReport);
}

document.addEventListener("DOMContentLoaded", () => {
  start().catch(exc => { document.getElementById("form-error").textContent = exc.message; });
});

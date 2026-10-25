"use strict";

// Графики отчёта по данным report_model.model_data: сводка плитками, доля Н/А по группам
// с порогами и прошлой аттестацией, тепловая карта баллов группы. Только DOM и CSS, без
// библиотек: CSP страницы разрешает скрипты лишь с этого сайта. Имена групп, дисциплин и
// студентов приходят с портала, поэтому вставляются только через textContent.

const NBSP = " ";
const STATUS_ICONS = { "норма": "●", "внимание": "▲", "критично": "✕" };
const LEVEL_NAMES = { "б": "Бакалавриат", "м": "Магистратура" };

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}

function decimal(value, digits = 1) {
  return value.toFixed(digits).replace(".", ",");
}

function percent(value) {
  return `${decimal(value)}${NBSP}%`;
}

function share(part, total) {
  return total ? (part / total) * 100 : 0;
}

function score(value) {
  if (value === null || value === undefined) return "";
  return Number.isInteger(value) ? String(value) : decimal(value);
}

function shortName(fullName) {
  const parts = fullName.split(/\s+/).filter(Boolean);
  if (parts.length < 2) return fullName;
  return parts[0] + NBSP + parts.slice(1, 3).map(part => `${part[0]}.`).join(NBSP);
}

function plural(number, forms) {
  const tens = number % 100;
  const units = number % 10;
  if (units === 1 && tens !== 11) return forms[0];
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return forms[1];
  return forms[2];
}

function statusFor(rate, thresholds) {
  if (rate > thresholds.crit) return "критично";
  if (rate > thresholds.warn) return "внимание";
  return "норма";
}

function statusBadge(status) {
  const badge = el("span", `badge badge-${{ "норма": "ok", "внимание": "warn", "критично": "crit" }[status]}`);
  badge.append(el("span", "badge-icon", STATUS_ICONS[status]), document.createTextNode(` ${status}`));
  return badge;
}

// Изменение в процентных пунктах; goodWhenUp решает, какое направление считать улучшением
function deltaNode(value, goodWhenUp, suffix) {
  if (value === null || value === undefined) return null;
  const rounded = Math.round(value * 10) / 10;
  const node = el("span", "delta");
  if (rounded === 0) {
    node.textContent = `без изменений ${suffix}`.trim();
    return node;
  }
  const better = goodWhenUp ? rounded > 0 : rounded < 0;
  node.classList.add(better ? "delta-good" : "delta-bad");
  node.textContent = `${rounded > 0 ? "▲ +" : "▼ −"}${decimal(Math.abs(rounded))}${NBSP}п.${NBSP}п. ${suffix}`.trim();
  return node;
}

// --- Подсказка: одна на страницу, по наведению и по фокусу ---------------------------------

const tooltip = (() => {
  let node = null;
  function ensure() {
    if (!node) {
      node = el("div", "chart-tooltip");
      node.setAttribute("role", "tooltip");
      node.hidden = true;
      document.body.appendChild(node);
    }
    return node;
  }
  return {
    show(lines, x, y) {
      const box = ensure();
      box.replaceChildren(...lines.map((line, index) => el("div", index === 0 ? "tip-value" : "tip-label", line)));
      box.hidden = false;
      const width = box.offsetWidth;
      const height = box.offsetHeight;
      const left = Math.min(x + 14, window.innerWidth - width - 8);
      const top = y + height + 20 > window.innerHeight ? y - height - 12 : y + 16;
      box.style.left = `${Math.max(8, left)}px`;
      box.style.top = `${Math.max(8, top)}px`;
    },
    hide() {
      if (node) node.hidden = true;
    },
  };
})();

function withTooltip(target, lines) {
  target.addEventListener("pointermove", event => tooltip.show(lines(), event.clientX, event.clientY));
  target.addEventListener("pointerleave", () => tooltip.hide());
  target.addEventListener("focus", () => {
    const box = target.getBoundingClientRect();
    tooltip.show(lines(), box.left + box.width / 2, box.bottom);
  });
  target.addEventListener("blur", () => tooltip.hide());
}

// --- Сводка плитками ------------------------------------------------------------------------

function tile(label, value, details) {
  const node = el("div", "tile");
  node.append(el("div", "tile-label", label), el("div", "tile-value", value));
  details.filter(Boolean).forEach(detail => {
    node.appendChild(typeof detail === "string" ? el("div", "tile-note", detail) : detail);
  });
  return node;
}

function renderSummaryTiles(data) {
  const summary = data.summary;
  const comparison = summary.comparison;
  const vs = comparison ? `к аттестации №${comparison.attestation}` : "";
  const tiles = el("div", "tiles");
  tiles.appendChild(tile("Студентов", String(summary.students), [
    `${summary.groups} ${plural(summary.groups, ["группа", "группы", "групп"])}`,
  ]));
  tiles.appendChild(tile("Аттестованы полностью", String(summary.fully_attested), [
    `${percent(share(summary.fully_attested, summary.students))} студентов`,
    comparison && deltaNode(comparison.fully_attested_delta, true, vs),
  ]));
  const status = statusFor(summary.failure_rate, data.thresholds);
  tiles.appendChild(tile("Доля Н/А", percent(summary.failure_rate), [
    statusBadge(status),
    comparison && deltaNode(comparison.failure_delta, false, vs),
  ]));
  tiles.appendChild(tile("0 баллов", percent(share(summary.zero, summary.failed)), [
    `неаттестаций: ${summary.zero} ${plural(summary.zero, ["оценка", "оценки", "оценок"])} из ${summary.failed}`,
  ]));
  tiles.appendChild(tile(
    "Не выставлено",
    summary.not_entered_disciplines ? String(summary.not_entered_disciplines) : "нет",
    [
      summary.not_entered_disciplines
        ? `${plural(summary.not_entered_disciplines, ["дисциплина", "дисциплины", "дисциплин"])} с нулями у всей группы, ${percent(share(summary.not_entered, summary.failed))} неаттестаций`
        : "дисциплин, где у всей группы 0 баллов",
    ],
  ));
  if (summary.rank) {
    tiles.appendChild(tile("Место кафедры", `${summary.rank.place} из ${summary.rank.total}`, [
      `${percent(summary.rank.failure_rate)} Н/А при среднем по вузу ${percent(summary.rank.university_rate)}`,
    ]));
  }
  return tiles;
}

// --- Доля Н/А по группам --------------------------------------------------------------------

const SEGMENTS = [
  { key: "zero", label: "0 баллов", className: "seg-zero" },
  { key: "below", label: "ниже минимума", className: "seg-below" },
  { key: "not_entered", label: "не выставлено", className: "seg-none" },
];

function legendItem(className, label) {
  const item = el("span", "legend-item");
  item.append(el("span", `legend-key ${className}`), document.createTextNode(label));
  return item;
}

function groupParts(group) {
  return {
    zero: group.zero,
    below: group.failed - group.zero - group.not_entered,
    not_entered: group.not_entered,
  };
}

function groupRow(group, data, previousNumber) {
  const parts = groupParts(group);
  const row = el("div", "gchart-row");
  row.tabIndex = 0;

  const label = el("div", "gchart-label");
  label.append(el("span", "gchart-name", group.name), el("span", "gchart-meta", `${group.students} студ.`));

  const track = el("div", "gchart-track");
  [data.thresholds.warn, data.thresholds.crit].forEach(value => {
    const line = el("span", "gchart-threshold");
    line.style.left = `${value}%`;
    track.appendChild(line);
  });
  const bar = el("div", "gchart-bar");
  SEGMENTS.forEach(segment => {
    if (!parts[segment.key]) return;
    const piece = el("span", `gchart-seg ${segment.className}`);
    // доли полосы — пропорционально числу оценок, за вычетом зазоров между частями
    piece.style.flex = `${parts[segment.key]} 1 0px`;
    bar.appendChild(piece);
  });
  bar.style.width = `${group.failure_rate}%`;
  track.appendChild(bar);
  if (group.previous_rate !== null) {
    const marker = el("span", "gchart-previous");
    marker.style.left = `${group.previous_rate}%`;
    track.appendChild(marker);
  }

  const value = el("div", "gchart-value");
  value.appendChild(el("span", "gchart-rate", percent(group.failure_rate)));
  if (group.previous_rate !== null) {
    value.appendChild(deltaNode(group.failure_rate - group.previous_rate, false, ""));
  }
  value.appendChild(statusBadge(group.status));

  row.append(label, track, value);
  withTooltip(row, () => {
    const lines = [
      `${percent(group.failure_rate)} Н/А — ${group.name}`,
      `неаттестаций ${group.failed} из ${group.records} оценок`,
      `0 баллов: ${parts.zero}, ниже минимума: ${parts.below}`,
    ];
    if (parts.not_entered) lines.push(`не выставлено: ${parts.not_entered}`);
    if (group.previous_rate !== null) lines.push(`аттестация №${previousNumber}: ${percent(group.previous_rate)}`);
    lines.push(`аттестованы полностью: ${group.fully_attested} из ${group.students}`);
    return lines;
  });
  return row;
}

function renderGroupChart(data) {
  const figure = el("figure", "chart");
  figure.appendChild(el("figcaption", "chart-title", "Доля неаттестаций по группам"));
  figure.appendChild(el(
    "p",
    "chart-subtitle",
    `Линии — пороги: до ${data.thresholds.warn} % норма, до ${data.thresholds.crit} % внимание, выше — критично. ` +
      "Полоса делится на нулевые баллы и баллы ниже минимума.",
  ));

  const comparison = data.summary.comparison;
  const legend = el("div", "legend");
  SEGMENTS.forEach(segment => {
    if (segment.key === "not_entered" && !data.summary.not_entered) return;
    legend.appendChild(legendItem(segment.className, segment.label));
  });
  if (comparison) legend.appendChild(legendItem("key-previous", `аттестация №${comparison.attestation}`));
  figure.appendChild(legend);

  const previousNumber = comparison ? comparison.attestation : null;
  ["б", "м"].forEach(level => {
    const groups = data.groups.filter(group => group.level === level);
    if (!groups.length) return;
    const block = el("div", "gchart-block");
    block.appendChild(el("div", "gchart-level", LEVEL_NAMES[level]));
    groups
      .slice()
      .sort((a, b) => b.failure_rate - a.failure_rate || a.name.localeCompare(b.name, "ru"))
      .forEach(group => block.appendChild(groupRow(group, data, previousNumber)));
    figure.appendChild(block);
  });

  const axis = el("div", "gchart-row gchart-axis");
  axis.appendChild(el("div"));
  const ticks = el("div", "gchart-ticks");
  [0, data.thresholds.warn, data.thresholds.crit, 100].forEach(value => {
    const tick = el("span", "gchart-tick", `${value}${NBSP}%`);
    tick.style.left = `${value}%`;
    ticks.appendChild(tick);
  });
  axis.append(ticks, el("div"));
  figure.appendChild(axis);
  return figure;
}

// --- Тепловая карта группы ------------------------------------------------------------------

const CELLS = [
  { className: "h-ok", label: "аттестован" },
  { className: "h-near", label: "почти (от 80 % минимума)" },
  { className: "h-below", label: "ниже минимума" },
  { className: "h-zero", label: "0 баллов" },
  { className: "h-none", label: "не выставлено" },
];

function cellKind(value, discipline, nearShare) {
  if (value === null || value === undefined) return { className: "h-empty", text: "", label: "нет оценки" };
  if (discipline.not_entered) return { className: "h-none", text: "—", label: "не выставлено у всей группы" };
  if (value === 0) return { className: "h-zero", text: "0", label: "0 баллов" };
  if (value < discipline.threshold) {
    return value >= nearShare * discipline.threshold
      ? { className: "h-near", text: score(value), label: "почти: ниже минимума менее чем на 20 %" }
      : { className: "h-below", text: score(value), label: "ниже минимума" };
  }
  return { className: "h-ok", text: score(value), label: "аттестован" };
}

function renderHeatmap(group, data) {
  const figure = el("figure", "chart heat");
  figure.appendChild(el("figcaption", "chart-title", "Баллы студентов по дисциплинам"));
  figure.appendChild(el(
    "p",
    "chart-subtitle",
    "Столбцы — дисциплины по номерам из списка под таблицей, в строке «мин.» — минимальный балл. " +
      "Красный столбец почти всегда значит проблему дисциплины, красная строка — проблему студента.",
  ));
  const legend = el("div", "legend");
  CELLS.forEach(cell => {
    if (cell.className === "h-none" && !group.not_entered) return;
    legend.appendChild(legendItem(`key-cell ${cell.className}`, cell.label));
  });
  figure.appendChild(legend);

  const table = el("table", "heat-table");
  const head = el("thead");
  const numbers = el("tr");
  numbers.appendChild(el("th", "heat-corner", "Студент"));
  group.disciplines.forEach((discipline, index) => {
    const th = el("th", "heat-col", String(index + 1));
    th.scope = "col";
    th.title = discipline.subject;
    numbers.appendChild(th);
  });
  numbers.appendChild(el("th", "heat-total", "Н/А"));
  const minimums = el("tr", "heat-min");
  minimums.appendChild(el("th", "heat-corner", "мин."));
  group.disciplines.forEach(discipline => minimums.appendChild(el("td", "", score(discipline.threshold))));
  minimums.appendChild(el("td"));
  head.append(numbers, minimums);
  table.appendChild(head);

  const body = el("tbody");
  group.students_scores.forEach(student => {
    const row = el("tr");
    const name = el("th", "heat-name", shortName(student.name));
    name.scope = "row";
    row.appendChild(name);
    student.scores.forEach((value, index) => {
      const discipline = group.disciplines[index];
      const kind = cellKind(value, discipline, data.thresholds.near_share);
      const cell = el("td", `heat-cell ${kind.className}`, kind.text);
      withTooltip(cell, () => [
        value === null || value === undefined ? "нет оценки" : `${score(value)} из минимума ${score(discipline.threshold)}`,
        student.name,
        `${index + 1}. ${discipline.subject}`,
        kind.label,
      ]);
      row.appendChild(cell);
    });
    row.appendChild(el("td", "heat-total", `${student.failed} из ${student.subjects}`));
    body.appendChild(row);
  });
  table.appendChild(body);

  const wrap = el("div", "heat-wrap");
  wrap.appendChild(table);
  figure.appendChild(wrap);

  const list = el("ol", "heat-subjects");
  group.disciplines.forEach(discipline => {
    const item = el("li");
    item.appendChild(el("span", "", discipline.subject));
    const notes = [
      discipline.teachers.length ? discipline.teachers.join(", ") : null,
      `Н/А ${discipline.failed} из ${discipline.students}`,
      discipline.not_entered ? "не выставлено" : null,
    ].filter(Boolean);
    item.appendChild(el("span", "heat-subject-note", ` — ${notes.join(" · ")}`));
    list.appendChild(item);
  });
  figure.appendChild(list);
  return figure;
}

import { dispositionColours, dispositionLabels, getCatalogue, getNeighbours, getProjectionAudit, getReleaseComparison, getStability } from "./model";
import type { CandidateAudit, Catalogue, Disposition, Lookup, Neighbour, Observation, Position, ProjectionAudit, ReleaseComparison, Stability } from "./model";
import { auditGroup, auditGroups, auditTable, readAuditFilter, type AuditFilter } from "./projection-audit";
import { releaseMeasurements } from "./release-view";
import { checkStudy, makeStudy, openStudyFile, parseStudy, saveStudyFile } from "./study-file";
import type { StudyView } from "./study-file";
import type { SignalScene } from "./scene";
import { showOpening } from "./opening";
import { arrive, motionAllowed } from "./ui-motion";

const byId = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const query = byId<HTMLInputElement>("query");
const search = byId<HTMLFormElement>("search");
const submit = search.querySelector("button")!;
const exampleButton = byId<HTMLButtonElement>("example");
const reset = byId<HTMLButtonElement>("reset");
const focusButton = byId<HTMLButtonElement>("focus-neighbours");
const projectedLines = byId("projected-lines");
const error = byId("error");
const ranks = byId("ranks");
const detail = byId("detail");
const uncertainty = byId("uncertainty");
const projection = byId("projection");
const summary = byId("summary");
const legend = byId("legend");
const stabilityPanel = byId("stability");
const stabilityButton = byId<HTMLButtonElement>("run-stability");
const stabilityStatus = byId("stability-status");
const stabilityDetails = byId("stability-result");
const plotTitle = byId("plot-title");
const plotStatus = byId("plot-status");
const scenarioControls = byId("scenario-controls");
const scenarioSlider = byId<HTMLInputElement>("scenario-slider");
const scenarioReadout = byId("scenario-readout");
const expandButton = byId<HTMLButtonElement>("expand-plot");
const plotPanel = expandButton.closest<HTMLElement>(".plot-panel")!;
const plotModal = byId<HTMLDialogElement>("plot-modal");
const plotHome = document.createComment("Plot workspace position");
plotPanel.after(plotHome);
const inspectorScroll = byId("inspector-scroll");
const detailSection = byId<HTMLDetailsElement>("detail-section");
const rankingSection = byId<HTMLDetailsElement>("ranking-section");
const jumpRanking = byId<HTMLButtonElement>("jump-ranking");
const jumpDistance = byId<HTMLButtonElement>("jump-distance");
const releaseButton = byId<HTMLButtonElement>("compare-release");
const releaseEarlier = byId<HTMLButtonElement>("release-dr24");
const releaseCurrent = byId<HTMLButtonElement>("release-current");
const releaseControls = byId("release-controls");
const releaseFallback = byId("release-fallback");
const releaseInspector = byId("release-inspector");
const auditButton = byId<HTMLButtonElement>("audit-projection");
const auditControls = byId("audit-controls");
const auditInspector = byId<HTMLDetailsElement>("audit-inspector");
const auditFilterControl = byId<HTMLSelectElement>("audit-filter");
const openStudyButton = byId<HTMLButtonElement>("open-study");
const saveStudyButton = byId<HTMLButtonElement>("save-study");
const studyFileStatus = byId("study-status");
const number = new Intl.NumberFormat("en-GB", { maximumSignificantDigits: 10 });
const candidateColour = "#e3b6ff";
const neighbourColour = "#ffe39a";
const activeColour = "#ffc265";
const stableColour = "#52dfce";
const changedColour = "#ff9b79";
const replacementColour = "#d1a0ff";
const historicalColour = "#6de0eb";
const cumulativeColour = "#e4adff";
const comparisonExample = "K00005.01";
const projectedColour = "#80dfff";

interface AuditData {
  report: ProjectionAudit;
  byId: Map<string, CandidateAudit>;
  strongestMismatch?: CandidateAudit;
}

let catalogue: Catalogue;
let scene: SignalScene | undefined;
let lookup: Lookup | undefined;
let visibleLookup: Lookup | undefined;
let active = 0;
let example = false;
let focused = false;
let study: Stability | undefined;
let pendingStudy: Lookup | undefined;
let scenario = 0;
let releaseReport: ReleaseComparison | undefined;
let pendingRelease: Lookup | undefined;
let showingEarlier = false;
let auditData: AuditData | undefined;
let auditRequest: symbol | undefined;
let auditPromise: Promise<AuditData> | undefined;
let auditFilter: AuditFilter = "all";
let latestRequest = 0;
let fileBusy = false;

function element<K extends keyof HTMLElementTagNameMap>(tag: K, text: string, className?: string) {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

function point(row: Observation, colour: string, selectable = false) {
  return { id: row.koi_id, position: row.position, colour, selectable };
}

function drawLegend(entries: [string, string][]) {
  legend.replaceChildren(...entries.map(([label, colour]) => {
    const swatch = element("span", "", "swatch");
    swatch.style.setProperty("--swatch", colour);
    const item = element("li", "");
    item.append(swatch, document.createTextNode(label));
    return item;
  }));
}

function drawCatalogue() {
  const dispositions = Object.keys(dispositionLabels) as Disposition[];
  scene?.show(catalogue.observations.map((row) =>
    point(row, dispositionColours[row.disposition], row.disposition === "CANDIDATE")));
  const share = (value: number) => `${(100 * value).toFixed(1)}%`;
  const variance = catalogue.variance_ratios.reduce((total, ratio) => total + ratio, 0);
  projection.textContent = `PCA projection · ${share(variance)} of training variance retained`;
  projection.title = catalogue.variance_ratios
    .map((ratio, index) => `PC${index + 1} ${share(ratio)}`).join(" · ");
  drawLegend([
    ...dispositions.map((label): [string, string] => [dispositionLabels[label], dispositionColours[label]]),
    ["Selected query", candidateColour],
    ["8D neighbours", neighbourColour],
  ]);
}

function drawLookup(result: Lookup) {
  visibleLookup = result;
  syncStudyButtons();
  jumpRanking.disabled = jumpDistance.disabled = false;
  stabilityPanel.hidden = !study;
  releaseInspector.hidden = !releaseReport;
  const audit = auditData?.byId.get(result.query.koi_id);
  auditInspector.hidden = !audit;
  if (audit) {
    const outsideFilter = auditFilter !== "all" && auditGroup(audit.shared) !== auditFilter;
    byId("audit-selection").textContent = `${audit.shared}/5 shared · ${number.format(audit.eligible_references)} eligible references${outsideFilter ? " · Outside filter" : ""}`;
    byId("audit-table").replaceChildren(auditTable(audit));
  }
  const view = releaseReport ? showingEarlier ? "DR24" : "Cumulative" : scenario ? `Scenario ${scenario}` : "";
  const label = view ? `${view} · ${result.query.koi_id}` : result.query.koi_id;
  summary.textContent = `${label} · ${number.format(result.eligible_references)} eligible references · ${result.same_host_excluded} same-star exclusions`;
  const flags = [];
  if (result.mixed_dispositions) flags.push("The five neighbours have mixed archive dispositions.");
  if (result.distant) {
    flags.push(`The fifth distance exceeds ${catalogue.distance_threshold.toFixed(3)}, the 95th percentile measured on held-out validation hosts.`);
  }
  uncertainty.textContent = flags.join(" ");
  uncertainty.hidden = !flags.length;
  ranks.replaceChildren(...result.neighbours.map((neighbour, index) => {
    const row = neighbour.observation;
    const button = element("button", "", "rank");
    button.type = "button";
    button.dataset.koi = row.koi_id;
    button.setAttribute("aria-pressed", String(index === active));
    const identity = element("span", "", "identity");
    identity.append(
      element("strong", row.koi_id),
      element("small", dispositionLabels[row.disposition]),
    );
    button.append(element("span", String(index + 1), "order"), identity,
      element("span", neighbour.distance.toFixed(6), "distance"));
    button.addEventListener("click", () => {
      active = index;
      [...ranks.querySelectorAll("button")].forEach((node, rank) =>
        node.setAttribute("aria-pressed", String(rank === index)));
      showDetail(result, neighbour);
      highlight(result);
      revealDistance();
    });
    const listItem = element("li", "");
    listItem.append(button);
    return listItem;
  }));
  arrive(ranks.children, 5);
  showDetail(result, result.neighbours[active]);
  highlight(result);
}

function revealDistance() {
  if (detailSection.open) arrive([detail], 6);
  revealInspector(detailSection, false);
}

function revealInspector(details: HTMLDetailsElement, alwaysAlign: boolean) {
  details.open = true;
  const pane = inspectorScroll.getBoundingClientRect();
  const section = details.getBoundingClientRect();
  if (alwaysAlign || section.top < pane.top || section.bottom > pane.bottom) {
    inspectorScroll.scrollTo({
      top: Math.max(0, inspectorScroll.scrollTop + section.top - pane.top - 5),
      behavior: motionAllowed() ? "smooth" : "instant",
    });
  }
}

function drawStability(result: Stability) {
  const list = element("ul", "", "stability-bars");
  list.setAttribute("aria-label", "Original neighbours retained in the top five");
  for (const item of result.baseline) {
    const row = element("li", "");
    const meter = document.createElement("meter");
    meter.max = result.trials;
    meter.value = item.appearances;
    meter.setAttribute("aria-label", item.koi_id);
    row.append(element("span", item.koi_id), meter, element("span", `${item.appearances}/${result.trials}`));
    list.append(row);
  }
  const details = document.createElement("details");
  const ranges = element("dl", "", "stability-ranges");
  for (const item of result.measurements) {
    const values = item.bounds
      ? item.bounds.map((value) => number.format(value)).join(" to ")
      : `${number.format(item.original)} (fixed)`;
    ranges.append(element("dt", item.name), element("dd", `${values} ${item.unit}`));
  }
  details.append(
    element("summary", "Measurement ranges and method"),
    ranges,
    element("p", `Quoted errors retrieved ${result.source_date}. Each scenario varies the candidate within the available ranges and keeps references fixed. Correlations between errors are unknown.`),
  );
  stabilityDetails.replaceChildren(list);
  if (result.replacements.length) {
    const example = result.replacements[0];
    stabilityDetails.append(element("p", `Most frequent replacement: ${example.koi_id} (${example.appearances}/${result.trials}).`));
  }
  stabilityDetails.append(details);
}

function clearStudy() {
  study = undefined;
  pendingStudy = undefined;
  scenario = 0;
  releaseReport = undefined;
  pendingRelease = undefined;
  showingEarlier = false;
  auditData = undefined;
  auditRequest = undefined;
  auditControls.hidden = auditInspector.hidden = true;
  auditButton.disabled = !lookup || example;
  auditButton.textContent = "Audit projection";
  auditButton.setAttribute("aria-pressed", "false");
  scenarioControls.hidden = stabilityPanel.hidden = plotStatus.hidden = true;
  delete plotStatus.dataset.loading;
  releaseControls.hidden = releaseInspector.hidden = releaseFallback.hidden = true;
  stabilityButton.disabled = !lookup || example;
  stabilityButton.textContent = "Explore uncertainty";
  stabilityButton.setAttribute("aria-pressed", "false");
  releaseButton.disabled = !lookup || example;
  releaseButton.textContent = "Compare releases";
  releaseButton.setAttribute("aria-pressed", "false");
  stabilityDetails.replaceChildren();
  setFocus(false);
}

function selectScenario(index: number) {
  if (!study || !lookup || !Number.isInteger(index) || index < 0 || index > study.scenarios.length) return;
  scenario = index;
  active = 0;
  scenarioSlider.value = String(index);
  const trial = study.scenarios[index - 1];
  if (!trial) {
    scenarioReadout.textContent = `Catalogue values · nearest ${lookup.neighbours[0].observation.koi_id}`;
    scenarioSlider.setAttribute("aria-valuetext", "Catalogue values");
    drawLookup(lookup);
    return;
  }
  const changed = trial.same_first ? "same nearest neighbour" : "different nearest neighbour";
  scenarioReadout.textContent = `Scenario ${index} of ${study.trials} · ${trial.neighbours[0].observation.koi_id} · ${changed}`;
  scenarioSlider.setAttribute("aria-valuetext", scenarioReadout.textContent);
  drawLookup(variationLookup(lookup, { ...lookup.query, position: trial.position, values: trial.values }, trial.neighbours));
}

function variationLookup(nominal: Lookup, query: Observation, neighbours: Neighbour[]): Lookup {
  return {
    ...nominal,
    query,
    neighbours,
    mixed_dispositions: neighbours.some((item) =>
      item.observation.disposition !== neighbours[0].observation.disposition),
    distant: neighbours.at(-1)!.distance > catalogue.distance_threshold,
  };
}

async function runStability(prefetched?: Stability, initialScenario = 1) {
  const current = lookup;
  if (!current || example || pendingStudy) return;
  if (releaseReport || pendingRelease || auditData || auditRequest) setExample(false);
  releaseFallback.hidden = true;
  pendingStudy = current;
  stabilityButton.disabled = true;
  plotStatus.dataset.loading = "";
  plotStatus.textContent = "Recomputing neighbours across the quoted measurement ranges…";
  plotStatus.hidden = false;
  try {
    const result = prefetched ?? await getStability(current.query.koi_id);
    if (lookup !== current || pendingStudy !== current) return;
    study = result;
    plotStatus.hidden = true;
    plotTitle.textContent = "Uncertainty explorer";
    stabilityButton.textContent = "Back to catalogue";
    stabilityButton.setAttribute("aria-pressed", "true");
    scenarioControls.hidden = false;
    scenarioSlider.max = String(result.scenarios.length);
    byId("results-title").textContent = "8D neighbours";
    byId("controls").textContent = "Drag to orbit · Select a scenario point";
    const originals = new Set(result.baseline.map((item) => item.koi_id));
    const references = new Map<string, Observation>();
    for (const nominal of current.neighbours) references.set(nominal.observation.koi_id, nominal.observation);
    for (const trial of result.scenarios) {
      for (const neighbour of trial.neighbours) references.set(neighbour.observation.koi_id, neighbour.observation);
    }
    scene?.showStudy(
      result.scenarios.map((trial, index) => ({
        id: String(index + 1),
        position: trial.position,
        colour: trial.same_first ? stableColour : changedColour,
        selectable: true,
      })),
      [...references.values()].map((row) => point(row, originals.has(row.koi_id) ? neighbourColour : replacementColour)),
      point(current.query, candidateColour),
    );
    setFocus(true);
    drawLegend([
      ["Same nearest", stableColour],
      ["Different nearest", changedColour],
      ["Catalogue position", candidateColour],
      ["Original neighbour", neighbourColour],
      ["Replacement neighbour", replacementColour],
    ]);
    stabilityStatus.textContent = `Same five neighbours in ${result.same_top_five}/${result.trials} scenarios. Same nearest neighbour in ${result.same_first}/${result.trials}.`;
    drawStability(result);
    selectScenario(initialScenario);
    arrive([scenarioControls, stabilityPanel], 7);
  } catch (problem) {
    if (pendingStudy === current) plotStatus.textContent = String(problem);
  } finally {
    if (pendingStudy === current) {
      pendingStudy = undefined;
      stabilityButton.disabled = false;
      delete plotStatus.dataset.loading;
    }
  }
}

function selectRelease(earlier: boolean) {
  if (!releaseReport || !lookup) return;
  const result = releaseReport;
  showingEarlier = earlier;
  active = 0;
  releaseEarlier.setAttribute("aria-pressed", String(earlier));
  releaseCurrent.setAttribute("aria-pressed", String(!earlier));
  byId("release-readout").textContent = `Nearest ${earlier ? result.earlier_nearest : result.current_nearest} · ${result.retained_neighbours}/5 shared`;
  if (!earlier) {
    drawLookup(lookup);
    return;
  }
  drawLookup(variationLookup(lookup, result.earlier_query, result.earlier_neighbours));
}

async function runRelease(prefetched?: ReleaseComparison, initialEarlier = true) {
  const current = lookup;
  if (!current || example || pendingRelease) return;
  if (study || pendingStudy || auditData || auditRequest) setExample(false);
  pendingRelease = current;
  releaseButton.disabled = true;
  plotStatus.dataset.loading = "";
  releaseFallback.hidden = true;
  plotStatus.textContent = "Comparing the two sets of measurements in the same model…";
  plotStatus.hidden = false;
  try {
    const result = prefetched ?? await getReleaseComparison(current.query.koi_id);
    if (lookup !== current || pendingRelease !== current) return;
    releaseReport = result;
    plotStatus.hidden = true;
    plotTitle.textContent = "Release comparison";
    releaseButton.textContent = "Back to catalogue";
    releaseButton.setAttribute("aria-pressed", "true");
    releaseControls.hidden = false;
    byId("results-title").textContent = "8D neighbours";
    byId("controls").textContent = "Drag to orbit · Select a release point";
    projectedLines.textContent = "The cyan line connects the two projected catalogue positions.";

    const references = new Map<string, Observation>();
    for (const item of [...current.neighbours, ...result.earlier_neighbours]) {
      references.set(item.observation.koi_id, item.observation);
    }
    const dr24 = { ...point(result.earlier_query, historicalColour, true), id: "DR24" };
    const cumulative = { ...point(current.query, cumulativeColour, true), id: "Cumulative" };
    scene?.showStudy(
      [dr24, cumulative], [...references.values()].map(row => point(row, neighbourColour)), cumulative, true,
    );
    setFocus(true);
    drawLegend([
      ["DR24", historicalColour], ["Cumulative", cumulativeColour], ["8D neighbours", neighbourColour],
    ]);
    byId("release-summary").textContent =
      `${result.earlier_nearest} → ${result.current_nearest} · ${result.retained_neighbours}/5 shared · 8D shift ${result.standardised_shift.toFixed(4)} · projected shift ${result.projected_shift.toFixed(4)}.`;
    byId("release-measurements").replaceChildren(releaseMeasurements(result, current.query, catalogue.features));
    byId("release-provenance").textContent =
      `${result.release} updated ${result.release_last_updated} · extract ${result.retrieved_utc_date}. Both rankings use the same scaler and reference set. The linked points show changes in reported measurements.`;
    selectRelease(initialEarlier);
    arrive([releaseControls, releaseInspector], 7);
  } catch (problem) {
    if (pendingRelease !== current) return;
    plotStatus.textContent = String(problem);
    releaseFallback.hidden = !String(problem).startsWith("No matched DR24");
  } finally {
    if (pendingRelease === current) {
      pendingRelease = undefined;
      releaseButton.disabled = false;
      delete plotStatus.dataset.loading;
    }
  }
}

function highlight(result: Lookup) {
  const neighbours = result.neighbours.map((item, index) =>
    point(item.observation, index === active ? activeColour : neighbourColour));
  const queryPoint = point(result.query, releaseReport ? showingEarlier ? historicalColour : cumulativeColour : candidateColour);
  if (releaseReport) queryPoint.id = showingEarlier ? "DR24" : "Cumulative";
  else if (scenario) queryPoint.id = `Scenario ${scenario}`;
  const projected = auditData?.byId.get(result.query.koi_id)?.projected_neighbours.flatMap((item, index) =>
    item.full_rank > 5 ? [{ position: item.position, colour: projectedColour, id: `P${index + 1}` }] : []);
  scene?.highlight(queryPoint, neighbours, active, projected);
  focusButton.hidden = projectedLines.hidden = !scene || example;
}

function setFocus(value: boolean) {
  focused = value;
  focusButton.setAttribute("aria-pressed", String(value));
  focusButton.textContent = value ? "Show full plot" : releaseReport ? "Focus on releases" : study ? "Focus on scenarios"
    : auditData ? "Focus on both rankings" : "Focus on neighbours";
  scene?.setFocus(value);
}

function loadAudit(): Promise<AuditData> {
  return auditPromise ??= getProjectionAudit().then((report) => {
    let strongestMismatch: CandidateAudit | undefined;
    for (const candidate of report.candidates) {
      if (candidate.shared === 0 && (!strongestMismatch ||
          candidate.projected_neighbours[0].full_rank > strongestMismatch.projected_neighbours[0].full_rank)) {
        strongestMismatch = candidate;
      }
    }
    return { report, byId: new Map(report.candidates.map(row => [row.koi_id, row])), strongestMismatch };
  }).catch((problem: unknown) => {
    auditPromise = undefined;
    throw problem;
  });
}

function showAudit(data: AuditData, filter: AuditFilter) {
  if (!lookup) return;
  auditData = data;
  auditFilter = filter;
  auditFilterControl.value = filter;
  const { report, byId: rows } = data;
  const groups = Object.entries(auditGroups).filter(([group]) => filter === "all" || group === filter);
  const visible = report.candidates.filter(row => filter === "all" || auditGroup(row.shared) === filter).length;
  const points = catalogue.observations.flatMap((row) => {
    const candidate = rows.get(row.koi_id);
    if (!candidate) return [point(row, "#465467")];
    const group = auditGroup(candidate.shared);
    return filter === "all" || group === filter ? [point(row, auditGroups[group].colour, true)] : [];
  });
  scene?.show(points);
  setFocus(false);
  plotTitle.textContent = "Projection audit";
  byId("results-title").textContent = "Neighbour comparison";
  auditButton.textContent = "Back to catalogue";
  auditButton.setAttribute("aria-pressed", "true");
  auditControls.hidden = false;
  auditInspector.open = true;
  byId<HTMLButtonElement>("audit-example").disabled = !data.strongestMismatch;
  byId("audit-overview").textContent = `${number.format(visible)} of ${number.format(report.candidates.length)} shown · Nearest neighbour changes for ${number.format(report.changed_nearest)} across the catalogue`;
  byId("controls").textContent = "Drag to orbit · Select a candidate";
  projectedLines.textContent = "Gold numbers show 8D ranks. Cyan P markers appear only in the 3D top five.";
  drawLegend([
    ...groups.map(([, group]): [string, string] => [group.label, group.colour]),
    ["8D top five", neighbourColour],
    ["3D-only top five", projectedColour],
  ]);
  drawLookup(lookup);
}

async function runAudit() {
  if (!lookup || auditRequest) return;
  if (example || study || pendingStudy || releaseReport || pendingRelease) setExample(false);
  const request = Symbol();
  auditRequest = request;
  auditButton.disabled = true;
  plotStatus.dataset.loading = "";
  plotStatus.textContent = "Comparing 3D and 8D neighbours across the catalogue…";
  plotStatus.hidden = false;
  try {
    const data = await loadAudit();
    if (auditRequest !== request) return;
    plotStatus.hidden = true;
    showAudit(data, "all");
    inspectorScroll.scrollTop = 0;
    arrive([auditControls, auditInspector], 7);
  } catch (problem) {
    if (auditRequest === request) plotStatus.textContent = String(problem);
  } finally {
    if (auditRequest === request) {
      auditRequest = undefined;
      auditButton.disabled = false;
      delete plotStatus.dataset.loading;
    }
  }
}

function showDetail(result: Lookup, neighbour: Neighbour) {
  const row = neighbour.observation;
  const table = document.createElement("table");
  table.setAttribute("aria-label", "Feature contributions to squared distance");
  const heading = table.createTHead().insertRow();
  ["Measurement", releaseReport ? showingEarlier ? "DR24" : "Cumulative" : scenario ? "Scenario" : "Query", "Neighbour", "Share"].forEach((label) =>
    heading.append(element("th", label)));
  const body = table.createTBody();
  const ordered = catalogue.features.map((feature, index) => ({ feature, index }))
    .sort((a, b) => neighbour.squared_deltas[b.index] - neighbour.squared_deltas[a.index]);
  ordered.forEach(({ feature, index }) => {
    const entry = body.insertRow();
    const name = element("th", feature.name);
    name.scope = "row";
    name.append(element("small", feature.unit));
    entry.append(name);
    const measured = entry.insertCell();
    measured.textContent = number.format(result.query.values[index]);
    if (scenario && lookup) measured.title = `Catalogue value ${number.format(lookup.query.values[index])} ${feature.unit}`;
    entry.insertCell().textContent = number.format(row.values[index]);
    const delta = neighbour.squared_deltas[index];
    const contribution = entry.insertCell();
    contribution.textContent = neighbour.distance_squared
      ? `${(100 * delta / neighbour.distance_squared).toFixed(1)}%` : "—";
    contribution.title = `Squared coordinate difference ${delta.toPrecision(8)}`;
  });
  detail.replaceChildren(
    element("h3", `Distance to ${row.koi_id}`),
    element("p", `d = ${neighbour.distance.toPrecision(12)} · d² = ${neighbour.distance_squared.toPrecision(12)} · Host ${row.host_id}`),
    table,
    element("p", "Distances compare catalogue measurements. Planet confirmation requires independent evidence.", "footnote"),
  );
}

function drawExample() {
  visibleLookup = undefined;
  syncStudyButtons();
  stabilityPanel.hidden = true;
  detailSection.open = true;
  const fixture = catalogue.teaching_example;
  const colours: Record<string, string> = { A: "#47d5bf", B: "#ffc265", C: "#b4a4ff" };
  const points = Object.entries(fixture.examples).map(([id, row]) => ({
    id,
    position: [row.vector[0], row.vector[1], row.vector[2]] as Position,
    colour: colours[id],
  }));
  points.push({ id: "Query", position: [0, 0, 0], colour: "#f4f5f8" });
  scene?.show(points, true);
  drawLegend(points.map(({ id, colour }) => [id, colour]));
  projection.textContent = "Teaching projection · Coordinates 1–3";
  projection.removeAttribute("title");
  summary.textContent = "Synthetic query at the origin";
  uncertainty.hidden = true;
  ranks.replaceChildren(...fixture.full_order.map((id) => {
    const row = fixture.examples[id];
    return element("li", `${id} · 8D ${row.full_distance.toFixed(5)} · 3D ${row.display_distance.toFixed(5)}`, "teaching-rank");
  }));
  detail.replaceChildren(
    element("h3", "Two different rankings"),
    element("p", `Full 8D order: ${fixture.full_order.join(" → ")}`),
    element("p", `Displayed 3D order: ${fixture.display_order.join(" → ")}`),
    element("p", "B appears nearest because coordinate 4 is outside this view. That hidden coordinate contributes 4 of B’s 4.04 squared distance."),
  );
}

function setExample(value: boolean) {
  example = value;
  clearStudy();
  projectedLines.textContent = "Lines connect projected positions of neighbours ranked in 8D.";
  focusButton.hidden = projectedLines.hidden = value || !scene || !lookup;
  exampleButton.setAttribute("aria-pressed", String(value));
  exampleButton.textContent = value ? "Back to Kepler signals" : "3D ranking example";
  plotTitle.textContent = value ? "Where the projection loses detail" : "Kepler signals";
  byId("results-title").textContent = value ? "Full and projected distances" : "Nearest neighbours";
  if (scene) byId("controls").textContent = value
    ? "Drag to orbit"
    : "Drag to orbit · Click a candidate";
  if (value) {
    drawExample();
  } else {
    drawCatalogue();
    if (lookup) drawLookup(lookup);
  }
}

async function runLookup(id: string, openRelease = false, prefetched?: Promise<Lookup>) {
  const request = ++latestRequest;
  error.hidden = true;
  submit.dataset.loading = "";
  submit.setAttribute("aria-busy", "true");
  try {
    const result = await (prefetched ?? getNeighbours(id));
    if (request !== latestRequest) return;
    const reopenStudy = Boolean(study || pendingStudy);
    const reopenRelease = openRelease || Boolean(releaseReport || pendingRelease);
    lookup = result;
    active = 0;
    query.value = result.query.koi_id;
    if (example || reopenStudy || reopenRelease) setExample(false);
    else {
      if (!auditRequest) plotStatus.hidden = true;
      releaseFallback.hidden = true;
      stabilityButton.disabled = false;
      releaseButton.disabled = false;
      auditButton.disabled = Boolean(auditRequest);
      drawLookup(result);
    }
    if (reopenRelease) await runRelease();
    else if (reopenStudy) await runStability();
  } catch (problem) {
    if (request !== latestRequest) return;
    error.textContent = String(problem);
    error.hidden = false;
  } finally {
    if (request === latestRequest) {
      delete submit.dataset.loading;
      submit.removeAttribute("aria-busy");
    }
  }
}

function syncStudyButtons() {
  openStudyButton.disabled = fileBusy || !catalogue;
  saveStudyButton.disabled = fileBusy || !visibleLookup;
}

function studyMessage(message: string, failed = false) {
  studyFileStatus.textContent = message;
  studyFileStatus.toggleAttribute("data-error", failed);
}

async function saveCurrentStudy() {
  if (!lookup || !visibleLookup || fileBusy) return;
  const view: StudyView = releaseReport ? { kind: "release", release: showingEarlier ? "DR24" : "Cumulative" }
    : study ? { kind: "uncertainty", scenario } : auditData ? { kind: "projection", filter: auditFilter }
    : { kind: "catalogue" };
  const selection = {
    candidate: lookup.query.koi_id,
    neighbour: visibleLookup.neighbours[active].observation.koi_id,
    view,
    camera: scene?.captureView() ?? null,
  };
  const file = makeStudy(selection, catalogue, lookup, visibleLookup, study, releaseReport,
    auditData?.byId.get(selection.candidate));
  fileBusy = true;
  syncStudyButtons();
  studyMessage("");
  try {
    const name = await saveStudyFile(file);
    if (name) studyMessage(`Saved ${name}`);
  } catch (problem) {
    studyMessage(problem instanceof Error ? problem.message : String(problem), true);
  } finally {
    fileBusy = false;
    syncStudyButtons();
  }
}

async function restoreStudy() {
  if (!catalogue || fileBusy) return;
  fileBusy = true;
  syncStudyButtons();
  studyMessage("");
  const request = latestRequest;
  try {
    const document = await openStudyFile();
    if (document === null) return;
    const file = parseStudy(document);
    if (file.catalogue.sha256 !== catalogue.snapshot.sha256) {
      throw new Error("This study was saved with a different Kepler catalogue snapshot.");
    }
    const { candidate, view, camera } = file.selection;
    const nominal = await getNeighbours(candidate);
    let visible = nominal;
    let uncertaintyReport: Stability | undefined;
    let comparison: ReleaseComparison | undefined;
    let projection: AuditData | undefined;
    if (view.kind === "uncertainty") {
      uncertaintyReport = await getStability(candidate);
      if (view.scenario > uncertaintyReport.scenarios.length) {
        throw new Error("The saved measurement scenario is unavailable.");
      }
      const trial = uncertaintyReport.scenarios[view.scenario - 1];
      if (trial) {
        visible = variationLookup(nominal, { ...nominal.query, position: trial.position, values: trial.values }, trial.neighbours);
      }
    } else if (view.kind === "release") {
      comparison = await getReleaseComparison(candidate);
      if (view.release === "DR24") visible = variationLookup(nominal, comparison.earlier_query, comparison.earlier_neighbours);
    } else if (view.kind === "projection") {
      projection = await loadAudit();
      if (!projection.byId.has(candidate)) throw new Error("This candidate has no projection audit.");
    }
    const rank = checkStudy(file, catalogue, nominal, visible, uncertaintyReport, comparison,
      projection?.byId.get(candidate));
    if (request !== latestRequest) {
      throw new Error("The active search changed. Open the study again to restore it.");
    }

    latestRequest++;
    delete submit.dataset.loading;
    submit.removeAttribute("aria-busy");
    error.hidden = true;
    lookup = nominal;
    query.value = candidate;
    active = 0;
    setExample(false);
    if (view.kind === "uncertainty") await runStability(uncertaintyReport, view.scenario);
    else if (view.kind === "release") await runRelease(comparison, view.release === "DR24");
    else if (view.kind === "projection" && projection) showAudit(projection, view.filter);
    if (rank !== active) {
      active = rank;
      drawLookup(visible);
    }
    if (camera && scene) {
      setFocus(camera.focused);
      scene.restoreView(camera);
    }
    studyMessage(`Opened study for ${candidate}`);
  } catch (problem) {
    studyMessage(problem instanceof Error ? problem.message : String(problem), true);
  } finally {
    fileBusy = false;
    syncStudyButtons();
  }
}

async function start(opening: ReturnType<typeof showOpening>) {
  const plotModule = import("./scene").catch(() => null);
  try {
    catalogue = await getCatalogue();
  } catch (problem) {
    byId("archive").textContent = "Catalogue unavailable";
    error.textContent = String(problem);
    error.hidden = false;
    return;
  }
  const demoRelease = import.meta.env.DEV && import.meta.env.VITE_TRANSIT_ATLAS_SHOW_RELEASE === "1";
  const initialQuery = demoRelease ? comparisonExample : catalogue.default_query;
  opening.update("Prefetching neighbours for the first signal…", 46);
  const firstLookup = getNeighbours(initialQuery);
  void firstLookup.catch(() => {});
  byId("archive").textContent = `NASA Exoplanet Archive · ${catalogue.snapshot.retrieved_utc_date}`;
  const candidates = catalogue.observations.filter((row) => row.disposition === "CANDIDATE");
  byId("candidates").replaceChildren(...candidates.map((row) => {
    const option = document.createElement("option");
    option.value = row.koi_id;
    return option;
  }));
  opening.update("Preparing the 3D plot and inspector…", 76);
  try {
    const plotRenderer = await plotModule;
    if (!plotRenderer) throw new Error("Plot module unavailable");
    const { SignalScene } = plotRenderer;
    scene = new SignalScene(byId("plot"), byId("axes"), byId("point-markers"), (id) => {
      if (releaseReport) selectRelease(id === "DR24");
      else if (study) selectScenario(Number(id));
      else void runLookup(id);
    });
  } catch {
    byId("plot").append(element("p", "WebGL is unavailable. The search and distance tables remain available.", "plot-error"));
    byId("controls").textContent = "";
  }
  drawCatalogue();
  syncStudyButtons();
  query.disabled = submit.disabled = exampleButton.disabled = false;
  reset.disabled = !scene;
  expandButton.disabled = !scene;
  byId("zoom-hint").hidden = !scene;
  query.value = initialQuery;
  await runLookup(initialQuery, demoRelease, firstLookup);
  if (!demoRelease && import.meta.env.DEV && import.meta.env.VITE_TRANSIT_ATLAS_SHOW_STABILITY === "1") {
    await runStability();
  }
}

search.addEventListener("submit", (event) => {
  event.preventDefault();
  void runLookup(query.value);
});
saveStudyButton.addEventListener("click", () => void saveCurrentStudy());
openStudyButton.addEventListener("click", () => void restoreStudy());
exampleButton.addEventListener("click", () => setExample(!example));
focusButton.addEventListener("click", () => setFocus(!focused));
stabilityButton.addEventListener("click", () => {
  if (study) setExample(false);
  else void runStability();
});
releaseButton.addEventListener("click", () => {
  if (releaseReport) setExample(false);
  else void runRelease();
});
auditButton.addEventListener("click", () => {
  if (auditData) setExample(false);
  else void runAudit();
});
auditFilterControl.addEventListener("change", () => {
  const filter = readAuditFilter(auditFilterControl.value);
  if (auditData && filter) showAudit(auditData, filter);
});
byId("audit-example").addEventListener("click", async () => {
  const current = auditData;
  const target = current?.strongestMismatch;
  if (!current || !target) return;
  showAudit(current, "none");
  await runLookup(target.koi_id);
  if (auditData === current && lookup?.query.koi_id === target.koi_id) {
    setFocus(true);
    revealInspector(auditInspector, true);
  }
});
releaseEarlier.addEventListener("click", () => selectRelease(true));
releaseCurrent.addEventListener("click", () => selectRelease(false));
byId("release-example").addEventListener("click", () => void runLookup(comparisonExample, true));
scenarioSlider.addEventListener("input", () => selectScenario(Number(scenarioSlider.value)));
byId("nominal-scenario").addEventListener("click", () => selectScenario(0));

function expandPlot(expanded: boolean) {
  if (!expanded) {
    plotModal.close();
    restorePlot();
    return;
  }
  plotModal.append(plotPanel);
  plotPanel.classList.add("plot-expanded");
  expandButton.setAttribute("aria-pressed", "true");
  expandButton.textContent = "Exit expanded view";
  plotModal.showModal();
  expandButton.focus();
  arrive([plotPanel], 5);
}

function restorePlot() {
  if (!plotPanel.classList.contains("plot-expanded")) return;
  plotHome.before(plotPanel);
  plotPanel.classList.remove("plot-expanded");
  expandButton.setAttribute("aria-pressed", "false");
  expandButton.textContent = "Expand 3D";
  requestAnimationFrame(() => {
    if (!plotModal.open) expandButton.focus({ preventScroll: true });
  });
}

expandButton.addEventListener("click", () => expandPlot(!plotModal.open));
plotModal.addEventListener("close", restorePlot);
plotModal.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    event.preventDefault();
    expandPlot(false);
  }
});
for (const section of document.querySelectorAll<HTMLDetailsElement>(".inspector-section")) {
  section.addEventListener("toggle", () => {
    if (section.open) arrive(section.querySelectorAll(":scope > .inspector-body"), 6);
  });
}
jumpRanking.addEventListener("click", () => revealInspector(rankingSection, true));
jumpDistance.addEventListener("click", () => revealInspector(detailSection, true));
reset.addEventListener("click", () => scene?.reset());
const opening = showOpening();
void start(opening).catch((problem: unknown) => {
  error.textContent = String(problem);
  error.hidden = false;
}).finally(() => opening.reveal());

import type { Catalogue, Observation, ReleaseComparison } from "./model";

const values = new Intl.NumberFormat("en-GB", { maximumSignificantDigits: 10 });

export function releaseMeasurements(
  report: ReleaseComparison,
  current: Observation,
  features: Catalogue["features"],
): HTMLTableElement {
  const table = document.createElement("table");
  table.setAttribute("aria-label", "Measurement changes from DR24 to the cumulative catalogue");
  const headings = table.createTHead().insertRow();
  for (const label of ["Measurement", "DR24", "Cumulative", "Scaled Δ"]) {
    const cell = document.createElement("th");
    cell.textContent = label;
    cell.scope = "col";
    headings.append(cell);
  }
  const body = table.createTBody();
  const ordered = features.map((feature, index) => ({ feature, index }))
    .sort((a, b) => Math.abs(report.standardised_deltas[b.index]) - Math.abs(report.standardised_deltas[a.index]));
  for (const { feature, index } of ordered) {
    const row = body.insertRow();
    const label = document.createElement("th");
    label.scope = "row";
    label.textContent = feature.name;
    label.title = feature.unit;
    row.append(label);
    row.insertCell().textContent = values.format(report.earlier_query.values[index]);
    row.insertCell().textContent = values.format(current.values[index]);
    const delta = report.standardised_deltas[index];
    row.insertCell().textContent = delta ? `${delta > 0 ? "+" : "−"}${Math.abs(delta).toFixed(3)}` : "0.000";
  }
  return table;
}

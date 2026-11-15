import type { ExactSensitivity } from "./model";

const number = new Intl.NumberFormat("en-GB", { maximumSignificantDigits: 10 });

export function exactDescription(report: ExactSensitivity): string {
  if (report.witness) {
    return `Nearest changes from ${report.nominal_nearest} to ${report.witness.neighbours[0].observation.koi_id}`;
  }
  if (report.status === "near_tie") return `Near a distance tie with ${report.challenger}`;
  return `${report.nominal_nearest} stays nearest throughout the ranges`;
}

export function exactMeasurements(report: ExactSensitivity) {
  const table = document.createElement("table");
  table.setAttribute("aria-label", "Quoted ranges and witness measurements");
  const header = table.createTHead().insertRow();
  const headers = report.witness ? ["Measurement", "Quoted range", "Witness"] : ["Measurement", "Quoted range"];
  for (const label of headers) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    header.append(cell);
  }
  const body = table.createTBody();
  report.measurements.forEach((measurement, i) => {
    const row = body.insertRow();
    const name = document.createElement("th");
    name.scope = "row";
    name.textContent = measurement.name;
    const unit = document.createElement("small");
    unit.textContent = measurement.unit;
    name.append(unit);
    row.append(name);
    row.insertCell().textContent = measurement.bounds
      ? measurement.bounds.map(value => number.format(value)).join(" to ")
      : `${number.format(measurement.original)} fixed`;
    if (report.witness) row.insertCell().textContent = number.format(report.witness.query.values[i]);
  });
  return table;
}

import type { CandidateAudit } from "./model";

export const auditGroups = {
  none: { label: "0 shared", colour: "#ff9b79" },
  low: { label: "1–2 shared", colour: "#d1a0ff" },
  high: { label: "3–5 shared", colour: "#52dfce" },
} as const;

export type AuditFilter = "all" | keyof typeof auditGroups;

export function readAuditFilter(value: unknown): AuditFilter | undefined {
  return value === "all" || value === "none" || value === "low" || value === "high" ? value : undefined;
}

export function auditGroup(shared: number): keyof typeof auditGroups {
  return shared === 0 ? "none" : shared <= 2 ? "low" : "high";
}

export function auditTable(audit: CandidateAudit) {
  const table = document.createElement("table");
  table.setAttribute("aria-label", "Five closest references in the PCA projection");
  const header = table.createTHead().insertRow();
  for (const label of ["3D rank / KOI", "8D rank", "3D d", "8D d", "Omitted"]) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = label;
    header.append(cell);
  }
  const number = new Intl.NumberFormat("en-GB");
  const body = table.createTBody();
  audit.projected_neighbours.forEach((neighbour, index) => {
    const row = body.insertRow();
    const name = document.createElement("th");
    name.scope = "row";
    name.textContent = `P${index + 1}  ${neighbour.koi_id}`;
    row.append(name);
    row.insertCell().textContent = number.format(neighbour.full_rank);
    row.insertCell().textContent = neighbour.projected_distance.toFixed(3);
    row.insertCell().textContent = neighbour.full_distance.toFixed(3);
    row.insertCell().textContent = neighbour.omitted_share === null
      ? "—" : `${(100 * neighbour.omitted_share).toFixed(1)}%`;
  });
  return table;
}

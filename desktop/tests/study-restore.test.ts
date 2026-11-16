import { describe, expect, test } from "bun:test";
import { commitVerifiedRestore } from "../src/study-restore";

describe("verified study restore commit boundary", () => {
  test("does not mutate the active investigation when replay verification fails", () => {
    const active = { candidate: "K00005.01", neighbour: "K01090.01", revision: 7 };
    const before = structuredClone(active);
    const commit = (verified: typeof active) => Object.assign(active, verified);

    expect(() => commitVerifiedRestore(
      () => { throw new Error("processing fingerprints differ"); },
      commit,
    )).toThrow("processing fingerprints differ");
    expect(active).toEqual(before);
  });

  test("does not mutate the active investigation when the original search changes", () => {
    const active = { candidate: "K00005.01", neighbour: "K01090.01", revision: 7 };
    const before = structuredClone(active);

    expect(() => commitVerifiedRestore(
      () => { throw new Error("The active search changed."); },
      (verified) => Object.assign(active, verified),
    )).toThrow("The active search changed.");
    expect(active).toEqual(before);
  });

  test("commits the prepared investigation only after verification succeeds", () => {
    const active = { candidate: "K00005.01", neighbour: "K01090.01", revision: 7 };
    const prepared = { candidate: "K00115.03", neighbour: "K02961.01", revision: 8 };
    const events: string[] = [];

    const result = commitVerifiedRestore(
      () => { events.push("verified"); return prepared; },
      (verified) => { events.push("committed"); Object.assign(active, verified); },
    );

    expect(events).toEqual(["verified", "committed"]);
    expect(result).toEqual(prepared);
    expect(active).toEqual(prepared);
  });
});

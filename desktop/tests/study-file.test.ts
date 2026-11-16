import { readFileSync } from "node:fs";
import { describe, expect, test } from "bun:test";
import { checkStudy, makeStudy, parseStudy, studyLightCurve } from "../src/study-file";

const legacyDocument = JSON.parse(
  readFileSync(new URL("../../data/studies/K00005.01.atlas.json", import.meta.url), "utf8"),
);

function lightCurveProvenance() {
  return {
    identity: {
      koi_id: "K00005.01",
      host_id: 8554498,
      signal_role: "candidate",
    },
    product: {
      archive: "MAST",
      mission: "Kepler",
      data_uri: "s3://stpubdata/kepler/product.fits",
      product_filename: "product.fits",
      source_sha256: "b".repeat(64),
      source_bytes: 469440,
      author: "Kepler",
      quarter: 4,
      data_release: 25,
      cadence: "long",
      time_format: "bkjd",
      time_scale: "tdb",
      time_unit: "d",
      flux_unit: "electron / s",
    },
    ephemeris: {
      period_days: 4.780327581,
      epoch_bkjd: 132.5,
      duration_hours: 2.0253,
      epoch_definition: "BKJD = BJD - 2454833.0",
    },
    processing_fingerprint: "a".repeat(64),
  };
}

function versionTwoDocument() {
  const document = structuredClone(legacyDocument);
  document.version = 2;
  document.selection.view = { kind: "catalogue" };
  delete document.evidence.projection_audit;
  document.evidence.context_points = [];
  document.provenance.light_curves = [lightCurveProvenance()];
  return document;
}

function bundledLightCurveDocument() {
  return {
    schema: "transit-atlas.kepler-lightcurve",
    version: 1,
    processing_fingerprint: "a".repeat(64),
    identity: { koi_id: "K00005.01", host_id: 8554498, signal_role: "candidate" },
    ephemeris: {
      period_days: 4.780327581,
      epoch_bkjd: 132.5,
      duration_hours: 2.0253,
      epoch_definition: "BKJD = BJD - 2454833.0",
    },
    source: {
      archive: "MAST",
      mission: "Kepler",
      data_uri: "s3://stpubdata/kepler/product.fits",
      product_filename: "product.fits",
      sha256: "b".repeat(64),
      bytes: 469440,
      author: "Kepler",
      quarter: 4,
      data_release: 25,
      cadence: "long",
      time_format: "bkjd",
      time_scale: "tdb",
      time_unit: "d",
      flux_unit: "electron / s",
    },
  };
}

describe("portable study provenance", () => {
  test("keeps version 1 studies readable without claiming light-curve verification", () => {
    const parsed = parseStudy(JSON.stringify(legacyDocument));
    expect(parsed.lightCurves).toBeNull();
    expect(parsed.selection.candidate).toBe("K00005.01");
  });

  test("parses version 2 product identity and processing fingerprint", () => {
    const parsed = parseStudy(JSON.stringify(versionTwoDocument()));
    expect(parsed.lightCurves).toHaveLength(1);
    expect(parsed.lightCurves?.[0]).toEqual(lightCurveProvenance());
  });

  test("writes version 2 provenance from the selected light-curve document", () => {
    const legacy = parseStudy(JSON.stringify(legacyDocument));
    const catalogue = {
      snapshot: legacy.catalogue,
      features: legacy.evidence.feature_metadata,
      variance_ratios: legacy.evidence.variance_ratios,
    };
    const lookup = {
      query: legacy.evidence.query,
      neighbours: legacy.evidence.neighbours,
    };
    const study = makeStudy(
      {
        candidate: "K00005.01",
        neighbour: "K01090.01",
        view: { kind: "catalogue" },
        camera: null,
      },
      catalogue as never,
      lookup as never,
      lookup as never,
      undefined,
      undefined,
      undefined,
      undefined,
      [bundledLightCurveDocument() as never],
    );
    const parsed = parseStudy(JSON.stringify(study));
    expect(study.version).toBe(2);
    expect(parsed.lightCurves?.[0].identity.koi_id).toBe("K00005.01");
    expect(parsed.lightCurves?.[0].product.source_sha256).toBe("b".repeat(64));
  });

  test("rejects malformed fingerprints and products unrelated to the selection", () => {
    const malformed = versionTwoDocument();
    malformed.provenance.light_curves[0].processing_fingerprint = "not-a-digest";
    expect(() => parseStudy(JSON.stringify(malformed))).toThrow(
      "invalid Kepler light-curve provenance",
    );

    const unrelated = versionTwoDocument();
    unrelated.provenance.light_curves[0].identity.koi_id = "K00006.01";
    expect(() => parseStudy(JSON.stringify(unrelated))).toThrow(
      "does not match the study selection",
    );

    const missingProduct = versionTwoDocument();
    missingProduct.selection.candidate = "K00115.03";
    missingProduct.provenance.light_curves = [];
    expect(() => parseStudy(JSON.stringify(missingProduct))).toThrow(
      "missing the selected candidate light-curve product",
    );
  });

  test("rejects a replay when the processing fingerprint changes", () => {
    const parsed = parseStudy(JSON.stringify(versionTwoDocument()));
    const catalogue = {
      snapshot: parsed.catalogue,
      features: parsed.evidence.feature_metadata,
      variance_ratios: parsed.evidence.variance_ratios,
    };
    const lookup = {
      query: parsed.evidence.query,
      neighbours: parsed.evidence.neighbours,
    };

    expect(() => checkStudy(
      parsed,
      catalogue as never,
      lookup as never,
      lookup as never,
      undefined,
      undefined,
      undefined,
      undefined,
      [lightCurveProvenance()],
    )).not.toThrow();

    expect(() => checkStudy(
      parsed,
      catalogue as never,
      lookup as never,
      lookup as never,
      undefined,
      undefined,
      undefined,
      undefined,
      [{ ...lightCurveProvenance(), processing_fingerprint: "c".repeat(64) }],
    )).toThrow("processing fingerprints differ");
  });
});



describe("bundled Kepler study replay evidence", () => {
  const candidate = JSON.parse(readFileSync(
    new URL("../../data/generated/lightcurves/K00115.03-q04.json", import.meta.url), "utf8",
  ));
  const reference = JSON.parse(readFileSync(
    new URL("../../data/generated/lightcurves/K02961.01-q04.json", import.meta.url), "utf8",
  ));

  function withFingerprint(document: Record<string, any>) {
    return { ...document, processing_fingerprint: "a".repeat(64) };
  }

  test("loads the real candidate and reference products and preserves source provenance", () => {
    const candidateEvidence = studyLightCurve(withFingerprint(candidate) as never);
    const referenceEvidence = studyLightCurve(withFingerprint(reference) as never);

    expect(candidateEvidence.identity).toEqual({
      koi_id: "K00115.03", host_id: 9579641, signal_role: "candidate",
    });
    expect(referenceEvidence.identity).toEqual({
      koi_id: "K02961.01", host_id: 10471515, signal_role: "reference",
    });
    expect(candidateEvidence.product.source_sha256).toBe(
      "ec65ca837736b99719c92ac064c5f1618f0715ac9258921bc18330b9e783fe3a",
    );
    expect(referenceEvidence.product.source_sha256).toBe(
      "a0bf92fa73c90f42e3927e315410fe72dc85a701d26e15a183685a494e9587e5",
    );
    expect(candidate.folded.cadences_total).toBe(4159);
    expect(candidate.folded.cadences_used).toBe(4108);
    expect(reference.folded.cadences_total).toBe(4159);
    expect(reference.folded.cadences_used).toBe(4108);
  });

  test("requires both products for the selected candidate/reference investigation", () => {
    const document = structuredClone(versionTwoDocument());
    document.selection.candidate = "K00115.03";
    document.selection.neighbour = "K02961.01";
    document.provenance.light_curves = [
      studyLightCurve(withFingerprint(candidate) as never),
    ];
    expect(() => parseStudy(JSON.stringify(document))).toThrow(
      "missing the selected reference light-curve product",
    );
  });
});

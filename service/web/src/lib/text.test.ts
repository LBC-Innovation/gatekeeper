import { describe, expect, it } from "vitest";
import { defaultSentence, defaultUpdate, humanize, recommendedVerb, splitClaimRefs, splitIdCodes, strengthWord } from "./text";

describe("humanize", () => {
  it("turns engine labels and field names into words", () => {
    expect(humanize("Recommended was REVIEW_OBJECTION.")).toBe("Recommended was serious objection.");
    expect(humanize("the why_now is stale")).toBe("the why now is stale");
    expect(humanize("need_evidence")).toBe("find out first");
  });
  it("leaves ordinary prose alone", () => {
    expect(humanize("Massachusetts moved it to a Senate bill.")).toBe("Massachusetts moved it to a Senate bill.");
  });
});

describe("splitClaimRefs", () => {
  it("finds single, listed and ranged claim references", () => {
    const parts = splitClaimRefs("Claim 136 shows it; claims 79/80 agree and claim ids 112, 114 and 141 too");
    expect(parts.filter((p) => p.ids).map((p) => p.ids)).toEqual([[136], [79, 80], [112, 114, 141]]);
  });
  it("returns plain text untouched", () => {
    expect(splitClaimRefs("nothing to see")).toEqual([{ text: "nothing to see" }]);
  });
});

describe("decisions", () => {
  it("maps the panel's advice to the verb that is filled in", () => {
    expect(recommendedVerb("CONSIDER")).toBe("promote");
    expect(recommendedVerb("REVIEW_OBJECTION")).toBe("need_evidence");
    expect(recommendedVerb(null)).toBeNull();
  });
  it("says what the default does, in a sentence", () => {
    expect(defaultSentence({ default_action: "park", default_on: "2026-11-01" })).toMatch(/^Updates to Parked on .* unless you decide\.$/);
    expect(defaultUpdate({ default_action: "need_evidence", default_on: "2026-11-04" })).toMatch(/^updated to Find out first on /);
    expect(defaultSentence(null)).toMatch(/waits for you/);
  });
  it("places a strength against the lines", () => {
    expect(strengthWord(52, 65, 45)).toBe("between the park line and the fund line");
    expect(strengthWord(70, 65, 45)).toBe("above the fund line");
  });
});

describe("splitIdCodes", () => {
  it("finds every kind of code and leaves the prose between them alone", () => {
    const parts = splitIdCodes("Held at 0.6 against SD-03, see PF-0006 and IDEA-2026-0031 (CAP-07).");
    expect(parts.filter((p) => p.code).map((p) => p.code)).toEqual(["SD-03", "PF-0006", "IDEA-2026-0031", "CAP-07"]);
    expect(parts.map((p) => p.text).join("")).toBe("Held at 0.6 against SD-03, see PF-0006 and IDEA-2026-0031 (CAP-07).");
  });
  it("does not link lookalikes", () => {
    expect(splitIdCodes("USD-03 and SD-3 and PF-12").some((p) => p.code)).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { splitFrontmatter } from "./markdown";

describe("splitFrontmatter", () => {
  it("separates the header fields from the body", () => {
    const { meta, body } = splitFrontmatter("---\nname: gatekeeper-scout\nmodel: sonnet\n---\n# Scout\n\nBody.");
    expect(meta).toEqual({ name: "gatekeeper-scout", model: "sonnet" });
    expect(body.startsWith("# Scout")).toBe(true);
  });
  it("leaves a file with no header alone", () => {
    expect(splitFrontmatter("# Just text")).toEqual({ meta: {}, body: "# Just text" });
  });
});

import { describe, expect, it } from "vitest";
import { getRoot } from "./root";

function fakeDoc(el: HTMLElement | null): Document {
  return { getElementById: () => el } as unknown as Document;
}

describe("getRoot", () => {
  it("returns the #root element", () => {
    const el = {} as HTMLElement;
    expect(getRoot(fakeDoc(el))).toBe(el);
  });

  it("fails loudly when #root is missing", () => {
    expect(() => getRoot(fakeDoc(null))).toThrow("#root is missing");
  });
});

import { describe, expect, it } from "vitest";
import { formatDateTime, formatDistance, formatDuration, formatPace, titleCase } from "./format";

describe("format helpers", () => {
  it("formats distance in km", () => {
    expect(formatDistance(5000)).toBe("5.00 km");
    expect(formatDistance(12345)).toBe("12.3 km");
    expect(formatDistance(null)).toBe("—");
  });

  it("formats duration", () => {
    expect(formatDuration(90)).toBe("1:30");
    expect(formatDuration(3661)).toBe("1:01:01");
    expect(formatDuration(0)).toBe("—");
  });

  it("formats pace per km", () => {
    expect(formatPace(300)).toBe("5:00 /km");
    expect(formatPace(330)).toBe("5:30 /km");
  });

  it("formats date and time in the requested timezone", () => {
    expect(formatDateTime("2026-08-18T12:30:00Z", "Asia/Jerusalem")).toBe(
      "Aug 18, 2026, 03:30 PM",
    );
  });

  it("title-cases snake_case", () => {
    expect(titleCase("weekly_update")).toBe("Weekly Update");
    expect(titleCase(null)).toBe("");
  });
});

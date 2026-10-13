import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

declare const jsdom: { window: { localStorage: Storage } };
// Node 26 also defines localStorage. Use the actual jsdom browser storage for
// workspace tests, without modifying or mocking production storage behavior.
Object.defineProperty(globalThis, "localStorage", {
  configurable: true,
  value: jsdom.window.localStorage,
});

afterEach(cleanup);

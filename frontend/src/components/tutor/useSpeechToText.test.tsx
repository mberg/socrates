import { renderHook } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useSpeechToText } from "./useSpeechToText";

afterEach(() => { vi.unstubAllGlobals(); });

test("reports unsupported when no SpeechRecognition global exists", () => {
  vi.stubGlobal("SpeechRecognition", undefined);
  vi.stubGlobal("webkitSpeechRecognition", undefined);
  const { result } = renderHook(() => useSpeechToText());
  expect(result.current.supported).toBe(false);
});

test("reports supported when the API exists", () => {
  class FakeRec { start() {} stop() {} onresult = null; onend = null; continuous = false; interimResults = false; }
  vi.stubGlobal("SpeechRecognition", FakeRec);
  const { result } = renderHook(() => useSpeechToText());
  expect(result.current.supported).toBe(true);
});

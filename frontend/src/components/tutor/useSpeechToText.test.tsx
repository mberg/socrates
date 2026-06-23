import { act, renderHook } from "@testing-library/react";
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

test("reports unsupported in an insecure context even if the API exists", () => {
  class FakeRec { start() {} stop() {} onresult = null; onend = null; continuous = false; interimResults = false; }
  vi.stubGlobal("SpeechRecognition", FakeRec);
  vi.stubGlobal("isSecureContext", false);
  const { result } = renderHook(() => useSpeechToText());
  expect(result.current.supported).toBe(false);
});

test("start() surfaces an error (not a silent failure) when start throws", () => {
  class ThrowingRec {
    onresult = null; onend = null; onerror = null; continuous = false; interimResults = false; lang = "";
    start() { throw new Error("not-allowed"); }
    stop() {}
  }
  vi.stubGlobal("SpeechRecognition", ThrowingRec);
  const { result } = renderHook(() => useSpeechToText());
  act(() => { result.current.start(); });
  expect(result.current.error).toBeTruthy();
  expect(result.current.listening).toBe(false);
});

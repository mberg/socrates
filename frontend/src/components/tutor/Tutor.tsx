import { useEffect, useState } from "react";
import { api, type GuidanceSession } from "../../api";
import { Button } from "../ui/Button";
import Prose from "./Prose";
import VisualRenderer from "../visuals/VisualRenderer";
import { useSpeechToText } from "./useSpeechToText";

export default function Tutor(
  { childId, attemptId, problemId, onClose }:
  { childId: string; attemptId: string; problemId: string; onClose: () => void }
) {
  const [session, setSession] = useState<GuidanceSession | null>(null);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const speech = useSpeechToText();

  useEffect(() => {
    let alive = true;
    api.startGuidance(childId, attemptId, problemId)
      .then((s) => { if (alive) setSession(s); })
      .catch((e) => { if (alive) setError(String(e)); });
    return () => { alive = false; };
  }, [childId, attemptId, problemId]);

  useEffect(() => { if (speech.transcript) setDraft(speech.transcript); }, [speech.transcript]);

  const run = async (fn: () => Promise<GuidanceSession>) => {
    setBusy(true); setError(null);
    try { setSession(await fn()); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const send = async () => {
    if (!session || !draft.trim()) return;
    const text = draft.trim();
    const input_source = speech.listening || speech.transcript ? "voice" : "typed";
    setDraft(""); speech.reset();
    await run(() => api.postTurn(session.id, { text, input_source }));
  };
  const showMore = () => session && run(() => api.postTurn(session.id, { advance: true }));
  const resolve = async () => {
    if (!session) return;
    setBusy(true); setError(null);
    try {
      await api.resolveGuidance(session.id);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const tier = session?.max_tier_reached ?? 1;
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 sm:items-center" role="dialog" aria-label="tutor">
      <div className="flex h-[85vh] w-full max-w-lg flex-col rounded-t-2xl bg-white p-4 shadow-xl sm:rounded-2xl">
        <div className="mb-2 flex items-center justify-between">
          <div className="font-bold">Help · #{session?.problem_number ?? ""} <span className="text-slate-400">({session?.problem_prompt})</span></div>
          <button onClick={onClose} aria-label="close" className="text-slate-500">✕</button>
        </div>

        <div className="flex-1 space-y-3 overflow-y-auto">
          {session?.turns.map((t) => (
            <div key={t.id} className={t.role === "child" ? "ml-auto max-w-[80%] rounded-2xl bg-blue-600 px-3 py-2 text-white" : "max-w-[90%] rounded-2xl bg-slate-100 px-3 py-2"}>
              <Prose text={t.text} />
              {t.visuals?.map((v, i) => <div key={i} className="mt-2"><VisualRenderer visual={v} /></div>)}
            </div>
          ))}
          {busy && <div className="text-sm text-slate-400">thinking…</div>}
          {error && <div className="text-sm text-red-600">{error}</div>}
        </div>

        <div className="mt-2 flex flex-wrap gap-2">
          <Button onClick={showMore} disabled={busy || tier >= 3} className="bg-amber-500">
            Still stuck — show me more
          </Button>
          <Button onClick={resolve} disabled={busy} className="bg-green-600">Got it</Button>
        </div>

        <div className="mt-2 flex items-center gap-2">
          <input
            className="flex-1 rounded-xl border border-slate-300 px-3 py-2"
            placeholder="Ask the tutor…" value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") send(); }}
          />
          {speech.supported && (
            <button aria-label="voice input" onClick={() => (speech.listening ? speech.stop() : speech.start())}
                    className={`rounded-xl px-3 py-2 ${speech.listening ? "bg-red-100" : "bg-slate-100"}`}>🎤</button>
          )}
          <Button onClick={send} disabled={busy || !draft.trim()}>Send</Button>
        </div>
      </div>
    </div>
  );
}

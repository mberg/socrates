import { useCallback, useEffect, useRef, useState } from "react";

type Rec = {
  continuous: boolean; interimResults: boolean; lang?: string;
  start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: ((e: { error?: string }) => void) | null;
};

function getCtor(): (new () => Rec) | null {
  const g = globalThis as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return g.SpeechRecognition || g.webkitSpeechRecognition || null;
}

// The Web Speech API only works in a secure context (https or localhost). On an
// insecure origin (e.g. http://host.local:8000) the constructor may exist but
// start() fails, so treat insecure origins as unsupported. undefined (non-browser
// test env) is treated as secure.
function isSecure(): boolean {
  return (globalThis as { isSecureContext?: boolean }).isSecureContext !== false;
}

export function useSpeechToText() {
  const Ctor = getCtor();
  const supported = Ctor !== null && isSecure();
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<Rec | null>(null);

  useEffect(() => () => { recRef.current?.stop(); }, []);

  const start = useCallback(() => {
    if (!Ctor) return;
    if (!isSecure()) {
      setError("Voice input needs a secure (https) connection.");
      return;
    }
    setError(null);
    try {
      const rec = new Ctor();
      rec.continuous = false;
      rec.interimResults = true;
      rec.lang = "en-US";
      rec.onresult = (e) => {
        let text = "";
        for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
        setTranscript(text);
      };
      rec.onerror = (e) => { setError(`Voice input failed (${e?.error ?? "error"}).`); setListening(false); };
      rec.onend = () => setListening(false);
      recRef.current = rec;
      setListening(true);
      rec.start();
    } catch (e) {
      setError(String(e));
      setListening(false);
    }
  }, [Ctor]);

  const stop = useCallback(() => { recRef.current?.stop(); setListening(false); }, []);
  const reset = useCallback(() => setTranscript(""), []);

  return { supported, listening, transcript, error, start, stop, reset };
}

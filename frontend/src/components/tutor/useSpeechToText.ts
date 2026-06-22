import { useCallback, useEffect, useRef, useState } from "react";

type Rec = {
  continuous: boolean; interimResults: boolean; lang?: string;
  start(): void; stop(): void;
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
};

function getCtor(): (new () => Rec) | null {
  const g = globalThis as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec };
  return g.SpeechRecognition || g.webkitSpeechRecognition || null;
}

export function useSpeechToText() {
  const Ctor = getCtor();
  const supported = Ctor !== null;
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recRef = useRef<Rec | null>(null);

  useEffect(() => () => { recRef.current?.stop(); }, []);

  const start = useCallback(() => {
    if (!Ctor) return;
    const rec = new Ctor();
    rec.continuous = false;
    rec.interimResults = true;
    rec.lang = "en-US";
    rec.onresult = (e) => {
      let text = "";
      for (let i = 0; i < e.results.length; i++) text += e.results[i][0].transcript;
      setTranscript(text);
    };
    rec.onend = () => setListening(false);
    recRef.current = rec;
    setListening(true);
    rec.start();
  }, [Ctor]);

  const stop = useCallback(() => { recRef.current?.stop(); setListening(false); }, []);
  const reset = useCallback(() => setTranscript(""), []);

  return { supported, listening, transcript, start, stop, reset };
}

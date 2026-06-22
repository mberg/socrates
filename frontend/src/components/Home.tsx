import { useEffect, useState } from "react";
import { api, type Child } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import PinPad from "./PinPad";
import AddKid from "./AddKid";

export default function Home({ onEnter }: { onEnter: (child: Child) => void }) {
  const [children, setChildren] = useState<Child[]>([]);
  const [pinFor, setPinFor] = useState<Child | null>(null);
  const [pinError, setPinError] = useState<string>();
  const [adding, setAdding] = useState(false);

  const reload = () => api.listChildren().then(setChildren).catch(() => setChildren([]));
  useEffect(() => { reload(); }, []);

  const tap = (c: Child) => { if (c.has_pin) { setPinError(undefined); setPinFor(c); } else onEnter(c); };
  const submitPin = async (pin: string) => {
    if (!pinFor) return;
    const { ok } = await api.verifyPin(pinFor.id, pin);
    if (ok) onEnter(pinFor); else setPinError("Try again");
  };

  if (pinFor) return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-4 text-2xl font-bold">{pinFor.name}'s PIN</h1>
      <PinPad onSubmit={submitPin} error={pinError} />
      <div className="mt-4"><Button variant="ghost" onClick={() => setPinFor(null)}>Back</Button></div>
    </div>
  );

  if (adding) return (
    <div className="mx-auto max-w-md p-6">
      <h1 className="mb-4 text-2xl font-bold">Add a kid</h1>
      <AddKid onAdded={(c) => { setAdding(false); reload(); onEnter(c); }} onCancel={() => setAdding(false)} />
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl p-6">
      <h1 className="mb-6 text-3xl font-bold">Who's working today?</h1>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {children.map((c) => (
          <button key={c.id} onClick={() => tap(c)} className="text-left">
            <Card className="flex h-32 flex-col justify-between hover:border-indigo-400">
              <span className="text-2xl font-bold">{c.name}</span>
              <span className="text-slate-500">Grade {c.grade}{c.has_pin ? " · 🔒" : ""}</span>
            </Card>
          </button>
        ))}
        <button onClick={() => setAdding(true)} className="text-left">
          <Card className="flex h-32 items-center justify-center border-dashed text-xl text-slate-500">+ Add kid</Card>
        </button>
      </div>
    </div>
  );
}

import { useState } from "react";
import { api, type Child } from "../api";
import { Button } from "./ui/Button";

export default function AddKid({ onAdded, onCancel }: { onAdded: (c: Child) => void; onCancel: () => void }) {
  const [name, setName] = useState("");
  const [grade, setGrade] = useState(5);
  const [pin, setPin] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try { onAdded(await api.createChild(name.trim(), grade, pin.trim() || undefined)); }
    finally { setBusy(false); }
  };
  return (
    <div className="flex flex-col gap-3">
      <input className="rounded-xl border p-3 text-lg" placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
      <select className="rounded-xl border p-3 text-lg" value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
        <option value={3}>Grade 3</option>
        <option value={5}>Grade 5</option>
      </select>
      <input className="rounded-xl border p-3 text-lg" placeholder="PIN (optional, 4 digits)" inputMode="numeric"
        maxLength={4} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))} />
      <div className="flex gap-2">
        <Button onClick={submit} disabled={busy || !name.trim()}>Add</Button>
        <Button variant="ghost" onClick={onCancel}>Cancel</Button>
      </div>
    </div>
  );
}

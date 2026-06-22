import { useState } from "react";
import { Button } from "./ui/Button";

export default function PinPad({ onSubmit, error }: { onSubmit: (pin: string) => void; error?: string }) {
  const [pin, setPin] = useState("");
  const press = (d: string) => {
    const next = (pin + d).slice(0, 4);
    setPin(next);
    if (next.length === 4) { onSubmit(next); setPin(""); }
  };
  return (
    <div className="flex flex-col items-center gap-4">
      <div className="text-2xl tracking-[0.4em]">{"•".repeat(pin.length).padEnd(4, "·")}</div>
      {error && <div className="text-red-600">{error}</div>}
      <div className="grid grid-cols-3 gap-3">
        {["1","2","3","4","5","6","7","8","9"].map((d) => (
          <Button key={d} variant="secondary" onClick={() => press(d)}>{d}</Button>
        ))}
        <div />
        <Button variant="secondary" onClick={() => press("0")}>0</Button>
      </div>
    </div>
  );
}

import { useState } from "react";
import type { Child } from "../api";
import { Button } from "./ui/Button";
import Print from "./Print";

type Tab = "print" | "scan" | "scores";

export default function KidSpace({ child, onHome }: { child: Child; onHome: () => void }) {
  const [tab, setTab] = useState<Tab>("print");
  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{child.name}</h1>
        <Button variant="ghost" onClick={onHome}>← Home</Button>
      </div>
      <div className="mb-6 flex gap-2">
        {(["print", "scan", "scores"] as Tab[]).map((t) => (
          <Button key={t} variant={tab === t ? "primary" : "secondary"} className="capitalize" onClick={() => setTab(t)}>
            {t === "scores" ? "My scores" : t}
          </Button>
        ))}
      </div>
      {tab === "print" && <Print child={child} />}
      {tab === "scan" && <div className="text-slate-500">Scan (Task 7)</div>}
      {tab === "scores" && <div className="text-slate-500">My scores (Task 8)</div>}
    </div>
  );
}

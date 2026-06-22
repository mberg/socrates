import { useEffect, useState } from "react";
import { api, type Child, type Skill, type Worksheet } from "../api";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";

export default function Print({ child }: { child: Child }) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [topic, setTopic] = useState<string>();
  const [skill, setSkill] = useState<Skill>();
  const [worksheets, setWorksheets] = useState<Worksheet[]>([]);
  const [worksheet, setWorksheet] = useState<Worksheet>();
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.listSkills(child.grade).then(setSkills).catch(() => setSkills([])); }, [child.grade]);
  useEffect(() => { if (skill) api.listWorksheets(skill.id).then(setWorksheets).catch(() => setWorksheets([])); }, [skill]);

  const topics = [...new Set(skills.map((s) => s.topic))].sort();

  const print = async () => {
    if (!worksheet) return;
    setBusy(true);
    try {
      const attempt = await api.createAttempt(child.id, worksheet.id);
      window.open(api.printUrl(attempt.id), "_blank");
    } finally { setBusy(false); }
  };

  if (worksheet) return (
    <div>
      <Button variant="ghost" onClick={() => setWorksheet(undefined)}>← {skill?.label}</Button>
      <h2 className="my-3 text-xl font-bold">{worksheet.title}</h2>
      <Card className="mb-4">
        <p className="text-slate-600">{worksheet.problem_count} problems{worksheet.variant ? ` · variant ${worksheet.variant}` : ""}</p>
      </Card>
      <Button onClick={print} disabled={busy}>{busy ? "…" : "Print"}</Button>
    </div>
  );

  if (skill) return (
    <div>
      <Button variant="ghost" onClick={() => { setSkill(undefined); setWorksheets([]); }}>← {skill.topic}</Button>
      <h2 className="my-3 text-xl font-bold">{skill.label}</h2>
      <div className="flex flex-col gap-2">
        {worksheets.map((w) => (
          <Button key={w.id} variant="secondary" className="justify-start text-left" onClick={() => setWorksheet(w)}>
            {w.title}{w.variant ? ` (${w.variant})` : ""}
          </Button>
        ))}
      </div>
    </div>
  );

  if (topic) return (
    <div>
      <Button variant="ghost" onClick={() => setTopic(undefined)}>← Topics</Button>
      <h2 className="my-3 text-xl font-bold capitalize">{topic}</h2>
      <div className="flex flex-col gap-2">
        {skills.filter((s) => s.topic === topic).map((s) => (
          <Button key={s.id} variant="secondary" className="justify-start text-left" onClick={() => setSkill(s)}>{s.label}</Button>
        ))}
      </div>
    </div>
  );

  return (
    <div>
      <h2 className="my-3 text-xl font-bold">Pick a topic</h2>
      <div className="grid grid-cols-2 gap-2">
        {topics.map((t) => (
          <Button key={t} variant="secondary" className="capitalize" onClick={() => setTopic(t)}>{t}</Button>
        ))}
      </div>
    </div>
  );
}

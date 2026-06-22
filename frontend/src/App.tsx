import { useState } from "react";
import type { Child } from "./api";
import Home from "./components/Home";

type View = { view: "home" } | { view: "kid"; child: Child };

export default function App() {
  const [state, setState] = useState<View>({ view: "home" });
  if (state.view === "kid")
    return <div className="p-6"><button className="mb-4 underline" onClick={() => setState({ view: "home" })}>← Home</button><div>Kid space for {state.child.name} (Task 6)</div></div>;
  return <Home onEnter={(child) => setState({ view: "kid", child })} />;
}

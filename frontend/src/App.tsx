import { useState } from "react";
import type { Child } from "./api";
import Home from "./components/Home";
import KidSpace from "./components/KidSpace";

type View = { view: "home" } | { view: "kid"; child: Child };

export default function App() {
  const [state, setState] = useState<View>({ view: "home" });
  if (state.view === "kid")
    return <KidSpace child={state.child} onHome={() => setState({ view: "home" })} />;
  return <Home onEnter={(child) => setState({ view: "kid", child })} />;
}

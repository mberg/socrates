import type { Visual } from "./types";
import Math from "./Math";
import Steps from "./Steps";
import NumberLine from "./NumberLine";
import FractionBar from "./FractionBar";
import PlaceValue from "./PlaceValue";
import MultGrid from "./MultGrid";

export default function VisualRenderer({ visual }: { visual: Visual }) {
  switch (visual.type) {
    case "math": return <Math tex={visual.tex} display={visual.display} />;
    case "steps": return <Steps title={visual.title} steps={visual.steps} />;
    case "number_line": return <NumberLine {...visual} />;
    case "fraction_bar": return <FractionBar bars={visual.bars} />;
    case "place_value": return <PlaceValue value={visual.value} columns={visual.columns} />;
    case "mult_grid": return <MultGrid rows={visual.rows} cols={visual.cols} partial={visual.partial} />;
    default: return null;
  }
}

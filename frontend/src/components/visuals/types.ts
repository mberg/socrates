export type Visual =
  | { type: "math"; tex: string; display?: boolean }
  | { type: "steps"; title?: string | null; steps: { text: string; highlight?: boolean }[] }
  | { type: "number_line"; min: number; max: number; ticks?: number | null;
      marks?: { value: number; label?: string | null; color?: string | null }[];
      jumps?: { from: number; to: number; label?: string | null }[] }
  | { type: "fraction_bar"; bars: { denominator: number; shaded: number; label?: string | null }[] }
  | { type: "place_value"; value: number; columns?: string[] | null }
  | { type: "mult_grid"; rows: number; cols: number; partial?: boolean };

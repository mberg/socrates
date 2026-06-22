const PLACES = [["thousands", 1000], ["hundreds", 100], ["tens", 10], ["ones", 1]] as const;
export default function PlaceValue({ value, columns }: { value: number; columns?: string[] | null }) {
  const whole = Math.floor(Math.abs(value));
  const places = (columns && columns.length
    ? PLACES.filter(([n]) => columns.includes(n))
    : PLACES.filter(([, p]) => p <= Math.max(1, whole))) as readonly (readonly [string, number])[];
  return (
    <div className="flex gap-2" role="img" aria-label={`place value of ${value}`}>
      {places.map(([name, p]) => {
        const digit = Math.floor(whole / p) % 10;
        return (
          <div key={name} className="flex flex-col items-center rounded-md border border-slate-200 p-2">
            <div className="text-xl font-bold">{digit}</div>
            <div className="text-[10px] uppercase text-slate-500">{name}</div>
            <div className="mt-1 grid grid-cols-3 gap-[2px]">
              {Array.from({ length: digit }, (_, i) => <span key={i} className="h-2 w-2 rounded-sm bg-blue-500" />)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

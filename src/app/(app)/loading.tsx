// Shown at once while a page reads the database, so a tap always answers straight away.
export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="page-head">
        <div className="skeleton h-8 w-56" />
        <div className="skeleton mt-2 h-4 w-80 max-w-full" />
      </div>
      <div className="stack">
        <div className="card grid gap-3"><div className="skeleton h-5 w-40" /><div className="skeleton h-4" /><div className="skeleton h-4 w-3/4" /></div>
        <div className="grid grid-cols-3 gap-3">{[0, 1, 2].map((i) => <div key={i} className="skeleton h-20 rounded-2xl" />)}</div>
        <div className="card grid gap-3">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-4" />)}</div>
      </div>
    </div>
  );
}

"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/icons";
import { py } from "@/components/py";
import { useAct } from "@/components/useAct";
import { MIDWEEK } from "@/lib/constants";
import { fmtDate } from "@/lib/dates";

export function CreateWeeks({ weeks, auxDefault }: { weeks: { date: string; label: string }[]; auxDefault: boolean }) {
  const router = useRouter();
  const [busy, act] = useAct();
  const [aux, setAux] = useState(auxDefault);
  const [group, setGroup] = useState("");
  return (
    <>
      {weeks.length > 1 ? (
        <div className="grid gap-3 rounded-xl border border-line p-3">
          <div className="text-sm">{weeks.length} weeks this month have no schedule. They can be created and filled in one go, then
            checked week by week. The suggestions follow the same rotation as the Suggest button.</div>
          <label className="check"><input type="checkbox" checked={aux} onChange={(e) => setAux(e.target.checked)} /> Auxiliary classroom in these weeks</label>
          {aux ? <label className="field max-w-xs"><span>Group using the classroom</span>
            <input className="input" placeholder="e.g. 1" value={group} onChange={(e) => setGroup(e.target.value)} /></label> : null}
          <button type="button" className="btn primary w-fit" disabled={busy}
            onClick={() => act(() => py("create_month", { weeks, aux, group }), () => router.refresh())}>
            <Icon name="sparkle" /> Create all {weeks.length} weeks
          </button>
        </div>
      ) : null}
      <div className="btns">
        {weeks.map((w) => (
          <Link key={w.date} className="btn" href={`/schedule?${new URLSearchParams({ date: w.date, type: MIDWEEK })}`}>
            <Icon name="add" /> Create {fmtDate(w.date, true)}
          </Link>
        ))}
      </div>
    </>
  );
}

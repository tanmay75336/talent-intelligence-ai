export function Header() {
  return (
    <header className="rounded-lg border border-slate-200 bg-white px-5 py-5 shadow-sm">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="section-label">Recruiter Workspace</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-950">
            Candidate Review
          </h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">
            Review role fit, inspect supporting evidence, and move candidates through a focused decision workflow.
          </p>
        </div>
        <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Mode</p>
          <p className="mt-1 text-sm font-medium text-slate-800">Evidence-assisted review</p>
        </div>
      </div>
    </header>
  );
}

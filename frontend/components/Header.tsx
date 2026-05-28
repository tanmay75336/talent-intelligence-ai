export function Header() {
  return (
    <header className="card-surface bg-grid animate-fade-up relative overflow-hidden px-6 py-8 sm:px-8 sm:py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(143,181,255,0.14),transparent_28%)]" />
      <div className="relative grid gap-8 lg:grid-cols-[1.4fr_0.9fr] lg:items-end">
        <div className="max-w-3xl">
          <p className="section-label mb-4">Recruitment Intelligence Platform</p>
          <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-slate-50 sm:text-5xl lg:text-6xl">
            TALENT INTELLIGENCE AI
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
            Evaluate resumes against live job requirements with AI-assisted ranking,
            semantic fit analysis, and recruiter-ready candidate summaries.
          </p>
          <div className="mt-8 flex flex-wrap gap-3 text-sm text-slate-300">
            <span className="rounded-full border border-slate-700/70 bg-slate-900/60 px-4 py-2">
              Multi-PDF resume upload
            </span>
            <span className="rounded-full border border-slate-700/70 bg-slate-900/60 px-4 py-2">
              Semantic and keyword scoring
            </span>
            <span className="rounded-full border border-slate-700/70 bg-slate-900/60 px-4 py-2">
              Transferable skill detection
            </span>
          </div>
        </div>

        <div className="card-muted p-5">
          <p className="section-label">Operational View</p>
          <div className="mt-5 space-y-4">
            <div className="flex items-start justify-between gap-4 rounded-2xl border border-slate-700/60 bg-slate-950/40 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-100">Recruiter workflow</p>
                <p className="mt-1 text-sm text-slate-400">
                  Upload resumes, paste the JD, review ranked candidates.
                </p>
              </div>
              <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-200">
                Live
              </span>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/40 p-4">
                <p className="text-sm text-slate-400">Backend</p>
                <p className="mt-2 font-medium text-slate-100">FastAPI</p>
              </div>
              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/40 p-4">
                <p className="text-sm text-slate-400">Ranking</p>
                <p className="mt-2 font-medium text-slate-100">Hybrid AI</p>
              </div>
              <div className="rounded-2xl border border-slate-700/60 bg-slate-950/40 p-4">
                <p className="text-sm text-slate-400">Output</p>
                <p className="mt-2 font-medium text-slate-100">Recruiter brief</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}

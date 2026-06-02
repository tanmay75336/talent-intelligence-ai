import type {
  RankDatasetResponse,
  RankingRunSummary,
  SavedRankingRunResults,
  UploadAndRankResponse,
} from "@/types/recruitment";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function uploadAndRankCandidates(
  files: File[],
  jdText: string,
): Promise<UploadAndRankResponse> {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file);
  });

  formData.append("jd_text", jdText);

  const response = await fetch(`${API_BASE_URL}/upload-and-rank/`, {
    method: "POST",
    body: formData,
  });

  return parseResponse<UploadAndRankResponse>(response);
}

export async function rankDatasetCandidates(
  jdText: string,
): Promise<RankDatasetResponse> {
  // The existing FastAPI route accepts `jd_text` as a simple parameter,
  // so we send it as a query string instead of changing the backend.
  const response = await fetch(
    `${API_BASE_URL}/rank-dataset/?jd_text=${encodeURIComponent(jdText)}`,
    {
      method: "POST",
    },
  );

  return parseResponse<RankDatasetResponse>(response);
}

export async function listRankingRuns(): Promise<RankingRunSummary[]> {
  const response = await fetch(`${API_BASE_URL}/ranking-runs/`);
  const payload = await parseResponse<{ ranking_runs: RankingRunSummary[] }>(response);
  return payload.ranking_runs ?? [];
}

export async function getRankingRunResults(
  runId: string,
): Promise<SavedRankingRunResults> {
  const response = await fetch(`${API_BASE_URL}/ranking-runs/${runId}/results`);
  return parseResponse<SavedRankingRunResults>(response);
}

"""
Phase 8C.3 comparison analysis — run after submission_phase8c3.csv is generated.
Compares Phase 8C.3 vs Phase 8B.3 champion on official evaluation dimensions.
"""
import sys, csv
sys.path.insert(0, '.')
from backend.dataset_intelligence.loader import iter_dataset_records
from backend.competition.redrob_adapter import adapt_redrob_candidate
from backend.competition.evidence_calibrator import calibrate_candidate_evidence
from backend.competition.evaluate import _extract_career_signals, _extract_behavioral_signals
from backend.utils.skill_taxonomy import normalize_whitespace, get_active_groups
from backend.competition.rank import read_job_text, _important_terms, _experience_fit
from backend.parsers.jd_analyzer import analyze_job_description
from backend.intelligence.candidate_engine import build_competition_core_signals
from backend.competition.rerank_experiment import _headroom_depth_bonus

job_text = read_job_text('data/job_description.docx')
job_analysis = analyze_job_description(job_text)
job_terms = _important_terms(job_text)

def load_csv(path):
    with open(path) as f:
        return {row['candidate_id']: {'rank': int(row['rank']), 'score': float(row['score']), 'reasoning': row['reasoning']} for row in csv.DictReader(f)}

p8b3 = load_csv('submission_phase8b3.csv')
p8c3 = load_csv('submission_phase8c3.csv')

p8b3_ids = set(p8b3.keys())
p8c3_ids = set(p8c3.keys())

gained = p8c3_ids - p8b3_ids
lost = p8b3_ids - p8c3_ids
stayed = p8c3_ids & p8b3_ids

print(f'=== PHASE 8C.3 vs PHASE 8B.3 COMPARISON ===')
print(f'  Candidates GAINED (new in 8C.3): {len(gained)}')
print(f'  Candidates LOST  (removed from 8C.3): {len(lost)}')
print(f'  Candidates STAYED in both: {len(stayed)}')
print()

# Analyze gained candidates
gained_data = []
lost_data = []

scanned = 0
gain_ids_found = set()
loss_ids_found = set()

for raw in iter_dataset_records('data/candidates.jsonl'):
    cid = raw.get('candidate_id', '')
    if cid not in gained and cid not in lost:
        scanned += 1
        if scanned > 50000 and (gain_ids_found >= gained or loss_ids_found >= lost):
            break
        continue
    
    p = adapt_redrob_candidate(raw)
    cal = calibrate_candidate_evidence(p)
    career_text = normalize_whitespace(' '.join(str(i.get('description','')) for i in p.career_history)).lower()
    cs = _extract_career_signals(career_text)
    bs = _extract_behavioral_signals(p.redrob_signals or {})
    
    record = {
        'cid': cid,
        'title': p.structured_profile.get('current_title','?'),
        'company': p.structured_profile.get('current_company','?'),
        'years': p.years_of_experience,
        'career_ai': cal.career_ai_infra_hits[:4],
        'depth': cs['evidence_depth'],
        'has_eval': cs['has_eval_maturity'],
        'has_ret': cs['has_retrieval'],
        'trap': cal.trap_flags,
        'adj': cal.adjustment,
        'snippet': career_text[:200],
    }
    
    if cid in gained:
        record['new_rank'] = p8c3[cid]['rank']
        gained_data.append(record)
        gain_ids_found.add(cid)
    elif cid in lost:
        record['old_rank'] = p8b3[cid]['rank']
        lost_data.append(record)
        loss_ids_found.add(cid)
    
    scanned += 1
    if gain_ids_found >= gained and loss_ids_found >= lost:
        break

print('=== GAINED CANDIDATES (new entries in Phase 8C.3) ===')
gained_data.sort(key=lambda x: x['new_rank'])
for d in gained_data:
    print(f'  NEW rank {d["new_rank"]:>3} | depth={d["depth"]} adj={d["adj"]:+.3f} trap={d["trap"]}')
    print(f'    {d["title"][:30]} @ {d["company"][:20]} ({d["years"]}y)')
    print(f'    career_ai={d["career_ai"]} eval={d["has_eval"]} ret={d["has_ret"]}')
    print(f'    snippet: {d["snippet"][:160]}')
    print()

print()
print('=== LOST CANDIDATES (removed from Phase 8C.3) ===')
lost_data.sort(key=lambda x: x['old_rank'])
for d in lost_data:
    print(f'  WAS rank {d["old_rank"]:>3} | depth={d["depth"]} adj={d["adj"]:+.3f} trap={d["trap"]}')
    print(f'    {d["title"][:30]} @ {d["company"][:20]} ({d["years"]}y)')
    print(f'    career_ai={d["career_ai"]} eval={d["has_eval"]} ret={d["has_ret"]}')
    print(f'    snippet: {d["snippet"][:160]}')
    print()

print()
print('=== RANK MOVEMENTS IN STAYED CANDIDATES ===')
movements = [(abs(p8c3[cid]['rank'] - p8b3[cid]['rank']), cid, p8c3[cid]['rank'], p8b3[cid]['rank']) for cid in stayed]
movements.sort(reverse=True)
print(f'  Candidates with rank change > 10: {sum(1 for m in movements if m[0] > 10)}')
print(f'  Candidates with rank change > 5:  {sum(1 for m in movements if m[0] > 5)}')
print(f'  Mean rank change: {sum(m[0] for m in movements)/len(movements):.1f}')
print()
print('  Top movements:')
for delta, cid, new_r, old_r in movements[:10]:
    direction = '↑' if new_r < old_r else '↓'
    print(f'    {direction} {old_r:>3} -> {new_r:>3} (delta={delta:>2}) {cid}')

print()
print('=== TOP-10 STABILITY CHECK ===')
old_top10 = {cid for cid, d in p8b3.items() if d['rank'] <= 10}
new_top10 = {cid for cid, d in p8c3.items() if d['rank'] <= 10}
print(f'  Top-10 overlap: {len(old_top10 & new_top10)}/10')
if old_top10 - new_top10:
    print(f'  Removed from top-10: {old_top10 - new_top10}')
if new_top10 - old_top10:
    print(f'  Added to top-10: {new_top10 - old_top10}')

print()
print('=== TOP-50 QUALITY CHECK ===')
old_top50 = {cid for cid, d in p8b3.items() if d['rank'] <= 50}
new_top50 = {cid for cid, d in p8c3.items() if d['rank'] <= 50}
print(f'  Top-50 overlap: {len(old_top50 & new_top50)}/50')
gained_in_50 = new_top50 - old_top50
print(f'  New entries in top-50: {len(gained_in_50)}')

print()
print('=== SCORE DISTRIBUTION COMPARISON ===')
tiers = [(1,10), (11,30), (31,50), (51,75), (76,100)]
for lo, hi in tiers:
    old_scores = [d['score'] for d in p8b3.values() if lo <= d['rank'] <= hi]
    new_scores = [d['score'] for d in p8c3.values() if lo <= d['rank'] <= hi]
    print(f'  Rank {lo:>3}-{hi:<3}: 8B.3=[{min(old_scores):.4f},{max(old_scores):.4f}]  8C.3=[{min(new_scores):.4f},{max(new_scores):.4f}]')

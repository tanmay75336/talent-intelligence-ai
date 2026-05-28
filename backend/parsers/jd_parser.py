from backend.parsers.jd_analyzer import analyze_job_description


def extract_skills_from_jd(jd_text):
    jd_analysis = analyze_job_description(jd_text)
    return jd_analysis.all_skills

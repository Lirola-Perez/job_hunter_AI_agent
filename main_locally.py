import json
import os
import time
import requests
from pypdf import PdfReader

# Local Ollama endpoint configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"  # Or "llama3.2:3b"

# Pre-filtering Keyword Arrays
AEC_KEYWORDS = [
    "construction", "building", "civil", "structural", "bim", 
    "facade", "geotechnical", "aec", "architectural", "structure"
]

TECH_KEYWORDS = [
    "python", "machine learning", "deep learning", "ai", "data science", 
    "developer", "computational", "automation", "algorithm", "data"
]

def load_resume(file_path: str = "resume.pdf") -> str:
    """Loads PDF or TXT resume."""
    if not os.path.exists(file_path):
        print(f"[Notice] '{file_path}' not found.")
        return ""
    
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def fetch_remotive_all():
    """Returns active remote jobs from Remotive."""
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            raw_jobs = res.json().get("jobs", [])
            return [{
                "position": j.get("title", ""),
                "company": j.get("company_name", ""),
                "location": j.get("candidate_required_location", "Remote"),
                "url": j.get("url", ""),
                "description": j.get("description", ""),
                "source": "Remotive"
            } for j in raw_jobs]
    except Exception as e:
        print(f"Error fetching Remotive: {e}")
    return []

def fetch_remoteok_all():
    """Returns recent remote jobs from RemoteOK."""
    try:
        res = requests.get("https://remoteok.com/api", headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if res.status_code == 200:
            data = res.json()
            raw_jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []
            return [{
                "position": j.get("position", ""),
                "company": j.get("company", ""),
                "location": j.get("location", "Remote"),
                "url": j.get("url", ""),
                "description": f"{j.get('description', '')} {' '.join(j.get('tags', []))}",
                "source": "RemoteOK"
            } for j in raw_jobs]
    except Exception as e:
        print(f"Error fetching RemoteOK: {e}")
    return []

def fetch_recent_jobs():
    """Fetches raw jobs and performs strict pre-filtering locally."""
    all_raw_jobs = fetch_remotive_all() + fetch_remoteok_all()
    filtered_jobs = []
    
    for job in all_raw_jobs:
        text = f"{job['position']} {job['description']}".lower()
        
        has_aec = any(kw in text for kw in AEC_KEYWORDS)
        has_tech = any(kw in text for kw in TECH_KEYWORDS)

        if has_aec and has_tech:
            filtered_jobs.append(job)

    return filtered_jobs

def evaluate_job_locally(job: dict, resume_text: str) -> dict:
    """Evaluates a job posting using Ollama running locally."""
    prompt = f"""
    You are a specialized recruitment AI for Building, Civil, and Construction Engineering combined with Python/ML/Data Science.
    Compare the following Candidate CV against the Job Description.

    CANDIDATE RESUME:
    {resume_text}

    JOB POSTING:
    Title: {job.get('position')}
    Company: {job.get('company')}
    Location: {job.get('location', 'Remote')}
    URL: {job.get('url')}
    Description: {job.get('description', '')[:2500]}

    CRITICAL EVALUATION RULES:
    1. If the role lacks Python/ML/Automation OR lacks AEC/Civil/Structural engineering context, assign match_score <= 4.
    2. Assign match_score between 1 and 10.
    3. Return strictly a JSON object with this exact structure:
    {{
      "company": "{job.get('company')}",
      "title": "{job.get('position')}",
      "match_score": 8,
      "location": "{job.get('location', 'Remote')}",
      "application_url": "{job.get('url')}",
      "summary": "Specific reason why this role aligns with the candidate CV."
    }}
    """

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "format": "json",  # Enforces structured JSON output from Ollama
        "stream": False
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"Ollama error {res.status_code}: {res.text}")

    response_json = res.json()
    raw_response = response_json.get("response", "{}")
    return json.loads(raw_response)

def main_locally():
    resume_text = load_resume("resume.pdf")
    if not resume_text:
        raise ValueError("Please place your 'resume.pdf' in the project folder.")

    # Check if Ollama is running locally
    try:
        requests.get("http://localhost:11434/", timeout=2)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Ollama is not running! Start it in your terminal with: 'ollama run qwen2.5:7b'"
        )

    jobs = fetch_recent_jobs()
    print(f"Loaded CV ({len(resume_text)} chars). Found {len(jobs)} relevant AEC + Tech jobs to analyze.\n")

    matched_jobs = []
    for idx, job in enumerate(jobs, 1):
        try:
            result = evaluate_job_locally(job, resume_text)
            score = result.get("match_score", 0)
            print(f"[{idx}/{len(jobs)}] {result.get('title')} @ {result.get('company')} - Score: {score}/10")
            
            if score >= 7:
                matched_jobs.append(result)
        except Exception as err:
            print(f"[{idx}/{len(jobs)}] Error evaluating {job.get('position')}: {err}")

        time.sleep(0.5)

    print(f"\n=== TOP MATCHES ({len(matched_jobs)}) ===")
    for match in matched_jobs:
        print(f"\n[{match.get('match_score')}/10] {match.get('title')} @ {match.get('company')}")
        print(f"Apply: {match.get('application_url')}")
        print(f"Fit Reason: {match.get('summary')}")

if __name__ == "__main__":
    main_locally()
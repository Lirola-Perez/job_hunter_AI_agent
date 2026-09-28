import json
import os
import time
import requests
from pypdf import PdfReader
from google import genai
from google.genai import types

# Target keywords to pre-filter construction roles before API calls
# Keywords for pre-filtering locally BEFORE calling Gemini
# Pre-filtering Keyword Arrays
AEC_KEYWORDS = [
    "construction", "building", "civil", "structural", "bim", 
    "facade", "geotechnical", "aec", "architectural", "structure"
]

TECH_KEYWORDS = [
    "python", "machine learning", "deep learning", "ai", "data science", 
    "developer", "computational", "automation", "algorithm", "data"
]
def fetch_recent_jobs():
    # 1. Fetch raw standard jobs from both APIs
    all_raw_jobs = fetch_remotive_all() + fetch_remoteok_all()
    
    filtered_jobs = []
    
    # 2. Filter locally to match BOTH criteria
    for job in all_raw_jobs:
        text = f"{job['position']} {job['description']}".lower()
        
        has_aec = any(kw in text for kw in AEC_KEYWORDS)
        has_tech = any(kw in text for kw in TECH_KEYWORDS)

        # Only pass jobs that satisfy both AEC and Python/ML requirements
        if has_aec and has_tech:
            filtered_jobs.append(job)

    return filtered_jobs

def load_resume(file_path: str = "resume.pdf") -> str:
    """Loads PDF or TXT resume."""
    if not os.path.exists(file_path):
        print(f"[Notice] '{file_path}' not found. Using fallback profile JSON.")
        return ""
    
    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

# def fetch_recent_jobs():
#     url = "https://remoteok.com/api"
#     headers = {"User-Agent": "Mozilla/5.0"}
    
#     response = requests.get(url, headers=headers)
#     data = response.json()
#     others = fetch_remotive_all()
#     data.append(others)
    
#     raw_jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []

#     return [
#         job for job in raw_jobs
#         if any(kw in f"{job.get('position', '')} {' '.join(job.get('tags', []))}".lower() for kw in TARGET_KEYWORDS)
#     ]

def fetch_remotive_all():
    """Returns ~1,000 active remote jobs from Remotive."""
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            raw_jobs = res.json().get("jobs", [])
            # Map Remotive schema to standardized schema
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
            # RemoteOK places API terms/disclaimers in index 0; skip it
            raw_jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []
            # Map RemoteOK schema to standardized schema
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

def evaluate_job(client: genai.Client, job: dict, resume_text: str) -> dict:
    prompt = f"""
    You are a specialized recruitment AI for Building, Civil, and Construction Engineering.
    Compare the following Candidate CV against the Job Description.

    CANDIDATE RESUME:
    {resume_text}

    JOB POSTING:
    Title: {job.get('position')}
    Company: {job.get('company')}
    Location: {job.get('location', 'Remote')}
    URL: {job.get('url')}
    Description: {job.get('description', '')[:2500]}

    CRITICAL RULES:
    - If the position is NOT related to Building, Civil, or Construction Engineering, assign match_score = 1.
    - Evaluate technical skill overlap, project management experience, and credentials.
    - Return strictly JSON in this schema:
    {{
      "company": "Company Name",
      "title": "Job Title",
      "match_score": 8,
      "location": "Location",
      "application_url": "URL",
      "summary": "Specific reason why this role aligns with the CV."
    }}
    """

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            )
        )
    )

    clean_text = (response.text or "").strip()
    
    # Strip markdown block quotes if present
    if clean_text.startswith("```"):
        lines = clean_text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean_text = "\n".join(lines).strip()

    return json.loads(clean_text)

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY secret is missing.")

    resume_text = load_resume("resume.pdf")
    if not resume_text:
        raise ValueError("Please place your 'resume.pdf' in the project folder.")

    client = genai.Client(
        api_key=api_key,
        http_options={'api_version': 'v1'}
    )
    jobs = fetch_recent_jobs()

    print(f"Loaded CV ({len(resume_text)} chars). Found {len(jobs)} relevant construction jobs to analyze.\n")

    matched_jobs = []
    for idx, job in enumerate(jobs, 1):
        try:
            result = evaluate_job(client, job, resume_text)
            score = result.get("match_score", 0)
            print(f"[{idx}/{len(jobs)}] {result.get('title')} @ {result.get('company')} - Score: {score}/10")
            
            if score >= 7:
                matched_jobs.append(result)
        except Exception as err:
            print(f"[{idx}/{len(jobs)}] Error evaluating {job.get('position')}: {err}")

        time.sleep(2)

    print(f"\n=== TOP MATCHES ({len(matched_jobs)}) ===")
    for match in matched_jobs:
        print(f"\n[{match['match_score']}/10] {match['title']} @ {match['company']}")
        print(f"Apply: {match['application_url']}")
        print(f"Fit Reason: {match['summary']}")

if __name__ == "__main__":
    main()
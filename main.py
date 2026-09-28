import json
import os
import time
import requests
from pypdf import PdfReader
from google import genai
from google.genai import types

# Target keywords to pre-filter construction roles before API calls
TARGET_KEYWORDS = [ "construction", "building", "civil", "structural", "bim", "bem",
    "architectural", "mep", "facade", "quantity surveyor"
]

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

def fetch_recent_jobs():
    response = requests.get("[https://remoteok.com/api](https://remoteok.com/api)", headers={"User-Agent": "Mozilla/5.0"})
    data = response.json()
    raw_jobs = data[1:] if isinstance(data, list) and len(data) > 1 else []

    # Pre-filter jobs locally to save API quota and execution time
    return [
        job for job in raw_jobs
        if any(kw in f"{job.get('position', '')} {' '.join(job.get('tags', []))}".lower() for kw in TARGET_KEYWORDS)
    ]

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
        model="gemini-1.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    response_text = response.text or ""
    clean_text = response_text.strip()
    if clean_text.startswith("```"):
        clean_text = "\n".join(clean_text.splitlines()[1:-1])

    return json.loads(clean_text)

def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY secret is missing.")

    resume_text = load_resume("resume.pdf")
    if not resume_text:
        raise ValueError("Please place your 'resume.pdf' in the project folder.")

    client = genai.Client(api_key=api_key)
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
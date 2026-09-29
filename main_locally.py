import json
import os
import time
import requests
from pypdf import PdfReader
from web_search import fetch_remoteok_all, fetch_remotive_all, fetch_weworkremotely, fetch_hn_hiring

# Default local Ollama endpoint configuration
OLLAMA_URL = "http://localhost:11434/api/generate"


def load_resume(file_path: str = "resume.pdf") -> str:
    """Loads PDF or TXT resume."""
    if not os.path.exists(file_path):
        print(f"[Notice] '{file_path}' not found.")
        return ""

    if file_path.endswith(".pdf"):
        reader = PdfReader(file_path)
        return "\n".join(
            [
                page.extract_text()
                for page in reader.pages
                if page.extract_text()
            ]
        )
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def fetch_recent_jobs(search_terms: str = ""):
    """Fetches raw jobs and performs pre-filtering using user keywords."""
    all_raw_jobs =  fetch_remotive_all() + \
                    fetch_remoteok_all() + \
                    fetch_weworkremotely() + \
                    fetch_hn_hiring()
    filtered_jobs = []

    # Parse comma-separated user keywords or fall back to defaults
    if search_terms == "default":
        keywords = [
                    "python",
                    "machine learning",
                    "deep learning",
                    "data scientist",
                    "data engineer",
                    "automation",
                    "researcher"
                ]
    elif search_terms.strip():
        keywords = [
            kw.strip().lower()
            for kw in search_terms.split(",")
            if kw.strip()
        ]
    else:
        raise Exception('No keywords specified')
        

    for job in all_raw_jobs:
        text = f"{job['position']} {job['description']}".lower()

        # Check if text contains at least one of the user keywords
        if any(kw in text for kw in keywords):
            filtered_jobs.append(job)

    return filtered_jobs


def evaluate_job_locally(
    job: dict,
    desired_location: str,
    resume_text: str, 
    model_name: str = "qwen2.5:7b"
) -> dict:
    """Evaluates a job posting using Ollama running locally."""
    prompt = f"""
    You are a specialized recruitment AI for Python/ML/AI Engineer/Data Science for Building and Construction Engineering.
    Compare the following Candidate CV against the Job Description.

    CANDIDATE RESUME:
    {resume_text}
    preferred_location: {desired_location}

    JOB POSTING:
    Title: {job.get('position')}
    Company: {job.get('company')}
    JobLocation: {job.get('location', 'Remote')}
    URL: {job.get('url')}
    Description: {job.get('description', '')[:2500]}

    CRITICAL EVALUATION RULES:
    1. HARD DISQUALIFICATIONS (match_score = 1):
       - Non-technical roles (Sales, Customer Service, Support, Account Manager).
    2. TECHNICAL MANDATES (Base Score):
       - If the role LACKS Python / Machine Learning / Data Science / Software Automation, match_score CANNOT exceed 4.
    3. BONUS WEIGHTING:
       - AEC / Civil / Structural / BIM / Computational Design context is a WELCOME PLUS (+1 to +2 points), but NOT required.
    4. LOCATION FILTERING:
       - If JobLocation is "Remote" keep score unchanged.
       - If JobLocation is '{desired_location}' add 1 point. 
       - If JobLocation specifies a region mismatch (e.g., "US Only" vs candidate preferred '{desired_location}'), deduct 2 points.
    4. BOUNDS:
       - Return an integer match_score between 1 and 10.
    6. Return strictly a JSON object with this exact structure:
    {{
      "company": "{job.get('company')}",
      "title": "{job.get('position')}",
      "match_score": 7,
      "location": "{job.get('location', 'Remote')}",
      "application_url": "{job.get('url')}",
      "summary": "Specific reason why this role aligns with the candidate CV."
    }}
    """

    payload = {
        "model": model_name,
        "prompt": prompt,
        "format": "json",
        "stream": False,
        "keep_alive": -1,  # Keeps the model loaded in VRAM between requests (no reload delays)
        "options": {
            "num_ctx": 8192,  # Expands context window so full CV + job description fit without clipping
            "temperature": 0.1,  # Lowers randomness for consistent score evaluation & structured JSON
            "num_predict": 512,  # Cap max output tokens since structured JSON summary is short
        },
    }

    res = requests.post(OLLAMA_URL, json=payload, timeout=(10, 180))
    if res.status_code != 200:
        raise RuntimeError(f"Ollama error {res.status_code}: {res.text}")

    response_json = res.json()
    raw_response = response_json.get("response", "{}")
    return json.loads(raw_response)


def run_job_hunter(
    cv_path: str = "resume.pdf",
    location: str = "Berlin",
    search_terms: str = "",
    threshold: int = 6,
    model_name: str = "llama3.2:3b",
) -> list:
    """Main pipeline entrypoint called by Streamlit (app.py)."""
    resume_text = load_resume(cv_path)
    if not resume_text:
        raise ValueError(
            f"Could not read resume text from uploaded path: '{cv_path}'"
        )

    # Ensure Ollama daemon is reachable
    try:
        requests.get("http://localhost:11434/", timeout=2)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Ollama is not running! Ensure 'services.ollama' is running on port 11434."
        )

    jobs = fetch_recent_jobs(search_terms)
    matched_jobs = []

    for job in jobs:
        try:
            result = evaluate_job_locally(job, location, resume_text, model_name)
            score = result.get("match_score", 0)

            if score >= threshold:
                matched_jobs.append(result)
        except Exception as err:
            print(f"Error evaluating {job.get('position')}: {err}")

        time.sleep(0.2)

    return matched_jobs


# Retain direct CLI support when executed outside Streamlit
if __name__ == "__main__":
    results = run_job_hunter()
    print(f"\nFound {len(results)} matches.")
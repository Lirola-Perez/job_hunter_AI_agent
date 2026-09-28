import os
import json
import requests
import time
from google import genai
from google.genai import types
from google.genai.errors import APIError

def load_candidate_profile() -> dict:
    """Loads candidate profile from GitHub Secret/Env or local JSON file."""
    # 1. Check if provided via environment variable (CI/CD / GitHub Actions)
    env_profile = os.environ.get("CANDIDATE_PROFILE_JSON")
    if env_profile:
        return json.loads(env_profile)

    # 2. Check for local profile.json file (Local development)
    if os.path.exists("profile.json"):
        with open("profile.json", "r", encoding="utf-8") as f:
            return json.load(f)

    # 3. Fallback to template if nothing is configured
    if os.path.exists("profile.template.json"):
        with open("profile.template.json", "r", encoding="utf-8") as f:
            return json.load(f)

    raise FileNotFoundError("No valid candidate profile configuration found.")

def fetch_recent_jobs():
    """Fetches job listings from open API endpoints."""
    url = "https://remoteok.com/api"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        # Exclude header metadata item from payload
        return response.json()[1:20]
    return []

def evaluate_job(client: genai.Client, job: dict, profile: dict, max_retries: int = 3):
    """Uses Gemini to score job fit and extract exact location details."""
    prompt = f"""
    Analyze the following job description against the target candidate profile.

    Candidate Profile:
    {json.dumps(profile, indent=2)}

    Job Details:
    Title: {job.get('position')}
    Company: {job.get('company')}
    Declared Location: {job.get('location', 'Remote/Unspecified')}
    URL: {job.get('url')}
    Description: {job.get('description', '')[:2500]}

    Instructions:
    Return ONLY a valid JSON object matching this strict schema:
    {{
      "company": "Company Name",
      "title": "Job Title",
      "match_score": 8,
      "location": "Physical City, Country, or Remote Region",
      "application_url": "Direct application URL",
      "summary": "1-sentence reason for match quality"
    }}
    """

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            text_content = (response.text or "").strip()

            # Clean markdown formatting if present
            if text_content.startswith("```"):
                lines = text_content.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text_content = "\n".join(lines).strip()

            return json.loads(text_content)

        except APIError as e:
            # Handle rate limits (429) or temporary server unavailability (503)
            if e.code in (429, 503) and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 12  # Wait 12s, 24s, etc. before retrying
                print(f"  [Warning] Received {e.code} for '{job.get('position')}'. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e
            
def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client(api_key=api_key)
    profile = load_candidate_profile()
    jobs = fetch_recent_jobs()
    min_score = profile.get("min_match_score", 7)

    # Load candidate profile from environment secret
    profile = json.loads(os.getenv("CANDIDATE_PROFILE_JSON", "{}"))

    # Extract min_match_score, defaulting to 7 if not specified in JSON
    MIN_MATCH_SCORE = profile.get("min_match_score", 7)

    print(f"Scanning {len(jobs)} jobs (Minimum match threshold: {min_score}/10)...")
    matches = []

    # Main Loop Execution inside main()
    for idx, job in enumerate(jobs, 1):
        try:
            result = evaluate_job(client, job, profile)
            if result:
                if result.get("match_score", 0) >= MIN_MATCH_SCORE:
                    matches.append(result)
        except Exception as err:
            print(f"Error processing job '{job.get('position')}': {err}")

        # Enforce rate-limiting pause between requests (15 requests/min max)
        time.sleep(4)

    # Output formatted results
    print(f"\n=== MATCHED ROLES FOUND: {len(matches)} ===")
    for match in matches:
        print(f"\n[{match['match_score']}/10] {match['title']} @ {match['company']}")
        print(f"Location: {match['location']}")
        print(f"Apply Link: {match['application_url']}")
        print(f"Fit Summary: {match['summary']}")

if __name__ == "__main__":
    main()
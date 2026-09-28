import os
import json
import requests
from google import genai
from google.genai import types

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

def evaluate_job(client: genai.Client, job: dict, profile: dict) -> dict:
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
    Return ONLY a raw valid JSON object with these keys: "company", "title", "match_score", "location", "application_url", "summary".
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    text_content = (response.text or "").strip()

    # Clean markdown code block wrappers if present
    if text_content.startswith("```"):
        lines = text_content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text_content = "\n".join(lines).strip()

    return json.loads(text_content)

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client(api_key=api_key)
    profile = load_candidate_profile()
    jobs = fetch_recent_jobs()
    min_score = profile.get("min_match_score", 7)

    print(f"Scanning {len(jobs)} jobs (Minimum match threshold: {min_score}/10)...")
    matches = []

    for job in jobs:
        try:
            eval_result = evaluate_job(client, job, profile)
            if eval_result.get("match_score", 0) >= min_score:
                matches.append(eval_result)
        except Exception as err:
            print(f"Error processing job '{job.get('position', 'Unknown')}': {err}")

    # Output formatted results
    print(f"\n=== MATCHED ROLES FOUND: {len(matches)} ===")
    for match in matches:
        print(f"\n[{match['match_score']}/10] {match['title']} @ {match['company']}")
        print(f"Location: {match['location']}")
        print(f"Apply Link: {match['application_url']}")
        print(f"Fit Summary: {match['summary']}")

if __name__ == "__main__":
    main()
import requests
import xml.etree.ElementTree as ET


def fetch_remotive_all():
    """Returns active remote jobs from Remotive."""
    try:
        res = requests.get("https://remotive.com/api/remote-jobs", timeout=10)
        if res.status_code == 200:
            raw_jobs = res.json().get("jobs", [])
            return [
                {
                    "position": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location", "Remote"),
                    "url": j.get("url", ""),
                    "description": j.get("description", ""),
                    "source": "Remotive",
                }
                for j in raw_jobs
            ]
    except Exception as e:
        print(f"Error fetching Remotive: {e}")
    return []


def fetch_remoteok_all():
    """Returns recent remote jobs from RemoteOK."""
    try:
        res = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if res.status_code == 200:
            data = res.json()
            raw_jobs = (
                data[1:] if isinstance(data, list) and len(data) > 1 else []
            )
            return [
                {
                    "position": j.get("position", ""),
                    "company": j.get("company", ""),
                    "location": j.get("location", "Remote"),
                    "url": j.get("url", ""),
                    "description": f"{j.get('description', '')} {' '.join(j.get('tags', []))}",
                    "source": "RemoteOK",
                }
                for j in raw_jobs
            ]
    except Exception as e:
        print(f"Error fetching RemoteOK: {e}")
    return []

def fetch_weworkremotely():
    url = "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"
    res = requests.get(url, timeout=10)
    jobs = []
    if res.status_code == 200:
        root = ET.fromstring(res.content)
        for item in root.findall("./channel/item"):
            if item is str:
                jobs.append(
                    {
                        "position": item.find("title").text,
                        "company": "We Work Remotely Listing",
                        "location": "Remote",
                        "url": item.find("link").text,
                        "description": item.find("description").text,
                        "source": "WeWorkRemotely",
                    }
                )
    return jobs

def fetch_hn_hiring():
    # Gets latest 'Who is Hiring' thread details via official HN API
    url = "https://hacker-news.firebaseio.com/v0/user/whoishiring.json"
    res = requests.get(url, timeout=10).json()
    submitted = res.get("submitted", [])

    # Grab top comments from the most recent thread
    latest_thread_id = submitted[0]
    thread_data = requests.get(
        f"https://hacker-news.firebaseio.com/v0/item/{latest_thread_id}.json"
    ).json()

    comments = thread_data.get("kids", [])[:30]  # Check first 30 postings
    jobs = []
    for comment_id in comments:
        item = requests.get(
            f"https://hacker-news.firebaseio.com/v0/item/{comment_id}.json"
        ).json()
        if item and "text" in item and not item.get("deleted"):
            jobs.append(
                {
                    "position": "HN Community Role",
                    "company": "Startup (HN)",
                    "location": "Remote",
                    "url": f"https://news.ycombinator.com/item?id={comment_id}",
                    "description": item.get("text", ""),
                    "source": "HackerNews",
                }
            )
    return jobs
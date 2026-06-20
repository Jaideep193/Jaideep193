import os, re, base64, textwrap, requests

username = os.environ["GH_USERNAME"]
token    = os.environ["GH_TOKEN"]
headers  = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Fetch all owner repos ────────────────────────────────────────────────────
repos, page = [], 1
while True:
    r = requests.get(
        "https://api.github.com/user/repos",
        headers=headers,
        params={"per_page": 100, "page": page,
            "sort": "created", "direction": "desc", "type": "owner"},
    )
    data = r.json()
    if not isinstance(data, list) or not data:
        break
    repos.extend(data)
    page += 1

# Live repos: non-fork, non-archived, not the profile repo itself
live_repos = {
    repo["name"]
    for repo in repos
    if repo["name"].lower() != username.lower()
    and not repo.get("fork", False)
    and not repo.get("archived", False)
}
# ── README summariser ────────────────────────────────────────────────────────
def fetch_readme_text(repo_name):
    """Fetch the raw README of a repo (max 4000 chars)."""
    url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return ""
    content = r.json().get("content", "")
    try:
        text = base64.b64decode(content).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return text[:4000]

def clean_markdown(text):
    """Strip markdown, code, badges, and noise — return plain prose."""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    text = re.sub(r"^[-*_]{3,}\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+>]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\|[-: ]+\|", " ", text)
    text = re.sub(r"\|", " ", text)
    lines = text.split("\n")
    good_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        real_words = re.findall(r"[A-Za-z]{2,}", stripped)
        if len(real_words) < 2:
            continue
        if re.match(r"^(https?|www\.|#|/\*|---|`|\|)", stripped):
            continue
        good_lines.append(stripped)
    return " ".join(good_lines)


def extract_summary(repo_name, fallback_desc=""):
    """Return a complete, clean project description (1-3 sentences)."""
    # Priority 1: Use the GitHub description if meaningful
    if fallback_desc and len(fallback_desc.split()) >= 4:
        desc = fallback_desc.strip()
        # Split into sentences and return complete sentences up to 300 chars
        parts = re.split(r"(?<=[.!?])\s+", desc)
        result = []
        total = 0
        for p in parts:
            if total + len(p) > 300:
                break
            result.append(p)
            total += len(p) + 1
        if result:
            return " ".join(result)
        # If single very long sentence, truncate at word boundary
        if len(desc) > 300:
            cut = desc[:300].rsplit(" ", 1)[0]
            return cut + "..."
        return desc

    # Priority 2: Extract from README
    raw = fetch_readme_text(repo_name)
    if not raw:
        return fallback_desc or "No description available."

    plain = clean_markdown(raw)
    plain = re.sub(r"\s+", " ", plain).strip()

    sentences = re.split(r"(?<=[.!?])\s+", plain)
    good = []
    for s in sentences:
        s = s.strip()
        words = s.split()
        if len(words) < 5 or len(words) > 80:
            continue
        if re.search(r"https?://", s):
            continue
        if re.search(r"[|\\<>{}]", s):
            continue
        good.append(s)
        if len(good) == 2:
            break

    if good:
        return " ".join(good)

    # Last resort: find a natural break point in cleaned text
    text = plain[:280]
    if len(plain) > 280:
        last_period = max(text.rfind(". "), text.rfind("! "), text.rfind("? "))
        if last_period > 100:
            return text[:last_period + 1]
        text = text.rsplit(" ", 1)[0] + "..."
    return text or fallback_desc or "No description available."


def keep_entry(m):
    entry_text = m.group(0)
    names = re.findall(
        r"https://github\.com/" + re.escape(username) + r"/([^/)\s\"']+)",
        entry_text, re.I
    )
    if names and names[0] not in live_repos:
        removed.append(names[0])
        return ""
    return entry_text

cleaned_block = entry_pattern.sub(keep_entry, block)

# Re-derive existing repos after removal
existing_after_clean = set(re.findall(
    r"https://github\.com/" + re.escape(username) + r"/([^/)\s\"']+)",
    cleaned_block, re.I
))

# ── Badge helpers ────────────────────────────────────────────────────────────
LANG_COLOR = {
    "Python": "3776AB", "JavaScript": "F7DF1E", "TypeScript": "3178C6",
    "Java": "007396", "Go": "00ADD8", "C++": "00599C",
    "Jupyter Notebook": "DA5B0B", "HTML": "E34F26", "CSS": "1572B6",
    "Rust": "000000", "Shell": "89E051",
}
LANG_LOGO = {
    "Python": "python", "JavaScript": "javascript", "TypeScript": "typescript",
    "Java": "openjdk", "Go": "go", "Jupyter Notebook": "jupyter",
    "HTML": "html5", "CSS": "css3",
}
EMOJIS = [
    (["fire", "forest", "wildfire"], "🔥"),
    (["cardiac", "heart", "ecg", "arrhythmia"], "🫀"),
    (["portfolio", "personal site", "portfolio website"], "🌐"),
    (["java", "ecommerce", "e-commerce"], "☕"),
    (["chatbot", "gemini", "gpt", "llm", "multimodal"], "🤖"),
    (["house", "price", "regression"], "🏡"),
    (["face", "facial", "attendance"], "🧑‍💼"),
    (["aqi", "air quality", "delhi"], "🏙️"),
    (["gesture", "hand"], "✋"),
    (["data", "analytics", "analysis"], "📊"),
    (["cloud", "gcp", "aws", "azure"], "☁️"),
    (["lunar", "moon", "satellite", "chandrayaan"], "🌙"),
]

def pick_emoji(name, desc):
    text = (name + " " + desc).lower()
    for kws, emoji in EMOJIS:
        if any(k in text for k in kws):
            return emoji
    return "🚀"

def badge(lang):
    if not lang:
        return ""
    color = LANG_COLOR.get(lang, "555555")
    slug = lang.replace(" ", "%20").replace("+", "%2B")
    logo = LANG_LOGO.get(lang)
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    return f"![{lang}](https://img.shields.io/badge/{slug}-{color}?style=flat-square{logo_part})"

def topic_badge(label):
    label = label.replace("-", " ").title()
    slug = label.replace(" ", "%20")
    return f"![{label}](https://img.shields.io/badge/{slug}-0A66C2?style=flat-square)"

# ── Fetch topics for repos ──────────────────────────────────────────────────
def fetch_topics(repo_name):
    """Fetch topics for a repo via the GitHub API."""
    url = f"https://api.github.com/repos/{username}/{repo_name}/topics"
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json().get("names", [])
    return []

# ── Build entries for ALL live repos (refresh existing + add new) ────────────
all_entries, added, updated = [], [], []
for repo in repos:
    if repo["name"].lower() == username.lower():
        continue
    if repo.get("fork", False) or repo.get("archived", False):
        continue

    name = repo["name"]
    fallback = (repo.get("description") or "").strip().rstrip(".")
    url = repo["html_url"]
    lang = repo.get("language")
    stars = repo.get("stargazers_count", 0)
    topics = fetch_topics(name)[:4]
    emoji = pick_emoji(name, fallback)
    title = name.replace("_", " ").replace("-", " ").title()

    print(f"Processing {name}...")
    summary = extract_summary(name, fallback)

    # Build badge line
    badges = []
    if lang:
        badges.append(badge(lang))
    for t in topics:
        badges.append(topic_badge(t))
    badge_line = " ".join(badges)

    # Build attractive card
    entry = f"#### {emoji} **[{title}]({url})**\n"
    if badge_line:
        entry += badge_line + "\n"
    entry += f"> {summary}\n"
    if stars > 0:
        entry += f"\n[⭐ {stars} stars]({url}) &nbsp; [→ View Project]({url})\n"
    else:
        entry += f"\n[→ View Project]({url})\n"
    entry += "\n---\n\n"

    all_entries.append(entry)
    if name in existing_after_clean:
        updated.append(name)
    else:
        added.append(name)

if not all_entries and not removed:
    print("No changes needed - README unchanged.")
    raise SystemExit

# Replace the entire featured block with freshly generated entries
insert_text = "\n" + "".join(all_entries)
new_readme = readme[:si + len(START)] + insert_text + readme[ei:]

with open("README.md", "w", encoding="utf-8") as f:
    f.write(new_readme)

if added:
    print(f"Added {len(added)} new project(s): {', '.join(added)}")
if updated:
    print(f"Refreshed {len(updated)} existing project(s): {', '.join(updated)}")
if removed:
    print(f"Removed {len(removed)} project(s): {', '.join(removed)}")

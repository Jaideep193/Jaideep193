import os, re, base64, requests

username = os.environ["GH_USERNAME"]
token    = os.environ["GH_TOKEN"]
headers  = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── Fetch all owner repos ────────────────────────────────────────────────────────────
repos, page = [], 1
while True:
    r = requests.get(
        "https://api.github.com/user/repos",
        headers=headers,
        params={"per_page": 100, "page": page,
            "sort": "pushed", "direction": "desc", "type": "owner"},
    )
    data = r.json()
    if not isinstance(data, list) or not data:
        break
    repos.extend(data)
    page += 1

# Live repos: non-fork, non-archived, not the profile repo itself
# Sorted by pushed_at (most recently edited first)
live_repos = {
    repo["name"]
    for repo in repos
    if repo["name"].lower() != username.lower()
    and not repo.get("fork", False)
    and not repo.get("archived", False)
}

# Sort repos list by pushed_at descending (most recently edited first)
repos_sorted = sorted(
    [r for r in repos if r["name"] in live_repos],
    key=lambda r: r.get("pushed_at", ""),
    reverse=True
)
# ── README summariser ────────────────────────────────────────────────────────────
def fetch_readme_text(repo_name):
    """Fetch the raw README content for a repo via the GitHub API."""
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/readme",
        headers={**headers, "Accept": "application/vnd.github.raw+json"},
    )
    if r.status_code != 200:
        return ""
    return r.text


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
    """Return a rich 5-sentence project description."""
    # Get GitHub description (Priority 1 - clean human text)
    desc_sentences = []
    if fallback_desc and len(fallback_desc.split()) >= 3:
        parts = re.split(r"(?<=[.!?])\s+", fallback_desc.strip())
        desc_sentences = [p.strip() for p in parts if len(p.split()) >= 3]

    # Get README content (Priority 2)
    raw = fetch_readme_text(repo_name)
    readme_sentences = []
    if raw:
        plain = clean_markdown(raw)
        plain = re.sub(r"\s+", " ", plain).strip()
        all_sentences = re.split(r"(?<=[.!?])\s+", plain)
        for s in all_sentences:
            s = s.strip()
            words = s.split()
            if len(words) < 5 or len(words) > 60:
                continue
            if re.search(r"https?://", s):
                continue
            if re.search(r"[|\\<>{}@#]", s):
                continue
            readme_sentences.append(s)
            if len(readme_sentences) >= 5:
                break

    # Combine: desc first, then readme sentences, no duplicates, cap at 5
    combined = []
    seen_words = set()
    for s in desc_sentences + readme_sentences:
        key = " ".join(s.lower().split()[:6])
        if key not in seen_words:
            seen_words.add(key)
            combined.append(s)
        if len(combined) >= 5:
            break

    # Build exactly 5-sentence summary
    if len(combined) >= 5:
        return " ".join(combined[:5])
    elif combined:
        result = " ".join(combined)
        title = repo_name.replace("-", " ").replace("_", " ").title()
        if len(combined) < 3:
            result += f" This project focuses on {title.lower()} and provides practical implementations using modern tools and techniques."
        if len(combined) < 5:
            result += f" It is actively maintained with clean code, thorough documentation, and follows software engineering best practices."
        return result
    else:
        title = repo_name.replace("-", " ").replace("_", " ").title()
        return (f"This project covers {title.lower()} with practical real-world implementation. "
                f"It uses modern technologies and frameworks following best development practices. "
                f"The codebase is clean, well-structured, and thoroughly documented. "
                f"It is actively maintained and open to community contributions and feedback. "
                f"Explore the repository to discover more about {title.lower()} in action.")

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

# ── Badge helpers ──────────────────────────────────────────────────────────
LANG_COLOR = {
    "Python": "3776AB", "JavaScript": "F7DF1E", "TypeScript": "3178C6",
    "Java": "007396", "Go": "00ADD8", "C++": "00599C",
    "Jupyter Notebook": "DA5B0B", "HTML": "E34F26", "CSS": "1572B6",
    "Rust": "000000", "Shell": "89E051",
}
LANG_LOGO = {
    "Python": "python", "JavaScript": "javascript", "TypeScript": "typescript",
    "Java": "java", "Go": "go", "Jupyter Notebook": "jupyter",
    "HTML": "html5", "CSS": "css3", "Rust": "rust", "Shell": "gnubash",
}

# Rotating card accent colors - each project gets a different color
CARD_COLORS = [
    "FF6B6B",  # coral red
    "4ECDC4",  # teal
    "45B7D1",  # sky blue
    "96CEB4",  # sage green
    "FFEAA7",  # soft yellow
    "DDA0DD",  # plum
    "98D8C8",  # mint
    "F7DC6F",  # golden
    "BB8FCE",  # lavender
    "85C1E9",  # light blue
    "F0B27A",  # peach
    "82E0AA",  # light green
    "F1948A",  # salmon
    "AED6F1",  # pale blue
    "A9DFBF",  # pale green
    "FAD7A0",  # pale orange
    "D7BDE2",  # pale purple
    "A3E4D7",  # pale teal
]

# Topic badge colors - cycle through vibrant colors
TOPIC_COLORS = [
    "E74C3C", "E67E22", "F1C40F", "2ECC71", "1ABC9C",
    "3498DB", "9B59B6", "E91E63", "00BCD4", "FF5722",
    "607D8B", "795548", "FF9800", "8BC34A", "03A9F4",
]

def badge(lang):
    color = LANG_COLOR.get(lang, "555555")
    logo  = LANG_LOGO.get(lang, "")
    label = lang.replace(" ", "%20").replace("+", "%2B")
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    return f"![{lang}](https://img.shields.io/badge/{label}-{color}?style=flat-square{logo_part})"


def topic_badge(label, color_idx=0):
    color = TOPIC_COLORS[color_idx % len(TOPIC_COLORS)]
    encoded = label.replace("-", "%20").replace("_", "%20")
    display = label.replace("-", " ").replace("_", " ").title()
    return f"![{display}](https://img.shields.io/badge/{encoded}-{color}?style=flat-square)"


# ── Fetch topics for repos ────────────────────────────────────────────
def fetch_topics(repo_name):
    """Fetch topics for a repo via the GitHub API."""
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/topics",
        headers={**headers, "Accept": "application/vnd.github.mercy-preview+json"},
    )
    if r.status_code != 200:
        return []
    return r.json().get("names", [])

def pick_emoji(name, desc):
    """Pick a relevant emoji for the repo."""
    text = (name + " " + desc).lower()
    checks = [
        (["lunar", "moon", "satellite", "chandrayaan"], "👨‍🚀"),
        (["fire", "forest", "wildfire", "burn"], "🔥"),
        (["cardiac", "heart", "ecg", "health", "medical", "bio"], "🪀"),
        (["cloud", "aws", "azure", "gcp", "deploy"], "☁️"),
        (["brain", "neural", "deep", "learn", "ai", "ml", "model"], "🧠"),
        (["web", "frontend", "portfolio", "website", "react", "html"], "🌐"),
        (["robot", "automat", "bot", "script"], "🤖"),
        (["data", "analyt", "visual", "plot", "graph", "dashboard"], "📊"),
        (["security", "crypto", "auth", "hack"], "🔐"),
        (["game", "simulation", "model", "cellular"], "🎮"),
        (["image", "vision", "detect", "recogni", "segmen"], "👁️"),
        (["nlp", "text", "language", "chat", "llm", "gpt"], "💬"),
        (["geo", "map", "spatial", "gis", "remote"], "🗺️"),
    ]
    for keywords, emoji in checks:
        if any(k in text for k in keywords):
            return emoji
    return "📁"

# ── Build entries for ALL live repos (refresh existing + add new) ──────────────
all_entries, added, updated = [], [], []

for idx, repo in enumerate(repos_sorted):
    name     = repo["name"]
    fallback = (repo.get("description") or "").strip().rstrip(".")
    url      = repo["html_url"]
    lang     = repo.get("language")
    stars    = repo.get("stargazers_count", 0)
    forks    = repo.get("forks_count", 0)
    topics   = fetch_topics(name)[:5]
    emoji    = pick_emoji(name, fallback)
    title    = name.replace("_", " ").replace("-", " ").title()
    pushed   = (repo.get("pushed_at") or "")[:10]

    print(f"Processing {name}...")
    summary  = extract_summary(name, fallback)

    # Pick accent color (rotate through palette)
    accent   = CARD_COLORS[idx % len(CARD_COLORS)]

    # Build badge line
    badges = []
    if lang:
        badges.append(badge(lang))
    for ti, t in enumerate(topics):
        badges.append(topic_badge(t, ti + 1))
    badge_line = " ".join(badges)

    # Stars & forks line
    meta_parts = []
    if stars > 0:
        meta_parts.append(f"![Stars](https://img.shields.io/badge/⭐%20Stars-{stars}-{accent}?style=flat-square)")
    if forks > 0:
        meta_parts.append(f"![Forks](https://img.shields.io/badge/🔀%20Forks-{forks}-{accent}?style=flat-square)")
    if pushed:
        meta_parts.append(f"![Updated](https://img.shields.io/badge/📅%20Updated-{pushed.replace('-', '--')}-{accent}?style=flat-square)")
    meta_line = " ".join(meta_parts)

    # Build colorful animated card using HTML in markdown
    entry  = f"### {emoji} **[{title}]({url})**\n"
    if badge_line:
        entry += badge_line + "\n"
    if meta_line:
        entry += meta_line + "\n"
    entry += "\n"
    entry += f"> {summary}\n"
    entry += "\n"
    entry += f"[![View Project](https://img.shields.io/badge/🚀%20View%20Project-{accent}?style=for-the-badge)]({url})\n"
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

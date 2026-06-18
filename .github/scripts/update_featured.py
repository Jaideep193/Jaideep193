import os, re, base64, textwrap, requests

username = os.environ["GH_USERNAME"]
token    = os.environ["GH_TOKEN"]
headers  = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

# ── Fetch all owner repos ────────────────────────────────────────────────────
repos, page = [], 1
while True:
            r = requests.get("https://api.github.com/user/repos", headers=headers,
                                                  params={"per_page": 100, "page": page,
                                                                                       "sort": "created", "direction": "desc", "type": "owner"})
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
            """Fetch the raw README of a repo and return plain text (max ~4000 chars)."""
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
            """Strip markdown syntax and return plain sentences."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove images and badges  ![...](...) 
    text = re.sub(r"!\[[^\]]*\]\([^\)]*\)", " ", text)
    # Remove links but keep text  [text](url)
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    # Remove markdown headings markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove bold/italic
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", " ", text, flags=re.MULTILINE)
    # Remove bullet/numbered list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Remove table separators
    text = re.sub(r"\|[-: ]+\|", " ", text)
    text = re.sub(r"\|", " ", text)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def summarise_readme(repo_name, fallback_desc=""):
            """Return a 2-3 sentence summary derived from the repo README."""
    raw = fetch_readme_text(repo_name)
    if not raw:
                    return fallback_desc or "No description available."

    plain = clean_markdown(raw)

    # Split into sentences (naive but good enough)
    sentences = re.split(r'(?<=[.!?])\s+', plain)
    # Filter: keep sentences that are informative (>= 8 words, no pure URLs)
    good = []
    for s in sentences:
                    s = s.strip()
                    words = s.split()
                    if len(words) < 8:
                                        continue
                                    if re.match(r'^https?://', s):
                                                        continue
                                                    if s.count("http") > 2:
                                                                        continue
                                                                    good.append(s)

    if not good:
                    return fallback_desc or "No description available."

    # Pick up to 3 best sentences:
    # 1st sentence after the title (usually the project overview)
    # Then pick the longest remaining sentence (usually the most informative)
    chosen = [good[0]]
    remaining = good[1:]
    if remaining:
                    # pick the longest sentence that isn't too similar to the first
                    remaining.sort(key=lambda x: -len(x))
        for s in remaining:
                            # avoid near-duplicate starts
                            if s[:30].lower() != chosen[-1][:30].lower():
                                                    chosen.append(s)
                                                    break
                                        if len(remaining) > 1 and len(chosen) < 3:
                                                        for s in remaining:
                                                                            if s not in chosen and s[:30].lower() != chosen[-1][:30].lower():
                                                                                                    chosen.append(s)
                                                                                                    break

                                                                    summary = " ".join(chosen[:3])
    # Hard cap at 400 chars to keep README clean
    if len(summary) > 400:
                    summary = textwrap.shorten(summary, width=400, placeholder="...")
    return summary

# ── Read profile README ──────────────────────────────────────────────────────
with open("README.md", "r", encoding="utf-8") as f:
            readme = f.read()

START = "<!-- FEATURED-PROJECTS-START -->"
END   = "<!-- FEATURED-PROJECTS-END -->"
if START not in readme or END not in readme:
            print("Markers not found - nothing to do.")
    raise SystemExit

si = readme.index(START)
ei = readme.index(END)
block = readme[si + len(START):ei]

# ── REMOVAL: strip entries for repos that no longer exist ────────────────────
entry_pattern = re.compile(r'(### .+?(?=\n### |\Z))', re.DOTALL)
removed = []

def keep_entry(m):
            entry_text = m.group(1)
    names = re.findall(
                    r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""",
                    entry_text, re.I
    )
    if names and names[0] not in live_repos:
                    removed.append(names[0])
        return ""
    return entry_text

cleaned_block = entry_pattern.sub(keep_entry, block)

# Re-derive existing repos after removal
existing_after_clean = set(re.findall(
            r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""",
            cleaned_block, re.I
))

# ── Badge helpers ────────────────────────────────────────────────────────────
LANG_COLOR = {"Python": "3776AB", "JavaScript": "F7DF1E", "TypeScript": "3178C6",
                             "Java": "007396", "Go": "00ADD8", "C++": "00599C",
                             "Jupyter Notebook": "DA5B0B", "HTML": "E34F26", "CSS": "1572B6",
                             "Rust": "000000", "Shell": "89E051"}
LANG_LOGO  = {"Python": "python", "JavaScript": "javascript", "TypeScript": "typescript",
                             "Java": "openjdk", "Go": "go", "Jupyter Notebook": "jupyter",
                             "HTML": "html5", "CSS": "css3"}
EMOJIS = [
            (["fire", "forest", "wildfire"], "🔥"),
            (["cardiac", "heart", "ecg", "arrhythmia"], "🫀"),
            (["portfolio", "personal site", "portfolio website"], "🌐"),
            (["java", "ecommerce", "e-commerce"], "☕"),
            (["chatbot", "gemini", "gpt", "llm", "multimodal"], "🤖"),
            (["house", "price", "regression"], "🏡"),
            (["face", "facial", "attendance"], "🧑\u200d💼"),
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
            if not lang: return ""
                        color = LANG_COLOR.get(lang, "555555")
    slug  = lang.replace(" ", "%20").replace("+", "%2B")
    logo  = LANG_LOGO.get(lang)
    logo_part = f"&logo={logo}&logoColor=white" if logo else ""
    return f"![{lang}](https://img.shields.io/badge/{slug}-{color}?style=flat-square{logo_part})"

def topic_badge(label):
            label = label.replace("-", " ").title()
    slug  = label.replace(" ", "%20")
    return f"![{label}](https://img.shields.io/badge/{slug}-0A66C2?style=flat-square)"

# ── Build new entries ────────────────────────────────────────────────────────
new_entries, added = [], []
for repo in repos:
            if repo["name"] in existing_after_clean:
                            continue
    if repo["name"].lower() == username.lower():
                    continue
    if repo.get("fork", False) or repo.get("archived", False):
                    continue

    name      = repo["name"]
    fallback  = (repo.get("description") or "").strip().rstrip(".")
    url       = repo["html_url"]
    lang      = repo.get("language")
    topics    = repo.get("topics", [])[:4]
    emoji     = pick_emoji(name, fallback)
    title     = name.replace("_", " ").replace("-", " ")

    # Summarise from the project's README
    print(f"Summarising README for {name}...")
    summary = summarise_readme(name, fallback)

    badges = []
    if lang: badges.append(badge(lang))
                for t in topics: badges.append(topic_badge(t))
                            badge_line = " ".join(badges)

    entry = f"### {emoji} [{title}]({url})\n"
    if badge_line:
                    entry += badge_line + "\n"
    entry += summary + "\n"
    new_entries.append(entry)
    added.append(name)

if not new_entries and not removed:
            print("No changes needed - README unchanged.")
    raise SystemExit

insert_text = "\n".join(new_entries)
new_readme = readme[:si + len(START)] + cleaned_block + insert_text + readme[ei:]

with open("README.md", "w", encoding="utf-8") as f:
            f.write(new_readme)

if added:
            print(f"Added {len(added)} project(s): {', '.join(added)}")
if removed:
            print(f"Removed {len(removed)} project(s): {', '.join(removed)}")

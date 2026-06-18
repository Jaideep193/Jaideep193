import os, re, requests

username = os.environ["GH_USERNAME"]
token    = os.environ["GH_TOKEN"]
headers  = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

# Fetch all owner repos with a description
repos, page = [], 1
while True:
        r = requests.get("https://api.github.com/user/repos", headers=headers,
                                              params={"per_page":100,"page":page,"sort":"created","direction":"desc","type":"owner"})
        data = r.json()
        if not isinstance(data, list) or not data:
                    break
                repos.extend(data)
    page += 1

# Build a set of live repo names (non-fork, non-archived, with description)
live_repos = {
        repo["name"]
        for repo in repos
        if repo.get("description")
        and repo["name"].lower() != username.lower()
        and not repo.get("fork", False)
        and not repo.get("archived", False)
}

# Read README
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

# Find which repos are already in the block by URL
existing = set(re.findall(
        r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""", block, re.I))

# ── REMOVAL: strip entries for repos that no longer exist ──────────────────
# Each auto-generated entry starts with "### " and ends just before the next
# "### " or the end of the block. We rebuild the block keeping only entries
# whose repo name still exists in live_repos.
entry_pattern = re.compile(
        r'(### .+?(?=\n### |\Z))',
        re.DOTALL
)
removed = []
def keep_entry(m):
        entry_text = m.group(1)
    # extract the repo name from the GitHub link inside the entry
    names = re.findall(
                r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""",
                entry_text, re.I
    )
    if names and names[0] not in live_repos:
                removed.append(names[0])
                return ""          # drop it
    return entry_text      # keep it

cleaned_block = entry_pattern.sub(keep_entry, block)
# ───────────────────────────────────────────────────────────────────────────

# Re-derive existing after removal so we don't re-add what's still there
existing_after_clean = set(re.findall(
        r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""",
        cleaned_block, re.I
))

# Badge helpers
LANG_COLOR = {"Python":"3776AB","JavaScript":"F7DF1E","TypeScript":"3178C6",
                             "Java":"007396","Go":"00ADD8","C++":"00599C","Jupyter Notebook":"DA5B0B",
                             "HTML":"E34F26","CSS":"1572B6","Rust":"000000","Shell":"89E051"}
LANG_LOGO  = {"Python":"python","JavaScript":"javascript","TypeScript":"typescript",
                             "Java":"openjdk","Go":"go","Jupyter Notebook":"jupyter",
                             "HTML":"html5","CSS":"css3"}
EMOJIS = [
        (["fire","forest","wildfire"],"🔥"),
        (["cardiac","heart","ecg","arrhythmia"],"🫀"),
        (["portfolio","personal site","portfolio website"],"🌐"),
        (["java","ecommerce","e-commerce"],"☕"),
        (["chatbot","gemini","gpt","llm","multimodal"],"🤖"),
        (["house","price","regression"],"🏡"),
        (["face","facial","attendance"],"🧑‍💼"),
        (["aqi","air quality","delhi"],"🏙️"),
        (["gesture","hand"],"✋"),
        (["data","analytics","analysis"],"📊"),
        (["cloud","gcp","aws","azure"],"☁️"),
        (["lunar","moon","satellite","chandrayaan"],"🌙"),
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

new_entries, added = [], []
for repo in repos:
        if repo["name"] in existing_after_clean:
                    continue
                if not repo.get("description"):
                            continue
                        if repo["name"].lower() == username.lower():
                                    continue
                                if repo.get("fork", False) or repo.get("archived", False):
                                            continue

    name   = repo["name"]
    desc   = repo["description"].strip().rstrip(".")
    url    = repo["html_url"]
    lang   = repo.get("language")
    topics = repo.get("topics", [])[:4]
    emoji  = pick_emoji(name, desc)
    title  = name.replace("_", " ").replace("-", " ")

    badges = []
    if lang: badges.append(badge(lang))
            for t in topics: badges.append(topic_badge(t))
                    badge_line = " ".join(badges)

    entry = f"### {emoji} [{title}]({url})\n"
    if badge_line:
                entry += badge_line + "\n"
    entry += f"{desc}.---"
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

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

repos = [r for r in repos
         if r.get("description")
         and r["name"].lower() != username.lower()
         and not r.get("fork", False)
         and not r.get("archived", False)]

# Read README
with open("README.md", "r", encoding="utf-8") as f:
    readme = f.read()

START = "<!-- FEATURED-PROJECTS-START -->"
END   = "<!-- FEATURED-PROJECTS-END -->"
if START not in readme or END not in readme:
    print("Markers not found – nothing to do.")
    raise SystemExit(0)

si    = readme.index(START)
ei    = readme.index(END)
block = readme[si + len(START): ei]

# Find which repos are already in the block by URL
existing = set(re.findall(
            r"""https://github\.com/""" + re.escape(username) + r"""/([^/)\s"']+)""", block, re.I))

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
]

def pick_emoji(name, desc):
    s = (name + " " + desc).lower()
    for kws, em in EMOJIS:
        if any(k in s for k in kws): return em
    return "🚀"

def badge(lang):
    if not lang: return ""
    c = LANG_COLOR.get(lang,"555555")
    slug = lang.replace(" ","%20").replace("+","%2B")
    logo = LANG_LOGO.get(lang,"")
    lp = f"&logo={logo}&logoColor=white" if logo else ""
    return f"![{lang}](https://img.shields.io/badge/{slug}-{c}?style=flat-square{lp})"

def topic_badge(t):
    label = t.replace("-"," ").title()
    slug  = t.replace("-","%20")
    return f"![{label}](https://img.shields.io/badge/{slug}-0A66C2?style=flat-square)"

new_entries, added = [], []
for repo in repos:
    if repo["name"] in existing:
        continue
    name   = repo["name"]
    desc   = repo["description"].strip().rstrip(".")
    url    = repo["html_url"]
    lang   = repo.get("language") or ""
    topics = repo.get("topics",[])[:4]
    emoji  = pick_emoji(name, desc)
    title  = name.replace("_"," ").replace("-"," ")

    badges = []
    if lang: badges.append(badge(lang))
    for t in topics: badges.append(topic_badge(t))
    badge_line = " ".join(badges)

    entry = f"### {emoji} [{title}]({url})\n"
    if badge_line: entry += badge_line + "\n"
    entry += f"\n{desc}.\n\n---"
    new_entries.append(entry)
    added.append(name)

if not new_entries:
    print("No new repos to add – README unchanged.")
    raise SystemExit(0)

insert_text = "\n\n" + "\n\n".join(new_entries) + "\n\n"
new_readme  = readme[:ei] + insert_text + readme[ei:]

with open("README.md", "w", encoding="utf-8") as f:
    f.write(new_readme)

print(f"Added {len(added)} project(s): {', '.join(added)}")

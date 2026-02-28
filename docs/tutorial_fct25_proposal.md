# 🚀 From Research Idea to FCT Proposal — A Step-by-Step Guide

**How to use the FCT Proposal Engine to draft, review, and refine your FCT25 research proposal using AI**

---

## What this tool does for you

You have a research idea. This tool turns it into a structured, submission-ready
FCT25 proposal, then runs it through a panel of AI reviewers that behave like
real FCT referees, and revises your proposal until it is strong enough to submit.

The entire process works in three stages:

```
📝 Your Idea  ➜  🤖 AI Drafting  ➜  📋 AI Peer Review  ➜  ✨ Polished Proposal
   (YAML file)     (generates       (4 AI reviewers        (revised, scored,
                    all sections)     score & critique)       ready to use)
```

**Estimated time for your first run:** about 45 minutes (most of that is
filling in your research idea — the engine itself runs in 5–15 minutes).

**What you need before starting:** your terminal open, your API keys already
configured in the `.env` file, and an internet connection. This tutorial assumes
your local environment is fully set up and ready to go.

<details>
<summary>🧠 What are the "AI reviewers", exactly?</summary>

The engine includes a panel of four AI reviewers, each powered by a different
large language model and given a distinct personality and focus area:

| Reviewer | Focus | What they check hardest |
|----------|-------|------------------------|
| **Claude** (Anthropic) | Scientific rigour | Methodology, evidence, internal consistency |
| **GPT** (OpenAI) | Innovation & impact | Novelty, societal relevance, state of the art |
| **Gemini** (Google) | Feasibility | Budget realism, timeline, risk management |
| **LLaMA** (Meta) | Domain expertise | Field-specific standards, data practices, ethics |

They score your proposal against the same criteria FCT uses (Scientific Merit,
Team & PI track record, Feasibility & resources), give written feedback, and
then the engine revises your proposal based on their suggestions. This cycle
repeats 2–3 times, so each version of your proposal gets progressively stronger.

</details>

---

## 📥 Section 1 — Getting the Code from GitHub

GitHub is simply a website where code is stored and shared. You are going to
download a copy of the proposal engine to your computer using one command.

**Step 1.** Open your terminal and run:

```bash
git clone https://github.com/dpolonia/202602-fct-proposal-engine.git
```

**Step 2.** Move into the project folder:

```bash
cd 202602-fct-proposal-engine
```

**Step 3.** Verify everything is there:

```bash
ls
```

You should see something like this:

```
CLAUDE.md   Makefile    config.yaml  drafts/   output/   scripts/  tests/
Dockerfile  README.md   data/        docs/     src/      ...
```

If you see those files, you are ready to go.

<details>
<summary>🔄 What if I already downloaded it before?</summary>

If you cloned the repository previously and want to make sure you have the
latest version, navigate to your existing folder and pull the updates:

```bash
cd 202602-fct-proposal-engine
git pull origin main
```

This downloads any changes that were made since your last download.

</details>

<details>
<summary>❌ What if git clone gives an error?</summary>

**"git: command not found"** — Git is not installed. On Ubuntu/WSL, run:

```bash
sudo apt update && sudo apt install -y git
```

**"Permission denied"** — You may need to set up SSH keys for GitHub. The
simplest alternative is to download the code as a ZIP file: go to
`https://github.com/dpolonia/202602-fct-proposal-engine`, click the green
**Code** button, then click **Download ZIP**. Unzip it and open a terminal
inside the folder.

**"Repository not found"** — Double-check the URL. Make sure you typed it
exactly as shown above.

</details>

### ✅ Progress Check

- [ ] I cloned the repository successfully
- [ ] I am inside the `202602-fct-proposal-engine` folder

---

## 🗺️ Section 2 — A Quick Tour of the Project

You do not need to understand every file in this project. There are only **four
places** you will interact with directly. Think of the project like a kitchen:

```
202602-fct-proposal-engine/
│
├── 📝 drafts/            ← YOUR INGREDIENTS (your research idea goes here)
│   ├── example_idea.yaml     (a complete template you will copy)
│   └── my_idea.yaml          (your version — you will create this)
│
├── ⚙️ config.yaml         ← YOUR CONTROL PANEL (how the engine behaves)
│
├── 🔑 .env                ← YOUR API KEYS (already set up — don't touch)
│
├── 📦 output/             ← YOUR FINISHED DISHES (proposals appear here)
│
└── 🚫 Everything else     ← THE ENGINE (you don't need to open these)
    ├── src/                   (the code that does the work)
    ├── tests/                 (automated tests)
    ├── data/                  (templates and schemas)
    └── infra/                 (cloud deployment — ignore)
```

> **💡 Key insight:** You only edit files in `drafts/` and occasionally glance
> at `config.yaml`. The engine reads your draft, does all the heavy lifting, and
> puts the results in `output/`. That is the entire workflow.

<details>
<summary>🔍 For the curious — what is inside src/?</summary>

If you are interested in what happens under the hood:

| Folder | What it does |
|--------|-------------|
| `src/cli.py` | The command-line interface — the doorway you use to start the engine |
| `src/generators/` | The AI writing engine that produces each proposal section |
| `src/reviewers/` | The AI peer review panel that scores and critiques |
| `src/scrapers/` | Connects to Scopus to find relevant academic literature |
| `src/config/` | Reads your settings from `config.yaml` and `.env` |
| `src/utils/` | Helper code for talking to different AI providers |

You never need to modify any of these files.

</details>

### ✅ Progress Check

- [ ] I understand that `drafts/` is where my research idea goes
- [ ] I understand that `output/` is where results appear
- [ ] I know I do not need to touch anything inside `src/`

---

## 📝 Section 3 — Preparing Your Research Idea

This is the most important section of the tutorial. You are going to create a
file that describes your research idea, and the engine will use it to generate
a complete FCT25 proposal.

### Step 3.1 — Copy the template

Do not edit the original template. Make your own copy:

```bash
cp drafts/example_idea.yaml drafts/my_idea.yaml
```

### Step 3.2 — Open your file

Open your new file in a text editor. Choose whichever you are comfortable with:

```bash
# Option A: Simple terminal editor
nano drafts/my_idea.yaml

# Option B: Visual Studio Code (if installed)
code drafts/my_idea.yaml
```

### Step 3.3 — Fill it in, section by section

The file is organised into clearly labelled blocks. Below is a guide to each
one. Replace the example text with your own content — the engine will use
exactly what you write here as the starting point for your proposal.

---

#### 🏷️ 3.3.1 — Core Idea

```yaml
title: "Your Project Title in English"
title_pt: "O Título do Seu Projecto em Português"
acronym: "SHORT-NAME"
typology: "SR&TD"   # or "PEX"
```

> **🇵🇹 FCT25 Tip — SR&TD vs PEX:**
>
> - **SR&TD** (Scientific Research & Technological Development): up to
>   **€250,000** over **36 months**. For mature research with clear
>   methodology and expected outputs.
> - **PEX** (Exploratory Projects): up to **€60,000** over **18 months**.
>   For feasibility studies, early-stage ideas, or methodological exploration.
>
> Choose the one that matches your project's maturity and ambition.
> The engine enforces the budget and timeline limits automatically.

---

#### 🔬 3.3.2 — Research Framing

```yaml
research_topic: |
  Write 1-2 paragraphs describing your research problem, the gap in existing
  knowledge, and what your project proposes to do about it. Use the pipe
  character (|) to write multi-line text as shown here.

research_questions:
  - "RQ1: Your first research question?"
  - "RQ2: Your second research question?"
  - "RQ3: Your third research question (if applicable)?"

keywords_en:
  - "keyword one"
  - "keyword two"
  - "keyword three"

keywords_pt:
  - "palavra-chave um"
  - "palavra-chave dois"
  - "palavra-chave três"

scientific_domain: "Social Sciences"
scientific_area: "Economics and Business"
scientific_subarea: "Business and Management"
```

> **🇵🇹 FCT25 Tip — Evaluation Criterion A (Scientific Merit & Innovation):**
>
> The `research_topic` and `research_questions` directly feed into the sections
> that reviewers evaluate for Criterion A. Be specific about what gap you are
> addressing, why it matters, and what is novel about your approach.
> The more precise your input here, the stronger the generated proposal will be.

---

#### 👥 3.3.3 — Team

```yaml
pi:
  name: "Your Full Name"
  email: "your.email@university.pt"
  institution: "Your University"
  role: "pi"
  expertise: "Your areas of expertise, briefly"
  orcid: "0000-0001-XXXX-XXXX"

team_members:
  - name: "Colleague Name"
    email: "colleague@university.pt"
    institution: "Their University"
    role: "team_member"
    expertise: "Their expertise"

hirings_planned:
  - name: "Research Fellow (to hire)"
    institution: "Your University"
    role: "to_hire"
    expertise: "What skills this person should have"
```

You can add as many `team_members` and `hirings_planned` entries as you need.
Just follow the same indentation pattern — copy and paste an existing entry
and change the values.

---

#### 🏛️ 3.3.4 — Institutions

```yaml
principal_contractor: "Your University"
research_units:
  - "YOUR-RESEARCH-UNIT"
participating_institutions: []
collaborative_institutions:
  - "Partner University (if any)"
```

> **🇵🇹 FCT25 Tip:** The `research_units` field should contain the exact name
> of your FCT-recognised research unit (e.g., "GOVCOPP", "IEETA", "CICECO").
> This must match the unit name in the FCT database.

---

#### 📄 3.3.5 — PI Career Summary & Track Record

This section feeds directly into **Criterion B** (Team quality and track record).
Write about yourself in the third person or first person — the engine will
adapt the style.

```yaml
pi_career_summary: |
  Describe your academic career, highlighting: your current position,
  years of experience, main research line, key achievements.
  Mention any project coordination experience and funded projects.
  Include Scopus metrics if available (h-index, publications, citations).

key_publications:
  - "Author, A., Author, B. (2024). Title. Journal Name, vol(issue), pages. DOI"
  - "Author, A. (2023). Title. Conference Name. DOI"

funded_projects:
  - "PROJECT-NAME — Funding programme, Role (PI/Co-PI), Years, Budget"
  - "ANOTHER-PROJECT — Programme, Role, Years, Budget"
```

> **🇵🇹 FCT25 Tip — Criterion B (Team quality):**
>
> FCT reviewers weight the PI's track record heavily. Include your strongest
> publications (preferably 5–10, most-cited first), coordination roles in
> previous funded projects, and any international collaboration experience.
> This is your opportunity to demonstrate that your team can deliver.

---

#### 💰 3.3.6 — Budget & Methodology Notes

```yaml
budget_notes: |
  A brief description of how you plan to spend the money.
  E.g., "1 research fellow (12 months), travel for 2 conferences,
  cloud computing credits, open-access publication fees."

methodology_notes: |
  A brief description of your planned methodology.
  E.g., "Mixed-methods: Phase 1 literature review and framework
  development (M1-M6), Phase 2 data collection via surveys and
  interviews (M7-M12), Phase 3 analysis and validation (M13-M18)."
```

The engine uses these notes as guidance to generate the detailed methodology,
task plan, deliverables, and milestones. The more specific you are, the better
the output.

---

#### 🌍 3.3.7 — FCT-Specific Metadata

```yaml
sdg_alignment:
  - 3    # Good Health and Well-being
  - 9    # Industry, Innovation and Infrastructure

ethics_requirements: |
  Describe any ethical considerations: personal data, informed consent,
  vulnerable populations, animal experiments, etc.
  Write "No specific ethical concerns identified." if not applicable.
```

For **PEX projects only**, you also need:

```yaml
why_timely: |
  Explain why this exploratory research is timely and cannot wait.
  Reference recent policy changes, emerging technologies, or new
  datasets that make this the right moment for this investigation.
```

> **🇵🇹 FCT25 Tip — PEX "Why Timely":**
>
> This is a mandatory narrative for PEX proposals (Section 3 in the FCT form).
> Reviewers expect a clear argument for urgency. Reference specific dates,
> regulations, or developments — not vague statements like "AI is growing."

<details>
<summary>📐 YAML basics — what are those colons, dashes, and pipes?</summary>

YAML is a simple text format for structured data. Here are the only rules you
need to know:

**Colons (`:`)** separate a field name from its value:
```yaml
title: "My Project Title"
```

**Dashes (`-`)** create list items:
```yaml
keywords_en:
  - "first keyword"
  - "second keyword"
```

**Pipes (`|`)** let you write multi-line text:
```yaml
research_topic: |
  This is the first line of a long paragraph.
  This is the second line. It will all be treated
  as one continuous block of text.
```

**Indentation matters.** Use exactly 2 spaces (not tabs) for each level of
nesting. The template file already has the correct indentation — just replace
the text between the quotes.

**Quotes** around values are optional but recommended. Always use them if your
text contains colons, dashes, or special characters.

</details>

<details>
<summary>🐛 What if I get a YAML error when I run the engine?</summary>

The most common YAML mistakes and how to fix them:

**"could not find expected ':'"** — You probably have a colon inside your text
without quotes. Wrap the value in double quotes:
```yaml
# ❌ Wrong
title: AI-Driven Innovation: A Framework
# ✅ Right
title: "AI-Driven Innovation: A Framework"
```

**"found character that cannot start any token"** — You used a tab character
instead of spaces. Replace tabs with 2 spaces.

**"mapping values are not allowed here"** — Indentation is inconsistent.
Make sure every level uses exactly 2 spaces.

You can check your file before running the engine:

```bash
python3 -c "import yaml; yaml.safe_load(open('drafts/my_idea.yaml'))" && echo "✅ Valid YAML"
```

</details>

### ✅ Progress Check

- [ ] I copied `example_idea.yaml` to `my_idea.yaml`
- [ ] I filled in all the Core Idea fields (title, acronym, typology)
- [ ] I wrote my research topic and research questions
- [ ] I added my team information (PI + any team members)
- [ ] I wrote my PI career summary and listed key publications
- [ ] I added budget and methodology notes
- [ ] I saved the file

---

## ⚙️ Section 4 — Checking Your Settings

Your research idea (in `drafts/my_idea.yaml`) tells the engine **what** to
write about. The configuration file (`config.yaml`) tells the engine **how**
to do its work — which AI models to use, how many revision rounds to run,
and whether to search for relevant literature.

You usually do not need to change `config.yaml`, but it is worth verifying
three things before your first run.

**Step 1.** Check that the project typology matches your draft:

```bash
grep "typology" config.yaml
```

You should see something like:

```yaml
  typology: "SR&TD"
```

Make sure this matches what you wrote in your draft YAML. If your draft says
`typology: "PEX"`, this should also say `"PEX"`.

**Step 2.** Verify the pipeline settings:

```bash
grep -A 3 "pipeline:" config.yaml
```

The key values are:

```yaml
pipeline:
  iterations: 3          # How many generate→review→revise cycles
  stop_on_accept: true   # Stop early if reviewers are satisfied
```

Three iterations is a good default. The engine will stop sooner if the
reviewers accept the proposal before the third round.

**Step 3.** Check the literature search:

```bash
grep -A 2 "scopus:" config.yaml
```

```yaml
scopus:
  enabled: true          # Set to false if you want to skip this
  max_results: 100
```

If you have a Scopus API key in your `.env` file, leave this as `true` — the
engine will automatically find and cite relevant academic literature in your
proposal. If you do not have a Scopus key, set it to `false`.

**Step 4.** Run a quick verification:

```bash
fct-engine config --show
```

This prints all your resolved settings. Skim it to make sure nothing looks
wrong — in particular, check that your API keys show as "set" (never as the
actual key value).

<details>
<summary>🤖 How to change which AI models are used</summary>

The `config.yaml` file has a `llm:` section that controls which AI writes
each part of your proposal:

```yaml
llm:
  generator:   { provider: anthropic, model: claude-opus-4-6 }
  consensus:   { provider: anthropic, model: claude-opus-4-6 }
  revision:    { provider: anthropic, model: claude-opus-4-6 }
```

You can change the `provider` and `model` to any supported combination:

| Provider | Example models |
|----------|---------------|
| `anthropic` | `claude-opus-4-6`, `claude-sonnet-4-5-20250929` |
| `openai` | `gpt-5.2-2025-12-11` |
| `google` | `gemini-3.1-pro-preview`, `gemini-2.5-flash` |

Larger models (like Opus and GPT-5.2) produce higher-quality proposals but cost
more per run and take longer.

</details>

<details>
<summary>🔑 What if I do not have all four API keys?</summary>

You do not need all four. The engine gracefully skips any reviewer whose API
key is missing. At a minimum, you need **one** API key for the generator
(whichever provider is set under `llm.generator` in `config.yaml`).

For the best experience, we recommend at least two: one for the generator
(e.g., Anthropic) and one for a reviewer (e.g., OpenAI or Google). This gives
you both proposal writing and at least one independent review perspective.

To disable a reviewer explicitly, find its entry under `review_panel:` in
`config.yaml` and set `enabled: false`.

</details>

### ✅ Progress Check

- [ ] The typology in `config.yaml` matches my draft
- [ ] Pipeline iterations are set (I recommend 3)
- [ ] I ran `fct-engine config --show` and it looks correct

---

## 🚀 Section 5 — Running the Engine

This is the moment everything comes together. One command, and the engine will
generate, review, and revise your proposal.

### Step 5.1 — Run the pipeline

```bash
fct-engine pipeline -i drafts/my_idea.yaml
```

That is it. The engine will now:

1. **Read** your research idea from the YAML file
2. **Search** Scopus for relevant academic literature (if enabled)
3. **Generate** a complete proposal with all FCT-required sections
4. **Submit** it to the AI reviewer panel for scoring and feedback
5. **Revise** the proposal based on reviewer critiques
6. **Repeat** steps 4–5 for the configured number of iterations
7. **Save** everything to the `output/` folder

### Step 5.2 — What you will see on screen

The terminal will show a progress display as each stage completes. At the end,
you will see a summary table like this:

```
┌──────────────────────────────────┐
│ 🚀 Full Pipeline (3 iterations) │
├──────┬───────┬──────────┬───────┤
│ Iter │ Score │ Decision │  A    │
├──────┼───────┼──────────┼───────┤
│  1   │  6.2  │  revise  │  6.5  │
│  2   │  7.4  │  revise  │  7.8  │
│  3   │  8.1  │  accept  │  8.3  │
└──────┴───────┴──────────┴───────┘

✅ Output: output/20260228_143052
```

The scores range from 1 to 10. A score above 7.5 with an "accept" decision
means the AI reviewers consider the proposal competitive.

> **⏱️ Expected time:** 5–15 minutes, depending on how many iterations run
> and how fast the AI providers respond. The engine shows progress as it goes,
> so you will know it is working.

### Step 5.3 — Find your results

```bash
ls output/
```

You will see a timestamped folder (e.g., `20260228_143052`). Inside it:

```bash
ls output/20260228_143052/
```

```
final_proposal.json      ← The complete proposal (structured data)
proposal_summary.md      ← Human-readable summary (start here!)
char_report.json         ← Character counts vs FCT limits
v0_proposal.json         ← Version 0 (before any review)
v1_proposal.json         ← Version 1 (after first review)
v1_review.json           ← What the reviewers said about v0
v2_proposal.json         ← Version 2 (after second review)
v2_review.json           ← What the reviewers said about v1
...
```

**Start by reading `proposal_summary.md`** — it is the easiest way to see
what the engine produced:

```bash
cat output/20260228_143052/proposal_summary.md
```

Or, if you prefer a nicer reading experience, open it in VS Code:

```bash
code output/20260228_143052/proposal_summary.md
```

<details>
<summary>💥 What if it crashes mid-run?</summary>

Do not worry — the engine saves intermediate results as it goes. If it crashes
at iteration 2, you will still have `v0_proposal.json` and `v1_proposal.json`
in the output folder.

To resume, simply run the same command again:

```bash
fct-engine pipeline -i drafts/my_idea.yaml
```

The engine starts fresh each time (it does not resume from where it stopped),
but your previous output folder is preserved.

If the crash happens repeatedly, check:
- Your internet connection
- Your API key balance (some providers require pre-paid credits)
- The error message in the terminal — it usually tells you what went wrong

</details>

<details>
<summary>⚡ What if a reviewer is unavailable?</summary>

If one of the four AI reviewers cannot be reached (e.g., the API key is
missing, or the service is temporarily down), the engine simply **skips**
that reviewer and continues with the remaining ones. You will see a warning
message in the terminal, but the pipeline will not crash.

Your proposal will still be reviewed — just with fewer perspectives. You can
re-run later when the service is back to get the full panel review.

</details>

<details>
<summary>🔧 Running individual steps instead of the full pipeline</summary>

If you want more control, you can run each stage separately:

**Generate only** (no review):

```bash
fct-engine generate -i drafts/my_idea.yaml
```

**Review an existing proposal:**

```bash
fct-engine review -i output/20260228_143052/final_proposal.json
```

This is useful if you want to manually edit the proposal JSON between stages
or if you want to re-run the review with different settings.

</details>

> **⚠️ Important — API Costs:**
>
> Each full pipeline run (3 iterations, 4 reviewers) typically costs between
> **$5–15** in API fees, depending on which models you use. Larger models
> (Claude Opus, GPT-5.2) cost more but produce higher-quality output.
>
> If you are on a Claude Pro or Max subscription, Claude Code usage is included
> in your subscription. However, the pipeline's direct API calls (via the
> Python engine) are billed separately through your `.env` API keys.
>
> You can check your spending in each provider's dashboard:
> - Anthropic: https://console.anthropic.com
> - OpenAI: https://platform.openai.com/usage
> - Google AI Studio: https://aistudio.google.com

### ✅ Progress Check

- [ ] I ran `fct-engine pipeline -i drafts/my_idea.yaml` successfully
- [ ] The output folder was created with results inside it
- [ ] I read `proposal_summary.md` and it looks like a real proposal

---

## 📊 Section 6 — Reading and Using Your Results

Now that the engine has produced your proposal, here is how to understand and
use the output files.

### What is in the output folder

| File | What it contains | What to do with it |
|------|-----------------|-------------------|
| `final_proposal.json` | The complete structured proposal | This is the source of truth — all sections, tasks, deliverables, milestones |
| `proposal_summary.md` | Human-readable narrative summary | **Read this first** — copy sections into your FCT application form |
| `char_report.json` | Character counts vs FCT limits per section | Check that no section exceeds its limit |
| `v0_proposal.json` | Initial draft (before any review) | Compare with final to see how much it improved |
| `v1_review.json`, `v2_review.json` | Reviewer feedback for each iteration | Read the critiques — they highlight weaknesses |
| `v1_proposal.json`, `v2_proposal.json` | Revised versions after each review | Track the evolution of your proposal |

### Checking character limits

FCT imposes strict character limits on each section of the proposal. The engine
tracks these automatically. To see if any section is over the limit:

```bash
cat output/20260228_143052/char_report.json
```

You will see something like:

```json
{
  "state_of_art_objectives": { "chars": 18420, "limit": 20000, "status": "ok" },
  "research_plan_methods":   { "chars": 19850, "limit": 20000, "status": "ok" },
  "bibliography":            { "chars": 4200,  "limit": 5000,  "status": "ok" },
  "career_profile":          { "chars": 3800,  "limit": 4000,  "status": "warning" }
}
```

A status of `"ok"` means you are within the limit. A `"warning"` means you are
close. If any section says `"over"`, you will need to trim it before submitting.

### Understanding reviewer scores

Open any review file to see how the panel evaluated your proposal:

```bash
cat output/20260228_143052/v2_review.json
```

Each reviewer scores three criteria on a scale of 1–10:

| Criterion | FCT label | What it measures |
|-----------|-----------|-----------------|
| **A** | Scientific merit & innovation | Is the research question important? Is the approach novel and sound? |
| **B** | Team & PI track record | Can this team deliver? Does the PI have relevant experience? |
| **C** | Feasibility & resources | Is the timeline realistic? Is the budget justified? |

A **weighted score above 7.5** with an **"accept" decision** means the panel
considers your proposal competitive. Scores between 6.0 and 7.5 usually mean
"revise" — the idea is good but needs strengthening in specific areas.

### Using the feedback to improve

The most valuable part of the output is the **reviewer feedback**. Each review
file contains specific, section-by-section critiques. Read them carefully —
they tell you exactly what a referee would challenge.

To iterate:

1. Read the reviewer feedback in the latest `v*_review.json`
2. Update your `drafts/my_idea.yaml` based on their suggestions
3. Re-run the pipeline: `fct-engine pipeline -i drafts/my_idea.yaml`
4. Compare the new output with the previous version

Each run creates a new timestamped output folder, so you never lose previous
versions.

<details>
<summary>🔄 How to iterate manually — editing the draft and re-running</summary>

The most effective workflow is:

1. **Run the pipeline** with your initial draft
2. **Read the reviewer feedback** — focus on the lowest-scoring criterion
3. **Strengthen your draft YAML** — add more detail in the weak areas:
   - Low A score → improve `research_topic`, add more `research_questions`,
     sharpen the gap analysis
   - Low B score → expand `pi_career_summary`, add more `key_publications`
     and `funded_projects`
   - Low C score → add more detail to `methodology_notes` and `budget_notes`,
     consider adding team members
4. **Re-run the pipeline** with the updated draft
5. **Compare scores** between runs to see if they improved

Typically, 2–3 manual iterations produce a strong, submission-ready proposal.

</details>

### ✅ Progress Check

- [ ] I read `proposal_summary.md` and understand the proposal structure
- [ ] I checked the character count report — no sections are over the limit
- [ ] I read at least one review file and understand the feedback format

---

## 💾 Section 7 — Saving Your Work with Git

Version control means never losing a good draft. Think of it as "save points"
in a video game — you can always go back to an earlier version.

> **Warning — What gets saved to GitHub and what stays local:**
>
> Your personal draft YAML files (`drafts/my_idea.yaml`) and generated
> output (`output/`) are **automatically excluded** from Git. They stay
> on your computer only — your research ideas are never uploaded to GitHub.
>
> Git tracks only the engine code, configuration, and the example template.
> This is by design: your intellectual property remains private.

### The three commands you need

**Command 1 — Stage your changes** (tell Git which files to save):

```bash
git add config.yaml
```

**Command 2 — Commit** (save a snapshot with a description):

```bash
git commit -m "Updated my engine settings"
```

**Command 3 — Push** (upload to GitHub for safekeeping):

```bash
git push origin main
```

That is it. Your work is now safely stored on GitHub. Every time you make
meaningful changes to your settings, repeat these three commands with a new
message.

> **💡 Tip:** Write commit messages that describe what you changed. This makes
> it easy to find a specific version later. Good examples:
> - `"Added budget breakdown and team member details"`
> - `"Strengthened PI career summary with H2020 experience"`
> - `"Revised research questions after iteration 2 feedback"`

<details>
<summary>🔐 What if git push asks for a password?</summary>

GitHub no longer accepts plain passwords. You need to authenticate using one
of these methods:

**Option A — SSH key (recommended):** If you set up SSH during environment
configuration, it should just work. If not, GitHub has a guide:
https://docs.github.com/en/authentication/connecting-to-github-with-ssh

**Option B — Personal Access Token:** Go to GitHub → Settings → Developer
Settings → Personal Access Tokens → Generate New Token. Use the token as
your password when Git asks.

**Option C — GitHub CLI:** If you have `gh` installed, run `gh auth login`
and follow the prompts. After that, `git push` will work automatically.

</details>

<details>
<summary>📜 How to see your version history</summary>

To see all your saved snapshots:

```bash
git log --oneline
```

You will see something like:

```
a1b2c3d Improved methodology section after reviewer feedback
e4f5g6h First draft of my FCT25 proposal
```

Each line is a commit, with its unique identifier on the left and your message
on the right.

To see what changed in a specific commit:

```bash
git show a1b2c3d
```

To go back to an earlier version of your draft:

```bash
git checkout a1b2c3d -- drafts/my_idea.yaml
```

This restores your draft to how it looked at that commit, without affecting
anything else.

</details>

### ✅ Progress Check

- [ ] I committed my settings changes
- [ ] I pushed my changes to GitHub

---

## 🎯 Section 8 — Next Steps & Tips

Congratulations — you have generated your first AI-assisted FCT25 proposal.
Here are some ways to get even more out of the engine.

### Iterate on your proposal

The best proposals come from multiple rounds of refinement:

1. Read the reviewer feedback carefully
2. Strengthen the weakest areas in your draft YAML
3. Re-run the pipeline
4. Compare the new scores with the previous ones

Each run takes only 5–15 minutes, so you can easily do 3–4 rounds in an
afternoon.

### Work on multiple proposals

Simply create more YAML files in the `drafts/` folder:

```bash
cp drafts/example_idea.yaml drafts/project_alpha.yaml
cp drafts/example_idea.yaml drafts/project_beta.yaml
```

Each one can have a different typology, team, and research topic. Run them
independently:

```bash
fct-engine pipeline -i drafts/project_alpha.yaml
fct-engine pipeline -i drafts/project_beta.yaml
```

### Adjust the review intensity

If you want faster runs (fewer iterations):

```bash
fct-engine pipeline -i drafts/my_idea.yaml --iterations 1
```

If you want maximum polish (more iterations):

```bash
fct-engine pipeline -i drafts/my_idea.yaml --iterations 5
```

### Quick-reference card

| What you want to do | Command |
|---------------------|---------|
| Run the full pipeline | `fct-engine pipeline -i drafts/my_idea.yaml` |
| Generate without review | `fct-engine generate -i drafts/my_idea.yaml` |
| Check your settings | `fct-engine config --show` |
| Validate your YAML | `python3 -c "import yaml; yaml.safe_load(open('drafts/my_idea.yaml'))"` |
| Save your progress | `git add config.yaml && git commit -m "message" && git push` |
| Update the engine | `git pull origin main` |

### Where to find more help

- **`README.md`** — Technical reference for the full project
- **`docs/`** — Additional documentation including tutorials for Claude Code
  and Gemini CLI setup
- **`drafts/example_idea.yaml`** — The complete template with all available
  fields and explanatory comments

---

## 📋 Final Checklist — Your Complete Progress Tracker

Use this master checklist to make sure you have completed every step:

### Getting Started
- [ ] Cloned the repository from GitHub
- [ ] Navigated into the project folder

### Understanding the Project
- [ ] I know where `drafts/`, `config.yaml`, `.env`, and `output/` are
- [ ] I know I do not need to modify anything inside `src/`

### Preparing My Research Idea
- [ ] Copied `example_idea.yaml` to `my_idea.yaml`
- [ ] Filled in all Core Idea fields (title, acronym, typology)
- [ ] Wrote research topic and research questions
- [ ] Added team information
- [ ] Wrote PI career summary and listed key publications
- [ ] Added budget and methodology notes
- [ ] Saved the file

### Configuring the Engine
- [ ] Verified typology matches between `config.yaml` and my draft
- [ ] Ran `fct-engine config --show` to verify settings

### Running the Pipeline
- [ ] Ran `fct-engine pipeline -i drafts/my_idea.yaml` successfully
- [ ] Output folder was created with results

### Reviewing Results
- [ ] Read `proposal_summary.md`
- [ ] Checked character count report
- [ ] Read reviewer feedback

### Saving My Work
- [ ] Committed my settings changes with Git
- [ ] Pushed to GitHub

### 🎉 You did it!

Your AI-assisted FCT25 proposal is ready for refinement and eventual
submission. Remember: the generated proposal is a **strong starting point**,
not a final submission. Always review it carefully, add your personal insights,
and ensure it accurately represents your research vision before submitting to
FCT.

> **Good luck with your FCT25 application! 🇵🇹🔬**

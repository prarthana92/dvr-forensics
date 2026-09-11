# TraceX

**Unified forensic recovery and analysis for multi-vendor DVR/NVR surveillance evidence.**

A multi-vendor DVR/NVR forensic analysis tool for standardized acquisition, recovery, and analysis of surveillance evidence. Starting with Hikvision and Dahua support.

## Project Structure

DVR/
├── acquisition/ # disk imaging, hashing, evidence backup (evidence integrity)
├── parsers/ # vendor-specific file system/format parsers
├── db/ # MySQL schema + connection layer
├── frontend/ # Flask web dashboard (login, evidence view, verification)
├── data/ # test files — never commit real evidence here


## Setup Instructions (do this once)

1. **Install Python**: Go to python.org/downloads, download, and during install make sure to check "Add python.exe to PATH".
2. **Install Git**: Download from git-scm.com if you don't have it.
3. **Install VS Code Python extension**: Open VS Code → Extensions icon → search "Python" → install the Microsoft one.
4. **Install MySQL**: Go to dev.mysql.com/downloads/installer, choose "Developer Default", remember your root password.
5. **Set your Git identity** (in a terminal):

git config --global user.name "Your Name"
git config --global user.email "your-github-email@example.com"

6. **Clone this repo** (don't use `git init`, the project already exists):

git clone https://github.com/prarthana92/tracex.git

7. **Install Python dependencies**:

pip install flask mysql-connector-python


## How We Work Together

- `main` branch is always the working, trusted version — nobody edits it directly.
- Before starting new work: `git checkout main` then `git pull` to get the latest.
- Create your own branch for whatever you're working on:

git checkout -b your-feature-name

- Commit and push your branch (not main):

git add .
git commit -m "describe what you did"
git push -u origin your-feature-name

- Open a Pull Request on GitHub.com to merge your branch into `main` once it works.

## Module Ownership

| Module | Owner | Status |
|---|---|---|
| Acquisition (hashing, evidence backup) | Working prototype |
| Database (MySQL schema, logging)| Working prototype |
| Frontend (login, dashboard, evidence, verification)| Working prototype |
| Hikvision parser |  Not started |
| Dahua parser + deleted-clip recovery |  Not started |
| ML analytics (face/object/motion detection) | Not started |

## Running the app


# Réorganisation en monorepo djona_public/{public,vendor,admin} Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (NOT subagent-driven-development — this plan is a sequence of filesystem/git operations across two repositories that must be executed by one operator holding continuous context, not parallelizable independent coding tasks). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the three currently-separate Djona codebases (`djona_public` at
`C:\Users\HP\Documents\Github\djona_public`, `djona_back_office/admin`, and
`djona_back_office/vendor`) into a single monorepo at `djona_public`, reorganized into
`djona_public/{public,vendor,admin}`, with zero functional regression.

**Architecture:** Each of the three Django projects keeps its own internal structure
completely intact (own `manage.py`, own `config`/`core` settings package, own app
packages) — only the *parent directory* each project sits in changes. Since Django
resolves module paths relative to wherever `manage.py` is invoked from, no Python import
or settings module path needs to change. Only files containing filesystem-absolute paths
(deployment scripts, the `media_cdn/annonces` directory junction) need updating.

**Tech Stack:** Windows filesystem operations (PowerShell `robocopy`, `mklink /J`), git
(within each repo separately — no cross-repo history merge), Django/`python-decouple`
for the credential fix.

**Spec:** `docs/superpowers/specs/2026-08-29-reorganisation-monorepo-djona_public-design.md`

---

**Before any step in this plan:** confirm the peer Claude session `djona-public-83` has
committed its in-progress work in `djona_public` (Task 1 does this explicitly — do not
skip ahead).

All paths below are absolute. `djona_back_office` = `C:\Users\HP\Documents\Github\djona_back_office`
(this repo). `djona_public` = `C:\Users\HP\Documents\Github\djona_public` (separate,
pre-existing repo).

## Task 1: Confirm clean starting state

- [ ] **Step 1: Confirm `djona-public-83` has committed**

Message the peer session (or check directly) that `djona_public`'s working tree is
clean. Then verify yourself:

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git status --short
```

Expected: no output (clean working tree). **Do not proceed past this step if there is
any output** — stop and re-confirm with the peer session / user instead of working
around uncommitted changes.

- [ ] **Step 2: Snapshot both repos' current commit for rollback reference**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git log --oneline -1
cd "/c/Users/HP/Documents/Github/djona_back_office" && git log --oneline -1
```

Note both commit hashes in your working notes (not committed anywhere) — if anything
goes wrong later, `djona_public` can be reset to the first hash with `git reset --hard`
(only if truly needed and confirmed with the user — see the safety rules already in
force for this session).

---

## Task 2: Move djona_public's existing content into `public/`

**Files:** everything currently at `djona_public/` root except `.git/`.

- [ ] **Step 1: Create the `public/` directory**

```bash
mkdir -p "/c/Users/HP/Documents/Github/djona_public/public"
```

- [ ] **Step 2: Replace the root `.gitignore` with the monorepo-generic one**

Copy `djona_back_office`'s root `.gitignore` (already proven to work for a multi-project
layout — its patterns are not anchored to the repo root, so they apply correctly no
matter which subfolder a file lives in) over `djona_public`'s current root `.gitignore`.

The CURRENT `djona_public/.gitignore` (with its Django-specific, root-anchored
`/media_cdn/`, `/static_cdn/`, `/static/css/output.css` entries) does not get deleted —
it moves into `public/.gitignore` in Step 3 below, where those same root-anchored
patterns become correct again (anchored to `public/`, which is exactly what they should
cover).

```bash
cp "/c/Users/HP/Documents/Github/djona_back_office/.gitignore" "/c/Users/HP/Documents/Github/djona_public/.gitignore.new"
```

(Named `.gitignore.new` for now — swapped into place in Step 4, after the old one has
already been moved into `public/` in Step 3, to avoid two files racing for the same
name.)

- [ ] **Step 3: `git mv` every git-tracked root item into `public/`**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git mv .gitignore .gitattributes AGENTS.md ARCHITECTURE.md BACK_OFFICE.md TACHES_A_FAIRE.md TACHES_EN_COURS.md TACHES_REALISEES.md _mockups apps config deploy images manage.py package-lock.json package.json requirements.txt static tailwind.config.js templates public/
```

Expected: `git mv` reports each rename, no errors. Verify:

```bash
git status --short | head -30
```

Expected: every moved item shows as `R  <old> -> public/<old>` (renamed, staged).

- [ ] **Step 4: Swap in the new root `.gitignore`**

```bash
mv "/c/Users/HP/Documents/Github/djona_public/.gitignore.new" "/c/Users/HP/Documents/Github/djona_public/.gitignore"
cd "/c/Users/HP/Documents/Github/djona_public" && git add .gitignore
```

- [ ] **Step 5: Move the untracked root items (not handled by `git mv`)**

`.env`, `db.sqlite3`, `media_cdn/`, and `static_cdn/` are gitignored (untracked — verified
via `git ls-files static_cdn/` and `git ls-files media_cdn/`, both return 0 tracked
files) — `git mv` does not touch them, use a plain move:

```bash
cd "/c/Users/HP/Documents/Github/djona_public"
mv .env db.sqlite3 media_cdn static_cdn public/
```

- [ ] **Step 6: Delete `node_modules/` and `.venv/` (not copied forward, per plan decision)**

```bash
cd "/c/Users/HP/Documents/Github/djona_public"
rm -rf node_modules .venv
```

- [ ] **Step 7: Verify the move**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && ls
```

Expected: only `.git`, `.gitattributes` (wait — this was moved; if still present here,
something went wrong), `.gitignore`, `public/` remain at root. Re-check with:

```bash
ls -la "/c/Users/HP/Documents/Github/djona_public"
```

Expected exactly: `.git/`, `.gitignore`, `public/` (and nothing else, besides `.` and
`..`).

```bash
ls "/c/Users/HP/Documents/Github/djona_public/public"
```

Expected: `.env`, `.gitattributes`, `AGENTS.md`, `ARCHITECTURE.md`, `BACK_OFFICE.md`,
`TACHES_A_FAIRE.md`, `TACHES_EN_COURS.md`, `TACHES_REALISEES.md`, `_mockups`, `apps`,
`config`, `db.sqlite3`, `deploy`, `images`, `manage.py`, `media_cdn`, `package-lock.json`,
`package.json`, `requirements.txt`, `static`, `static_cdn`, `tailwind.config.js`,
`templates`.

- [ ] **Step 8: Commit**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git commit -m "$(cat <<'EOF'
refactor: déplace le contenu existant dans public/ (préparation monorepo)

Réorganisation en monorepo : ce dépôt va accueillir 3 projets Django
(public/, vendor/, admin/). Le contenu actuel de djona_public devient
public/, sans aucun changement de code — seuls .gitignore (racine)
et .env/db.sqlite3/media_cdn (non versionnés) sont déplacés séparément
du git mv puisqu'ils ne sont pas suivis par git.
EOF
)"
```

---

## Task 3: Remediate the Aiven credentials in `public/config/settings/dev.py`

**Files:**
- Modify: `djona_public/public/config/settings/dev.py`
- Modify: `djona_public/public/.env` (untracked, not part of the commit)
- Create: `djona_public/public/.env.example`

- [ ] **Step 1: Read the current hardcoded values**

The current `dev.py` (already read during design) hardcodes:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'defaultdb',
        'USER': 'avnadmin',
        'PASSWORD': '<REDACTED — voir gestionnaire de secrets, ce service Aiven a été abandonné>',
        'HOST': '<REDACTED>.aivencloud.com',
        'PORT': '<REDACTED>',
    }
}
```

- [ ] **Step 2: Replace the hardcoded `DATABASES` block with `config()` calls**

In `djona_public/public/config/settings/dev.py`, replace:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'defaultdb',
        'USER': 'avnadmin',
        'PASSWORD': '<REDACTED — voir gestionnaire de secrets, ce service Aiven a été abandonné>',
        'HOST': '<REDACTED>.aivencloud.com',
        'PORT': '<REDACTED>',
    }
}
```

with:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('MYSQL_DB'),
        'USER': config('MYSQL_USER'),
        'PASSWORD': config('MYSQL_PASSWORD'),
        'HOST': config('MYSQL_HOST'),
        'PORT': config('MYSQL_PORT'),
    }
}
```

(`from decouple import config` is already imported at the top of this file — no new
import needed.)

- [ ] **Step 3: Update `public/.env` with the real (previously-hardcoded) values**

`djona_public/public/.env` already exists but currently has stale local-MySQL
placeholder values that `dev.py` was bypassing entirely. Replace its `MYSQL_*` lines so
runtime behavior stays identical to before this change (still pointing at the same Aiven
database):

Replace:
```
MYSQL_DB=djona_db
MYSQL_USER=root
MYSQL_PASSWORD=1234567890
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
```

with:
```
MYSQL_DB=defaultdb
MYSQL_USER=avnadmin
MYSQL_PASSWORD=<REDACTED — service Aiven abandonné, voir historique du projet>
MYSQL_HOST=<REDACTED>.aivencloud.com
MYSQL_PORT=<REDACTED>
```

- [ ] **Step 4: Create `public/.env.example`**

Create `djona_public/public/.env.example` (safe to commit — no real values):

```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=*

# MySQL (développement et production)
MYSQL_DB=
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_HOST=
MYSQL_PORT=3306
```

- [ ] **Step 5: Verify no real credentials remain in tracked files**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && grep -rn "avnadmin\|aivencloud" public/config/ public/.env.example
```

Expected: **no output** (the real password/host only exist in `public/.env`, which is
gitignored).

```bash
grep -n "^\.env$\|^\.env\b" "/c/Users/HP/Documents/Github/djona_public/.gitignore" "/c/Users/HP/Documents/Github/djona_public/public/.gitignore"
```

Expected: at least one match confirming `.env` is ignored somewhere in the chain (the
root `.gitignore` copied in Task 2 Step 2 already has a generic `.env` entry under
"Environments" — confirm it's there).

- [ ] **Step 6: Commit**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git add public/config/settings/dev.py public/.env.example
git commit -m "$(cat <<'EOF'
fix(public): sort les identifiants MySQL Aiven de dev.py vers .env

dev.py codait en dur des identifiants MySQL Aiven en clair. Remplacés
par des appels config() (python-decouple, déjà utilisé pour
DEBUG/ALLOWED_HOSTS dans ce même fichier). Comportement runtime
inchangé — .env (non versionné) garde les mêmes valeurs.
EOF
)"
```

---

## Task 4: Update deployment configs for the new `public/` path

**Files:**
- Modify: `djona_public/public/deploy/deploy.sh`
- Modify: `djona_public/public/deploy/gunicorn/djona.service`
- Modify: `djona_public/public/deploy/nginx/djona.tech.conf`

- [ ] **Step 1: Update `deploy.sh`**

In `djona_public/public/deploy/deploy.sh`, replace:

```bash
PROJECT_DIR="/var/www/project/djona_public"
```

with:

```bash
PROJECT_DIR="/var/www/project/djona_public/public"
```

- [ ] **Step 2: Update `djona.service`**

In `djona_public/public/deploy/gunicorn/djona.service`, replace:

```
WorkingDirectory=/var/www/project/djona_public
ExecStart=/var/www/project/djona_public/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8006 config.wsgi:application
```

with:

```
WorkingDirectory=/var/www/project/djona_public/public
ExecStart=/var/www/project/djona_public/public/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8006 config.wsgi:application
```

- [ ] **Step 3: Update `djona.tech.conf`**

In `djona_public/public/deploy/nginx/djona.tech.conf`, replace:

```
location /static/ {

alias /var/www/project/djona_public/static_cdn/;

}



location /media/ {

alias /var/www/project/djona_public/media_cdn/;

}
```

with:

```
location /static/ {

alias /var/www/project/djona_public/public/static_cdn/;

}



location /media/ {

alias /var/www/project/djona_public/public/media_cdn/;

}
```

- [ ] **Step 4: Verify no old bare path remains**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && grep -rn "djona_public\"" public/deploy/ ; grep -rn "djona_public/venv\|djona_public/static_cdn\|djona_public/media_cdn" public/deploy/
```

Expected: no output (every occurrence now has `/public/` in the path).

- [ ] **Step 5: Commit**

```bash
git add public/deploy/deploy.sh public/deploy/gunicorn/djona.service public/deploy/nginx/djona.tech.conf
git commit -m "$(cat <<'EOF'
fix(public): met à jour les chemins de déploiement pour public/

PROJECT_DIR, WorkingDirectory, ExecStart et les alias nginx pointaient
directement à la racine de djona_public — mis à jour vers
djona_public/public suite à la réorganisation en monorepo.
EOF
)"
```

---

## Task 5: Copy `vendor/` into `djona_public/vendor/`

**Files:** all of `djona_back_office/vendor/` (source), new tree at
`djona_public/vendor/` (destination).

- [ ] **Step 1: Copy with robocopy, excluding non-portable/regenerable directories**

```powershell
robocopy "C:\Users\HP\Documents\Github\djona_back_office\vendor" "C:\Users\HP\Documents\Github\djona_public\vendor" /E /XD venv __pycache__ /NFL /NDL
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
```

(`/E` copies all subdirectories including empty ones; `/XD venv __pycache__` excludes
any directory named `venv` or `__pycache__` anywhere in the tree — vendor has no
`node_modules`. Robocopy's exit codes 0-7 all mean success with informational detail,
not failure — the `if` line normalizes this so the tool doesn't misreport failure.)

- [ ] **Step 2: Verify the copy**

```bash
diff -rq --exclude=venv --exclude=__pycache__ "/c/Users/HP/Documents/Github/djona_back_office/vendor" "/c/Users/HP/Documents/Github/djona_public/vendor"
```

Expected: no output (identical trees, modulo the excluded directories).

- [ ] **Step 3: Commit**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git add vendor
git commit -m "$(cat <<'EOF'
feat(vendor): ajoute le projet vendor au monorepo

Copie intacte de djona_back_office/vendor/ — aucun changement de code,
aucun historique git préservé (décision explicite : copie simple).
EOF
)"
```

---

## Task 6: Copy `admin/` into `djona_public/admin/` (with the media_cdn junction handled correctly)

**Files:** all of `djona_back_office/admin/` (source), new tree at `djona_public/admin/`
(destination).

- [ ] **Step 1: Copy with robocopy, excluding `venv`, `__pycache__`, and the
  `media_cdn/annonces` junction**

The `annonces` subfolder under `admin/core/src/media_cdn/` is a directory **junction**
(created in an earlier session) pointing at `vendor/core/src/media_cdn/annonces` — it
must NOT be copied as-is (its target path won't exist once `vendor/` has moved); it gets
recreated fresh in Step 3 below, after Task 5 has already put `vendor/` in its new home.

```powershell
robocopy "C:\Users\HP\Documents\Github\djona_back_office\admin" "C:\Users\HP\Documents\Github\djona_public\admin" /E /XD venv __pycache__ "C:\Users\HP\Documents\Github\djona_back_office\admin\core\src\media_cdn\annonces" /NFL /NDL
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
```

- [ ] **Step 2: Verify the copy (excluding the known-excluded paths)**

```bash
diff -rq --exclude=venv --exclude=__pycache__ --exclude=annonces "/c/Users/HP/Documents/Github/djona_back_office/admin" "/c/Users/HP/Documents/Github/djona_public/admin"
```

Expected: no output.

```bash
ls "/c/Users/HP/Documents/Github/djona_public/admin/core/src/media_cdn/"
```

Expected: `avatars` present, `annonces` absent (not yet recreated).

- [ ] **Step 3: Recreate the `media_cdn/annonces` junction, now pointing at the new
  `vendor/` location**

```powershell
cmd /c mklink /J "C:\Users\HP\Documents\Github\djona_public\admin\core\src\media_cdn\annonces" "C:\Users\HP\Documents\Github\djona_public\vendor\core\src\media_cdn\annonces"
```

Verify:
```bash
ls "/c/Users/HP/Documents/Github/djona_public/admin/core/src/media_cdn/annonces/2026/08/"
```
Expected: the same `.jpeg` files seen previously through the old junction.

- [ ] **Step 4: Verify the settings.py comment already documents the correct path**

The comment above `MEDIA_ROOT` in `djona_back_office/admin/core/src/core/settings.py`
was corrected in a prior session (`git log` shows commit `779a54f`, fixing an off-by-one:
it previously said `..\..\..\..\vendor\...`, 4 levels, which resolves one directory too
high). The corrected version says `..\..\..\vendor\...` (3 levels) — and since
`djona_public/admin/core/src/` sits at the exact same relative depth from its sibling
`vendor/` as `djona_back_office/admin/core/src/` did (`src`→`core`→`admin`→up into the
repo root→down into `vendor/core/src/media_cdn/annonces`, 3 levels either way), this
comment needs **no further edit** after the robocopy in Step 1 — it already ships
correct. Just confirm:

```bash
grep -n "mklink" "/c/Users/HP/Documents/Github/djona_public/admin/core/src/core/settings.py"
```

Expected: `mklink /J media_cdn\annonces ..\..\..\vendor\core\src\media_cdn\annonces` (3
levels, matching Step 3's actual junction target).

- [ ] **Step 5: Commit**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git add admin
git commit -m "$(cat <<'EOF'
feat(admin): ajoute le projet admin au monorepo

Copie intacte de djona_back_office/admin/ — aucun changement de code
fonctionnel, aucun historique git préservé (décision explicite : copie
simple). La jonction media_cdn/annonces -> vendor/core/src/media_cdn/annonces
est recréée pour pointer vers le nouvel emplacement de vendor/, et le
commentaire de documentation dans settings.py mis à jour en conséquence.
EOF
)"
```

---

## Task 7: Move session docs into `admin/docs/` and `admin/.superpowers/`

**Files:**
- `djona_back_office/docs/superpowers/{plans,specs}/*` → merge into
  `djona_public/admin/docs/superpowers/{plans,specs}/` (which already has one older
  plan+spec pair from before this repo's `admin`/`vendor` split — no filename collision).
- `djona_back_office/.superpowers/` → `djona_public/admin/.superpowers/` (new — `admin/`
  has no `.superpowers/` yet).

- [ ] **Step 1: Copy the docs**

```powershell
robocopy "C:\Users\HP\Documents\Github\djona_back_office\docs\superpowers\plans" "C:\Users\HP\Documents\Github\djona_public\admin\docs\superpowers\plans" /E /NFL /NDL
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
robocopy "C:\Users\HP\Documents\Github\djona_back_office\docs\superpowers\specs" "C:\Users\HP\Documents\Github\djona_public\admin\docs\superpowers\specs" /E /NFL /NDL
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
```

- [ ] **Step 2: Copy `.superpowers/`**

```powershell
robocopy "C:\Users\HP\Documents\Github\djona_back_office\.superpowers" "C:\Users\HP\Documents\Github\djona_public\admin\.superpowers" /E /NFL /NDL
if ($LASTEXITCODE -lt 8) { $global:LASTEXITCODE = 0 }
```

- [ ] **Step 3: Verify**

```bash
ls "/c/Users/HP/Documents/Github/djona_public/admin/docs/superpowers/plans/" | grep "2026-08-2[7-9]"
ls "/c/Users/HP/Documents/Github/djona_public/admin/.superpowers/"
```

Expected: the plan files created during this and earlier sessions are present in both
locations.

- [ ] **Step 4: Commit**

```bash
cd "/c/Users/HP/Documents/Github/djona_public" && git add admin/docs admin/.superpowers
git commit -m "docs(admin): ajoute l'historique de planification de session (docs/, .superpowers/)"
```

---

## Task 8: Rebuild environments and verify nothing broke

- [ ] **Step 1: Rebuild `public/`'s Python + Node environments**

```bash
cd "/c/Users/HP/Documents/Github/djona_public/public" && python -m venv venv
./venv/Scripts/python.exe -m pip install --upgrade pip -q
./venv/Scripts/python.exe -m pip install -r requirements.txt -q
npm install
```

- [ ] **Step 2: `manage.py check` for `public/`**

```bash
cd "/c/Users/HP/Documents/Github/djona_public/public" && ./venv/Scripts/python.exe manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Rebuild `vendor/`'s Python environment and verify**

```bash
cd "/c/Users/HP/Documents/Github/djona_public/vendor/core" && python -m venv venv
./venv/Scripts/python.exe -m pip install --upgrade pip -q
./venv/Scripts/python.exe -m pip install -r requirements.txt -q
cd src && ../venv/Scripts/python.exe manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Rebuild `admin/`'s Python environment and verify (including tests)**

```bash
cd "/c/Users/HP/Documents/Github/djona_public/admin/core" && python -m venv venv
./venv/Scripts/python.exe -m pip install --upgrade pip -q
./venv/Scripts/python.exe -m pip install -r requirements.txt -q
```

Copy the (untracked, gitignored) `.env` forward — it was excluded from the robocopy? No
— `.env` was NOT in any `/XD` exclusion list in Task 6, so it should already be present
at `djona_public/admin/core/.env` (robocopy copies all files by default, including
gitignored ones, since it works at the filesystem level, not through git). Confirm:

```bash
ls "/c/Users/HP/Documents/Github/djona_public/admin/core/.env"
```

Expected: file exists (copied). If missing, copy it manually from
`djona_back_office/admin/core/.env` before proceeding.

```bash
cd "/c/Users/HP/Documents/Github/djona_public/admin/core/src" && ../venv/Scripts/python.exe manage.py check
../venv/Scripts/python.exe manage.py test --keepdb -v 2
```

Expected: `System check identified no issues (0 silenced).` and the full test suite
(56 tests as of the last run in `djona_back_office`) passes `OK`.

- [ ] **Step 5: Smoke-test `public/` actually serves a page**

```bash
cd "/c/Users/HP/Documents/Github/djona_public/public" && ./venv/Scripts/python.exe manage.py runserver 127.0.0.1:8020 &
sleep 2
curl -s -o /dev/null -w "GET / -> %{http_code}\n" http://127.0.0.1:8020/
```

Expected: `200`. Stop the server afterward (find its PID via `netstat`/`taskkill`, same
pattern used throughout this session).

- [ ] **Step 6: Report final state to the user**

Summarize: all 3 projects verified working from their new locations inside
`djona_public`; `djona_back_office` untouched and still present locally as a fallback
(not deleted per the earlier decision).

---

## Out of scope (explicitly, per the design doc)

- Preserving `admin`/`vendor`'s git history in the new `djona_public` repo.
- Deleting or archiving `djona_back_office`.
- Reconciling the separate `djona_vendor` directory (unrelated to this task).

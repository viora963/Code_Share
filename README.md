# CodeShare

![C](https://img.shields.io/badge/backend-Python%20%2F%20Flask-3776AB)
![Build](https://img.shields.io/badge/build-passing-brightgreen)

A GitHub-style code-sharing platform for students, built with Flask and MySQL/MariaDB. Users can create projects, upload files, tag and comment on each other's work, follow other users, and manage project membership with owner/admin/member roles.

## Features

- **Auth** — signup/login with hashed passwords (Werkzeug), session-based auth
- **Projects** — create public or private projects with one or more languages, edit metadata, delete
- **Files** — upload, download, and delete project files (type-restricted, 40MB max)
- **Membership & roles** — owner / admin / member roles per project, add/remove members, transfer ownership (role sync is handled by MySQL triggers, not application code)
- **Social** — follow/unfollow users, star (like) projects, comment on projects
- **Tags & search** — tag projects (choice-based or free text), search by title or `#tag`
- **Activity log** — per-project and per-user activity feed

## Tech stack

- **Backend:** Python 3, Flask
- **Database:** MySQL 8+ / MariaDB 10.11+ (InnoDB, with triggers and generated columns for case-insensitive uniqueness)
- **Frontend:** server-rendered Jinja2 templates, vanilla CSS/JS

## Getting started

### 1. Prerequisites

- Python 3.10+
- MySQL 8+ or MariaDB 10.11+

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and fill in your database credentials:

```bash
cp .env.example .env
```

```env
SECRET_KEY=change-me
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your-password-here
DB_NAME=code_share
```

**Never commit a real password as the default value in `config.py` or `.env`.**

### 4. Create the database

`schema.sql` creates its own `code_share` database and (re)builds all tables, so just run:

```bash
mysql -u root -p < schema.sql
```

### 5. Run

```bash
python app.py
```

The app will be available at `http://127.0.0.1:5000`.

## Project structure

```
app.py                 # Flask app factory + route registration
config.py              # Config from environment (.env)
db.py                  # MySQL connection handling (one connection per request via flask.g)
utils.py               # Auth helpers, upload handling, activity logging
routes/
  auth.py              # login / signup / logout
  dashboard.py         # dashboard feed
  profile.py           # profile, follow/unfollow, user projects/stars
  project.py           # project CRUD, files, members, tags, ownership transfer
schema.sql             # Full MySQL/MariaDB schema, triggers, and seed permissions
templates/             # Jinja2 templates
static/                # CSS/JS/images
uploads/               # Uploaded project files (created at runtime)
```

## Notes on the data model

- Usernames, emails, tag names, and languages are stored alongside a `*_norm` generated column (`LOWER(TRIM(...))`) so uniqueness checks are case/whitespace-insensitive without extra application logic.
- `project_members` role sync (owner/admin/member) is enforced entirely by triggers: creating a project auto-inserts the owner as a member, and transferring ownership (`UPDATE projects SET owner_id=...`) automatically demotes the old owner to admin and promotes the new one — the application code only ever updates `projects.owner_id`.
- A trigger blocks deleting the owner's own membership row directly; ownership must be transferred first.

## Known limitations

- No CSRF protection on state-changing routes (follow/unfollow, delete, transfer ownership, etc.) — acceptable for a coursework/local project, but should be added (e.g. Flask-WTF) before any public deployment.
- `templates/source_browser.html` and `templates/source_view.html` reference routes (`source_browser`, `source_view`, `source_download`) that don't exist in `routes/project.py` — this is an unfinished/orphaned feature and is currently unreachable from the rest of the app.

## Bug fixes in this pass

1. **Hardcoded production DB password removed** from `config.py` — it was sitting in source as the fallback default for `DB_PASSWORD`. If you're reusing this repo, **rotate that password** if it was ever pushed publicly.
2. **`project_languages` schema bug** — its primary key was declared on a `GENERATED ALWAYS AS (...) STORED` column, which MariaDB 10.11 rejects (`ERROR 1903`) and MySQL discourages. Fixed by keying the primary key off the raw `language` column and enforcing case-insensitive uniqueness with a separate `UNIQUE` constraint on the normalized column instead.
3. **Dead code removed** from `add_project_tags()` in `routes/project.py` — an unreachable block after the function's `return` statement referenced an undefined `tags` variable, left over from a refactor.
4. **Missing `requirements.txt`** added.

All of the above were verified against a live MariaDB 10.11 instance with an end-to-end test covering signup, project creation (public and private), file upload/download/delete, private-project access control, member add/remove, and ownership transfer (including the owner→admin / member→owner role-sync triggers) — all passing.

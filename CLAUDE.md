# CLAUDE.md

Guidance for working in this repository.

## What this is

`getex` is a **single-file Python 3 terminal text editor** (modal, Vim-style) built
on the standard-library `curses` module. The entire program lives in one executable
script: **`getex`** (no extension, has a `#!/usr/bin/env python3` shebang). There are
no dependencies beyond the Python standard library, no build step, and no package
layout — editing the `getex` file *is* editing the application.

The UI and all user-facing strings are in **Brazilian Portuguese**. Keep new strings,
comments, and help text in Portuguese to match the existing style.

## Running

```bash
./getex                # open a new document in the editor
./getex "meu titulo"   # new document with a title
./getex get all        # open the file browser (navegador de arquivos)
./getex --help         # help screen
```

On first run it prompts for config (folder name, AI provider, API key) and writes
`~/.getex_config` (JSON). Documents are saved as `.txt` under
`~/Desktop/<folder_name>/` (default `GetexDocs`).

## Checks

There is no test suite. After any change:

```bash
python3 -m py_compile getex     # must compile cleanly
```

For pure-logic changes (e.g. mark reindexing, selection math), prefer extracting the
logic into a tiny standalone `python3 -c '...'` harness and asserting on it, since
`curses` code cannot run in a non-TTY environment. Interactive behavior must be
verified by the user in a real terminal.

## Architecture

One file, a handful of top-level helpers, and three `curses` UI classes:

- **`GetexEditor`** (`getex` editor core) — modal editor with two modes:
  `MODE_CMD` ("COMMAND") and `MODE_INS` ("INSERT"). The main event loop is
  `run()`; per-keystroke handling branches on `self.mode`. `render()` draws the
  buffer, gutter line numbers, status bar, and hint line. `:` commands are handled
  in `run_cmd()` / `capture_command()`.
- **`FilesBrowser`** — the `get all` browser: file list + live preview pane + an
  optional calendar filter (`c` toggles, `←/→` change day). `r` sends a file to the
  AI organizer and overwrites it.
- **`ThemeMenu`** — `:theme` color-scheme picker.
- **`ConfigMenu`** — `:config` settings menu (folder, theme, AI provider, API key);
  persists via `save_config`. Reuses `ThemeMenu` for the theme entry.
- In-editor help is `GetexEditor.show_help_screen()` (`:help`), a scrollable overlay
  listing every command. Keep it in sync with `run_cmd` and the CLI `show_help()`.

Key module-level pieces:

- **Config**: `load_config` / `save_config` / `first_run_setup`, plus `load_env_file`
  which can override `api_key` from `~/.getex/.env` (`GETEX_API_KEY`).
- **AI**: `_make_ai_request` (shared HTTP via `urllib`, supports `gemini` and
  `openai`), `call_ai` (continue/answer), `call_ai_organizer` (restructure a doc).
- **Persistence**: `save_document` / `build_filepath` / `slugify`. Files are named
  `DOC_YYYY-MM-DD_HH-MM[_titulo].txt`.
- **Selection**: `sel_ordered`, `extract_selection`, `delete_selection` (module
  functions) plus the `has_sel`/`sel_range`/`*_sel`/`paste` methods on the editor.

### Colors / themes

`THEMES` is a dict of named palettes; each maps semantic keys to `(fg, bg)` curses
color constants. `init_colors()` binds them to `curses.init_pair` numbers **1–16**.
When adding a UI element with a new color, add the key to **every** theme in `THEMES`
and allocate a new pair number in `init_colors()` — themes are expected to be
complete, and rendering code references pairs by number.

### Line marks (F2 / F3)

`self.marks` is a `dict {line_index: "green"|"red"}` on the editor. **Marks are keyed
by line index, not by content.** Any operation that inserts or removes lines must
reindex the marks so they stay attached to the intended line, via the helpers:

- `_shift_marks_for_insert(at_row, count)` — call when `count` lines are inserted at
  `at_row` (Enter split, `o`, multi-line paste).
- `_shift_marks_for_delete(at_row, count)` — call when `count` lines starting at
  `at_row` are removed/merged (Backspace/Delete joins, `dd`, deleting a multi-line
  selection). Marks on removed lines are dropped.

If you add any new code path that mutates `self.lines` length, you **must** call the
appropriate helper or marks will desync. Marks are persisted next to the document in
a parallel `<file>.txt.marks` JSON file (`load_marks` / `save_marks`).

### Firebase / sync / auth

Optional cloud layer (degrades to local-only if absent). Lives in the
`# FIREBASE` section of `getex`.

- **Dependency**: `firebase-admin` (Admin SDK). Imported lazily inside `fb_init()`
  only when a credential is found, so local-only startup stays fast. Installed with
  `pip install --user --break-system-packages firebase-admin` (PEP 668 environment).
- **Credential**: service-account JSON, discovered by `find_credential()` from
  `$GETEX_FIREBASE_CRED`, `~/.getex/firebase/service-account.json`, or a `firebase/`
  dir next to the script. **Never commit it** (see `.gitignore`).
- **Global state**: `_fb_state` dict (db, user, online, reason) with accessors
  `fb_db()`, `fb_user()`, `fb_is_online()`, `fb_is_real_user()`, `fb_status_tag()`.
  This avoids threading db/user through every curses constructor.
- **Auth model — workspace-scoped accounts** (app-level, not Firebase Auth; only a
  service account is available, no Web API key). A login is **(workspace, email,
  password)**: the same email can have independent accounts in different workspaces.
  Firestore layout:
  - `workspaces/{WID}` — `{name, created_at, created_by, admin_uid}`. **`WID` =
    `normalize_ws(name)` is the primary key** (uppercase, alnum/`_`, ≤64): a name is
    globally unique, so there are **no access keys**. Privacy of `PESSOAL`/`UMTI`
    comes from the fact that you can't join an existing workspace yourself — only its
    admin adds you.
  - `workspaces/{WID}/users/{uid}` — `{email, name, salt, password_hash, created_at}`.
  - `notes/{id}` — `{workspace_id: WID, owner_uid, author_email, filename, content,
    marks, updated_at, deleted}`.
  Functions: `normalize_ws`, `fb_find_workspace`, `fb_find_user_in_ws`,
  `fb_create_workspace` (register = create a NEW workspace; fails if the name exists;
  the creator becomes admin via `created_by`/`admin_uid`), `fb_add_member` (admin
  provisions a user), `fb_login`, `offline_login` (matches cached workspace+email).
  `LoginScreen`: login = workspace/email/password; register = workspace/name/email/
  password (creates a new workspace). Session cached in `~/.getex/session.json`
  (chmod 600); `main()` auto-resumes it, else shows login, else `LOCAL_GUEST`.
- **Local storage is workspace-scoped**: `active_folder(cfg)` returns
  `~/Desktop/<folder>/<WID>/` for a real user (so each workspace's `.txt` notes are
  isolated on disk) and `~/Desktop/<folder>/` for the local guest. `build_filepath`,
  `list_docs`, and every sync call go through it.
- **Sync model**: notes stay as `.txt` files; each gets a sidecar
  `<file>.txt.sync.json` = `{id, workspace_id, owner_uid, updated_at, dirty, deleted}`.
  `sync_notes(folder)` pushes dirty notes then pulls the workspace's notes
  (last-write-wins by `updated_at`). Saving marks dirty (`mark_note_dirty`) and
  best-effort pushes (`push_note_if_online`). Offline deletes are queued as
  tombstones in `~/.getex/sync/tombstones.json`.
- **Account/member management** (`AccountMenu`, curses): `:account` opens it,
  `:passwd` jumps straight to password change. Trocar senha verifies the old password
  and updates `workspaces/{WID}/users/{uid}` + the local session. The workspace
  **creator** (`workspaces/{WID}.created_by`) is the admin and can **add** users
  (`fb_add_member`) and **remove** them (`fb_remove_member`); can't remove self or the
  creator. There is no password *reset* (forgot-password) flow — only authenticated
  change; a member who forgets is removed and re-added by the admin.
- Editor commands: `:sync`, `:whoami`, `:logout`, `:account`, `:passwd`. Browser: `s`
  to sync. Switch workspace = `:logout` then log into another one.
- **Security caveat**: the service account bypasses Firestore rules (full access), so
  workspace isolation is enforced at the app layer, not by the DB. Adequate for a
  trusted team now; real isolation needs Firebase Auth + security rules (or a backend)
  — a later hardening step.

### Cross-platform (Linux + macOS + Windows)

Pure stdlib + `curses`. Linux/macOS have `curses` natively; **Windows needs the
`windows-curses` pip package** (PDCurses). The top-level `import curses` is wrapped to
print a friendly install hint and exit on Windows if it's missing.

- **Desktop base**: `desktop_dir()` resolves the docs base across platforms — handles
  the OneDrive-redirected Desktop on Windows (`~/OneDrive/Desktop`, `$OneDrive`) and
  the localized `Área de Trabalho`. Everything goes through `active_folder()` →
  `desktop_dir()`. Don't hardcode `~/Desktop` anymore.
- **escdelay**: call `safe_set_escdelay()` (not `curses.set_escdelay` directly) —
  windows-curses may not implement it.
- **Colors**: `init_colors()` wraps `use_default_colors()` and each `init_pair` so the
  `-1` (transparent) values degrade to white/black when PDCurses rejects them. New
  pairs must go through the local `_pair()` helper.
- macOS Terminal/iTerm (and Windows consoles) often intercept `F2`/`F3` (need `Fn`),
  so command mode also accepts **`2`/`3`** as aliases for the green/red marks. Keep
  both wired together.
- **Installers**: `install.sh` (Linux/macOS, bash 3.2-compatible — no associative
  arrays/`${var^^}`) and `install.ps1` (Windows/PowerShell — installs
  `windows-curses`+`firebase-admin`, copies `getex.py` to `%LOCALAPPDATA%\getex`,
  writes a `getex.bat` shim, adds it to the user PATH). Keep both in sync with the
  install docs in `README.md`.
- **Sharing notes**: the workspace **admin adds each teammate** (`:account` → add
  user), setting their initial email/password. The teammate logs in with workspace +
  email + password and sees that workspace's notes. They still need the
  service-account credential (app-level auth uses the Admin SDK).

## Conventions

- Keep everything in the single `getex` file; don't split into modules.
- Match the existing heavy section-divider comment style (`# ─── ... ───`) and
  Portuguese comments/strings.
- Wrap `curses` drawing calls that can run off-screen in `try/except curses.error:
  pass`, as the existing code does.
- The terminal intercepts some control keys: `Ctrl+X` is unavailable (cut is
  `Ctrl+K`), and several `Ctrl+Shift+arrow` combos are read as raw escape sequences
  parsed manually in the insert-mode `\x1b` branch.

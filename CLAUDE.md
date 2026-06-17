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
- **Auth**: app-level, not Firebase Auth (only a service account is available, no Web
  API key). Users live in Firestore `users/{uid}` with PBKDF2-SHA256 salted hashes
  (`hash_password`/`verify_password`). `LoginScreen` (curses) does login/register;
  session cached in `~/.getex/session.json` (chmod 600) for auto-resume and offline
  login. `main()` auto-resumes a saved session, else shows login, else (no Firebase)
  runs as `LOCAL_GUEST`.
- **Sync model**: notes stay as `.txt` files; each gets a sidecar
  `<file>.txt.sync.json` = `{id, workspace_id, owner_uid, updated_at, dirty, deleted}`.
  `sync_notes()` pushes dirty notes then pulls the workspace's notes
  (last-write-wins by `updated_at`). Saving marks dirty (`mark_note_dirty`) and
  best-effort pushes (`push_note_if_online`). Offline deletes are queued as
  tombstones in `~/.getex/sync/tombstones.json`. Firestore collections: `users`,
  `workspaces`, `notes`.
- **Workspaces**: each user gets a personal `workspace_id` at signup; notes carry it.
  Team workspaces are a planned future phase — the data model already supports them
  (`workspaces/{wid}` with `members`), but no multi-workspace UI exists yet.
- Editor commands: `:sync`, `:whoami`, `:logout`. Browser: `s` to sync.
- **Security caveat**: the service account bypasses Firestore rules (full access).
  Fine for the single owner now; distributing it to a team would give everyone full
  DB access. Hardening (real Firebase Auth + rules, or a backend) is deferred to the
  workspace phase.

### Cross-platform (macOS + Linux)

Pure stdlib + `curses`, so it runs on macOS and Linux unchanged. Notes:

- `~/Desktop` is used as the docs base on both (macOS keeps the real path `~/Desktop`
  even when Finder shows a localized name).
- macOS Terminal/iTerm often intercept `F2`/`F3` (need `Fn`), so command mode also
  accepts **`2`/`3`** as aliases for the green/red marks. Keep both wired together.
- `install.sh` is the cross-platform installer (detects OS, installs `firebase-admin`
  trying `--user` then `--user --break-system-packages`, copies `getex.py` to
  `/usr/local/bin/getex`, prepares `~/.getex/firebase`). Keep it bash 3.2-compatible
  (macOS ships old bash): no associative arrays, no `${var^^}`.
- **Sharing notes**: in the current single-workspace model, a second person sees the
  owner's notes by using the same Firebase credential + logging in with the same
  account (same `workspace_id`). Per-user membership of a shared workspace is the
  future team phase.

## Conventions

- Keep everything in the single `getex` file; don't split into modules.
- Match the existing heavy section-divider comment style (`# ─── ... ───`) and
  Portuguese comments/strings.
- Wrap `curses` drawing calls that can run off-screen in `try/except curses.error:
  pass`, as the existing code does.
- The terminal intercepts some control keys: `Ctrl+X` is unavailable (cut is
  `Ctrl+K`), and several `Ctrl+Shift+arrow` combos are read as raw escape sequences
  parsed manually in the insert-mode `\x1b` branch.

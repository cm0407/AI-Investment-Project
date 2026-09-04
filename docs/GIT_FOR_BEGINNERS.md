# Git, for someone who has never used it

A short reference for this project. Nine commands do 95% of the work.

---

## What git actually is

Git is a **save-point system for folders**. Every time you commit, git photographs the
entire folder and stores that snapshot forever with a message saying what changed. You can
walk back to any snapshot later.

For this project that matters for one specific reason: CLAUDE.md says the record of what
you believed, and *when* you believed it, must be preserved and un-rewritable. Git is what
enforces that. It's the difference between "I always thought that stock was risky" and
being able to prove it.

### Three places a file can live

```
   your folder                staging area              repository
  (working tree)              ("the index")            (permanent history)

   you edit here  ──git add──▶  files you've   ──git commit──▶  a saved snapshot
                                picked for the                   with a message
                                next snapshot
```

The staging area exists so you can commit *some* changes and not others. When you're
starting out, `git add -A` (stage everything) is almost always what you want.

---

## The nine commands

### 1. Create a repository — once per project

```bash
git init
```

Creates a hidden `.git` folder. That folder *is* the repository — the entire history lives
in it. Nothing is tracked yet.

### 2. See what's changed — use this constantly

```bash
git status
git status --short      # compact version
```

Answers "what have I changed, and what's staged?" Run it before and after everything.
There is no way to break anything with `git status`.

### 3. Stage changes

```bash
git add -A              # stage everything (new, edited, deleted)
git add memory/         # stage just one folder
git add notes/file.md   # stage just one file
```

`-A` means *all*. Files matching `.gitignore` are skipped automatically.

### 4. Commit — make the save point

```bash
git commit -m "2026-09-04: reviewed AAPL, no recommendation issued"
```

Writes the snapshot permanently. `-m` is the message. **Write it for your future self** —
"updated stuff" is useless six months later; "rejected NVDA on valuation, logged reasoning"
is not.

For a longer message with detail underneath the summary line:

```bash
git commit -F - <<'EOF'
2026-09-04: reviewed AAPL and JPM

Reverse DCF shows AAPL price implies 35.6% FCF growth vs 6.1% delivered.
No recommendation issued - preferences file still unfilled.
EOF
```

### 5. Read the history

```bash
git log --oneline           # one line per commit
git log --stat -1           # the most recent commit + which files changed
git log --oneline -5        # last 5 commits
```

Press `q` to quit if it opens a scrolling pager.

### 6. See the actual edits

```bash
git diff                    # changes you have NOT staged yet
git diff --staged           # changes you HAVE staged
git diff HEAD~1 HEAD        # what changed in the last commit
```

### 7. Undo things

```bash
git restore notes/file.md       # throw away edits to one file (CAREFUL: unrecoverable)
git restore --staged file.md    # unstage a file, keep the edits
git revert <commit-hash>        # make a NEW commit that undoes an old one - safe
```

`git revert` is the safe undo: it adds a commit rather than erasing one, so the history
stays honest. That fits this project — you don't want to quietly delete a bad call, you
want the record to show you made it and then changed your mind.

### 8. Look at an old version

```bash
git show <hash>:memory/predictions.csv     # print an old version of a file
git log -p memory/lessons_learned.md       # every change ever made to one file
```

This is the payoff. `git log -p memory/predictions.csv` shows every prediction you ever
made, in the order you made them, with dates you cannot fake.

### 9. Fix the message you just wrote

```bash
git commit --amend -m "better message"
```

Rewrites the **most recent** commit only. Safe while the work is local. Avoid it once
you've pushed to somewhere shared — other people may already have the old version.

---

## Doing it yourself from scratch

Creating a repo and making the first commit, start to finish:

```bash
cd "path/to/your/folder"       # 1. go to the folder
git init                       # 2. create the repository
                               # 3. create a .gitignore (see below)
git status                     # 4. look at what git can see
git add -A                     # 5. stage everything not ignored
git status                     # 6. check what's staged before committing
git commit -m "Initial commit" # 7. save the snapshot
git log --oneline              # 8. confirm it worked
```

A minimal `.gitignore` for a Python data project:

```gitignore
data/cache/       # anything a script can re-download
__pycache__/      # Python's compiled bytecode
.env              # secrets - NEVER commit these
*.key
.venv/
```

**On secrets:** deleting a committed password does *not* remove it from history. It stays
in every past snapshot. Ignore it before the first commit, not after.

---

## The end-of-session routine for this project

```bash
git status --short                                   # what changed?
git add -A                                           # stage it all
git commit -m "2026-09-04: <what you actually did>"  # save it
```

That's it. Three commands.

---

## Two rules specific to this project

**1. Never rewrite the research record.** `git commit --amend`, and other history-editing
commands, are fine for a typo in a message you just wrote. They are *not* fine for making
a past prediction look smarter. CLAUDE.md is explicit about this, and it's the entire
reason predictions are stored append-only.

**2. Commit even when the answer was "no".** A session that reviewed four companies and
recommended none is a real result worth recording. Rejections in
`memory/rejected_stocks.md` are how you avoid re-researching the same name next month and
forgetting why you passed.

---

## When something looks broken

| You see | What it means | Do this |
|---|---|---|
| `nothing to commit, working tree clean` | No changes since the last commit | Nothing — this is fine |
| `Untracked files:` | New files git isn't watching yet | `git add -A` |
| Editor opens and you're stuck | Git wants a commit message | Type message, then `Esc` `:wq` `Enter` (vim) |
| A long output won't quit | You're in the pager | Press `q` |
| `LF will be replaced by CRLF` | Windows line-ending notice | Harmless, ignore it |
| `fatal: not a git repository` | You're in the wrong folder | `cd` to the project, or `git init` |

Nothing you do to *tracked, committed* files is truly lost — `git reflog` lists recent
states even after mistakes. The genuinely unrecoverable case is `git restore` on edits you
never committed.

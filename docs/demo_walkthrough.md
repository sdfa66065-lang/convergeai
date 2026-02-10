# Demo Setup Guide: Running ConvergeAI + Simulating a Merge Conflict

This guide gives you a clean, repeatable demo flow you can run locally.

---

## 1) Prerequisites

Make sure you have:

- Python 3.10+
- Git
- An OpenAI API key (if you plan to run with the OpenAI adapter)

Optional but useful:

- A separate terminal for each repository during the demo
- A screen recorder (for rehearsal)

---

## 2) Clone and prepare ConvergeAI

From a terminal:

```bash
git clone <YOUR_CONVERGEAI_REPO_URL>
cd convergeai
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

---

## 3) Configure environment variables

For OpenAI-backed demo runs:

```bash
export OPENAI_API_KEY="<your_key>"
```

If you use another adapter/script, set that adapter's required variables before running.

---

## 4) Create two repos to simulate conflict

Create a demo workspace and two repositories:

```bash
mkdir -p ~/convergeai-demo
cd ~/convergeai-demo
mkdir repo-a repo-b
cd repo-a
git init
```

Add an initial file in `repo-a`:

```bash
cat > app.txt <<'EOF_A'
Line 1: base
Line 2: shared
Line 3: base
EOF_A

git add app.txt
git commit -m "Initial base version"
```

Now create `repo-b` as a copy of the base state:

```bash
cd ~/convergeai-demo
git clone repo-a repo-b
```

At this point, `repo-a` and `repo-b` start from the same commit.

---

## 5) Introduce conflicting changes

### In `repo-a` (change the same line one way)

```bash
cd ~/convergeai-demo/repo-a
cat > app.txt <<'EOF_A2'
Line 1: base
Line 2: change from REPO A
Line 3: base
EOF_A2

git add app.txt
git commit -m "Repo A edits shared line"
```

### In `repo-b` (change the same line differently)

```bash
cd ~/convergeai-demo/repo-b
cat > app.txt <<'EOF_B2'
Line 1: base
Line 2: different change from REPO B
Line 3: base
EOF_B2

git add app.txt
git commit -m "Repo B edits shared line differently"
```

Now both repos changed the exact same line in different ways.

---

## 6) Produce conflict data for your demo

From `repo-b`, try pulling/cherry-picking `repo-a`'s change to force a conflict:

```bash
cd ~/convergeai-demo/repo-b

git remote add demo-a ../repo-a || true
git fetch demo-a

git cherry-pick demo-a/master
# If your default branch is main, use demo-a/main
```

Git should stop with conflict markers in `app.txt`.

Verify:

```bash
git status
cat app.txt
```

You should see `<<<<<<<`, `=======`, `>>>>>>>` sections.

---

## 7) Feed the conflict into ConvergeAI

From your ConvergeAI directory, use your normal conflict-resolution pipeline with:

- The conflict file (`app.txt`)
- The merge/cherry-pick context
- Any project-specific prompts in `prompts/conflict_resolver.md`

Typical structure in your demo:

1. Show the unresolved conflict in terminal.
2. Run ConvergeAI conflict workflow.
3. Show generated resolution suggestion.
4. Apply it and run:
   ```bash
   git add app.txt
   git cherry-pick --continue
   ```
5. Show clean history and final file.

---

## 8) Suggested demo script (talk track)

1. "We start with two repos from the same base commit."
2. "Each side changes the same line differently."
3. "A merge operation produces a real Git conflict."
4. "ConvergeAI analyzes conflict context and proposes a resolution."
5. "We apply, continue the operation, and verify clean result."

---

## 9) Quick reset between demo runs

If you want to repeat quickly:

```bash
rm -rf ~/convergeai-demo
mkdir -p ~/convergeai-demo
```

Then rerun sections 4-6.

---

## 10) Troubleshooting

- `cherry-pick demo-a/master` fails because branch name is `main`:
  - Use `demo-a/main`.
- No conflict appears:
  - Ensure both repos edited the *same line* from the same base commit.
- API errors in ConvergeAI:
  - Verify `OPENAI_API_KEY` is exported in the same shell where you run scripts.
- Import/module errors:
  - Re-activate venv and reinstall required dependencies.

---

## 11) Where adapter inputs/outputs are saved

Yes—Phase 2 persists adapter payloads so you can inspect exactly what was sent/received.

Inside your workspace (for example `./workspaces/run-20240101/artifacts/phase2/`), look for:

- `conflict_step_<n>/hunk_<id>/agent_request.json`
- `conflict_step_<n>/hunk_<id>/agent_response.json`
- `compile_step_<n>/agent_request.json`
- `compile_step_<n>/agent_response.json`
- `test_step_<n>/agent_request.json`
- `test_step_<n>/agent_response.json`

These are ideal for demo narration because they show deterministic interface contracts.

---

## 12) Mock adapter with preset responses

If you want predictable demo behavior, run the mock adapter with a fixed response:

### Option A: preset conflict resolution text

```bash
export MOCK_ADAPTER_RESOLVED_TEXT="Line 2: merged demo result"
python3 scripts/mock_agent_adapter.py --port 8001
```

Then run Phase 2:

```bash
python3 scripts/phase2.py \
  --workspace ./workspaces/run-20240101 \
  --agent-endpoint http://localhost:8001/v1/resolve
```

### Option B: load full JSON response from file

Create a response file (works for conflict/compile/test prompts):

```bash
cat > /tmp/mock-response.json <<'EOF'
{
  "resolved_text": "Line 2: merged demo result",
  "confidence": 0.99,
  "resolution": "demo-preset"
}
EOF

export MOCK_ADAPTER_RESPONSE_FILE=/tmp/mock-response.json
python3 scripts/mock_agent_adapter.py --port 8001
```

Tip: for compile/test demos, the response file can instead be:

```json
{ "patch": "<unified diff here>" }
```


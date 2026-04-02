# Phase 2 example: create a deliberate conflict and run the loop

This walkthrough creates a tiny upstream/downstream pair with a conflicting change
so you can see the Phase 1/Phase 2 artifacts end-to-end.

## 1) Create an upstream repo with a base commit

```bash
mkdir -p /tmp/phase2-demo
cd /tmp/phase2-demo
git init upstream
cd upstream
cat <<'EOF' > Demo.java
public class Demo {
  public static String greet() {
    return "hello";
  }
}
EOF
git add Demo.java
git commit -m "base"
UPSTREAM_BASE=$(git rev-parse HEAD)
```

## 2) Create a downstream fork and add a conflicting change

```bash
cd /tmp/phase2-demo
git clone upstream downstream
cd downstream
git remote add upstream ../upstream

cat <<'EOF' > Demo.java
public class Demo {
  public static String greet() {
    return "hello from downstream";
  }
}
EOF
git add Demo.java
git commit -m "downstream change"
```

## 3) Add an upstream change that will conflict

```bash
cd /tmp/phase2-demo/upstream
cat <<'EOF' > Demo.java
public class Demo {
  public static String greet() {
    return "hello from upstream";
  }
}
EOF
git add Demo.java
git commit -m "upstream change"
UPSTREAM_CHANGE=$(git rev-parse HEAD)
```

## 4) Create a Phase 1 config and run Phase 1

From the ConvergeAI repo root:

```bash
cat <<EOF > /tmp/phase2-demo/config.json
{
  "repository_url": "/tmp/phase2-demo/downstream",
  "base_ref": "main",
  "upstream_remote": "upstream",
  "upstream_url": "/tmp/phase2-demo/upstream",
  "upstream_ref": "main",
  "binary_conflict_policy": "ours",
  "cherry_picks": [
    "$UPSTREAM_CHANGE"
  ]
}
EOF

python3 scripts/phase1.py \
  --config /tmp/phase2-demo/config.json \
  --workspace-root /tmp/phase2-demo/workspaces \
  --run-id demo
```

Phase 1 will emit a conflict JSON that includes the diff3 hunk data for `Demo.java`.

## 5) Run Phase 2 and inspect artifacts

```bash
python3 scripts/phase2.py --workspace /tmp/phase2-demo/workspaces/demo
```

Check the artifacts directory:

```bash
ls /tmp/phase2-demo/workspaces/demo/artifacts/phase2
```

Each conflict step will include:
- `patch.diff` (the applied patch)
- `agent_request.json` (the structured hunk payload)
- `agent_response.json` (the resolution decision)

Compile/test steps will include:
- `agent_request.json` (structured errors/failures + context)
- `patch.diff` (if a fixer writes one)
- `stdout.txt` / `stderr.txt` (build output)

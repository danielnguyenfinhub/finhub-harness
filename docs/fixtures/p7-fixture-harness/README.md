# P7 fixture harness

One skill and one agent for probe P7 in `docs/surface-verification.md`. The agent lists `fixture` under `## Required connectors`; attach no such connector. Nothing here sends, writes or publishes.

Build the two upload files (run from the repository root):

```bash
bash docs/fixtures/p7-fixture-harness/build.sh
```

- `dist/p7-fixture-harness-skill.zip`: upload as a skill in Claude chat.
- `dist/p7-fixture-harness.plugin`: add as a plugin in Cowork.

Then send `run the fixture harness`. Pass: the reply names `fixture` and `fixture-checker`, then asks whether to attach it, continue without it, or stop, and does not stop by itself.

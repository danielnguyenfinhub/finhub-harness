---
name: broken
description: "Fixture with one defect per rule. Use to prove each rule fires."
---

# Broken

A dead link: [x](missing.md) and a dead image ![i](assets/none.png).
A dead fragment link: [y](gone/page.md#top).
[ref-style][d1]

[d1]: gone-def.md

A missing bundled file in code: `references/ghost.md`, and in prose: references/ghost2.md.

```text
[hidden](nope.md) and references/hidden.md stay silent
```
After the closed fence the next link is checked again: [z](after-fence.md)
An angle target with a space that is missing: [a](<missing angle.md>)

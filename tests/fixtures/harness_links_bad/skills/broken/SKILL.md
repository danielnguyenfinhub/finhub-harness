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
Nesting one level, missing: [n1](gone(1).md)
Nesting two levels, missing: [n2](gone((2)).md)
Titles: [t1](gone-t1.md "title") [t2](gone-t2.md 'title') [t3](gone-t3.md (title))
Padding: [p1](  gone-p1.md) [p2](gone-p2.md )
[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx](gone-t300.md)
   [d3]: gone-d3.md
[d4]: gone-d4.md "T"
[yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy]: gone-d300.md
[bt]: `gone-bt.md`
A hyphenated bundled name: references/a-b.md
[nsp]:gone-nospace.md
[unterm]: <gone-unterm.md
Double backticks do not hide a link: `` [dbl](gone-dbl.md) ``
```
inside a fence closed by a fence line that ends in a tab
```	
After the tab-closed fence: [tab](gone-tab.md)
A bundled name with a digit in its extension: references/ghost3.mp3

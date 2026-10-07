---
name: linky
description: "Fixture whose links and bundled-file mentions all resolve. Use to prove no false errors."
---

# Linky

Plain: [ok](references/real.md), [titled](references/real.md "a title"), [frag](references/real.md#top),
[query](references/real.md?x=1), [dir](references/), [angle](<references/real.md>), ![img](references/real.md).
Not local: [a](#anchor), [h](https://example.test/x.md), [m](mailto:a@b.test), [t](tel:123), [abs](/etc/none),
[tpl]({{ page.url }}), [home](~/none.md), [var]($ROOT/none.md).
Inline code is an example for links: `[bad](nope.md)`. (Bundled mentions in inline code are checked.)
Bundled mention that exists: references/real.md, and a sentence end references/real.md.
Submodule-style citation, never checked: references/some_repo/src/mod.py:43 and references/pkg.v2/inner.md.
Placeholders: references/<name>.md, references/{x}.md, references/*.md, references/... and references/.
Path-prefixed mention: .claude/skills/other/references/ghost.md and ../references/ghost.md.
[ref-style][r1] and an encoded space: [sp](references/with%20space.md)

[verified]: prose
[Step 1]: run the lint
[TODO]: write this
[^1]: See the paper.
[^3]: notes/missing.md
[x]: done
[Note]: docs/missing.md is the place for this

[r1]: references/real.md

```markdown
[bad](nope.md)
references/ghost.md
[r2]: gone.md
```

~~~
[bad](nope.md) references/ghost.md
```
[bad](nope.md)
~~~

````text
```
[bad](nope.md)
```
references/ghost.md
````

An angle target with a space: [s](<references/with space.md>).
A target too long for any file system is skipped, not judged: [long](aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.md).
Word boundary: my-references/zzz.md and myreferences/zzz.md are other paths.

    [indented]: nope.md

```markdown
[bad](nope.md)
```text
[bad](nope.md)
```

Silent: a 301-char link text [xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx](gone-t301.md), a definition whose title holds a link
[ok2]: references/real.md "see [y](gone.md)"
.references/zzz.md, references/zzz.md-y and references/.zzz.md are other paths.

A four-space-indented fence still opens one (the script is looser than CommonMark):
    ```
[hidden](gone-indent.md)

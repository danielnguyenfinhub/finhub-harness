---
name: license-compatibility-matrix
description: "Guide to open source license compatibility matrices, per-license obligations, dual-licensing strategy and SPDX identifiers. Use this skill whenever a decision involves open source licensing, with triggers such as 'license compatibility', 'choosing a license', 'MIT', 'Apache', 'GPL', 'LGPL', 'BSD', 'dual license', 'SPDX' and 'license conflict'. It strengthens the license-specialist's license analysis. Legal advice and generating actual license files are outside the scope of this skill."
---

# License Compatibility Matrix — Open Source License Compatibility Guide

A practical guide to choosing an open source license, analysing compatibility, and resolving dependency license conflicts.

## Comparison of Major Licenses

| License | Type | Commercial use | Modification disclosure | Patent protection | Network clause |
|---------|------|----------|----------|----------|-------------|
| MIT | Permissive | O | X | X | X |
| Apache 2.0 | Permissive | O | X | O | X |
| BSD 2-Clause | Permissive | O | X | X | X |
| BSD 3-Clause | Permissive | O | X | X | X |
| MPL 2.0 | Weak copyleft | O | Per file | O | X |
| LGPL 2.1/3.0 | Weak copyleft | O | Library only | X | X |
| GPL 2.0/3.0 | Strong copyleft | Conditional | O (whole work) | O(v3) | X |
| AGPL 3.0 | Strong copyleft | Conditional | O (whole work) | O | O |

## Compatibility Matrix

```
Project license ↓  |  Dependency license →
                    | MIT | Apache | BSD | MPL | LGPL | GPL | AGPL
────────────────────┼─────┼────────┼─────┼─────┼──────┼─────┼──────
MIT                 | ✅  | ✅     | ✅  | ✅  | ✅   | ❌  | ❌
Apache 2.0          | ✅  | ✅     | ✅  | ✅  | ✅   | ❌  | ❌
BSD                 | ✅  | ✅     | ✅  | ✅  | ✅   | ❌  | ❌
MPL 2.0             | ✅  | ✅     | ✅  | ✅  | ✅   | ✅* | ❌
LGPL 3.0            | ✅  | ✅     | ✅  | ✅  | ✅   | ✅  | ❌
GPL 3.0             | ✅  | ✅     | ✅  | ✅  | ✅   | ✅  | ❌
AGPL 3.0            | ✅  | ✅     | ✅  | ✅  | ✅   | ✅  | ✅

✅ Compatible | ❌ Incompatible | ✅* Conditionally compatible
```

**Key rules:**
- Using a GPL dependency means the whole project falls under the GPL (the viral effect)
- Using an AGPL dependency means network services must also disclose their source
- Apache 2.0 and GPL 2.0 are incompatible (the patent clauses conflict)

## License Selection Decision Tree

```
Project goal
├── Wants maximum adoption → MIT or Apache 2.0
│   ├── Needs patent protection → Apache 2.0
│   └── Wants maximum simplicity → MIT
├── Wants modifications disclosed (per file) → MPL 2.0
├── A library, where linking is allowed → LGPL 3.0
├── Wants all derivative works disclosed → GPL 3.0
├── Wants disclosure to include SaaS → AGPL 3.0
└── Dual license (OSS + commercial) → GPL + Commercial
```

## Resolving Dependency License Conflicts

### Conflict Patterns and Resolutions

| Conflict | Problem | Resolution |
|------|------|------|
| MIT project + GPL dependency | GPL propagation | Look for a replacement package, or switch to the GPL |
| Apache + GPL 2.0 | Incompatible patent clauses | Use the GPL 3.0 version |
| Commercial product + AGPL dependency | Obligation to disclose source | Replace the package or buy a license |
| Mixing several GPL versions | Version compatibility | Use "GPL 2.0 or later" |

### License Audit Tools

```bash
# Node.js
npx license-checker --json --production

# Python
pip-licenses --format=json --with-urls

# Go
go-licenses check ./...

# General purpose
scancode-toolkit --json-pp output.json src/
```

## SPDX License Expressions

```
# Single license
SPDX-License-Identifier: MIT

# OR (either may be chosen)
SPDX-License-Identifier: MIT OR Apache-2.0

# AND (both licenses must be complied with)
SPDX-License-Identifier: MIT AND BSD-3-Clause

# WITH (includes an exception)
SPDX-License-Identifier: GPL-2.0-only WITH Classpath-exception-2.0
```

## Dual-Licensing Strategy

```
Community Edition: AGPL 3.0
├── Free to use
├── Source must be disclosed when offering modifications as a service
└── Suited to individual and small open source projects

Enterprise Edition: Commercial license
├── Exempt from AGPL obligations
├── Includes additional features and support
└── Aimed at enterprise customers

Success stories: MongoDB(SSPL), Redis(RSALv2), MySQL(GPL+Commercial)
```

## License Obligations Checklist

```markdown
Check before releasing the project:
- [ ] All dependency licenses identified
- [ ] License compatibility matrix verified
- [ ] LICENSE file includes all third-party licenses
- [ ] Copyright notice (NOTICE) file written (required by Apache 2.0)
- [ ] Source disclosure prepared if a GPL dependency is used
- [ ] SPDX identifiers included in source files
- [ ] License field specified in package.json/pyproject.toml
```

## Known doubtful cells: verify before relying

The matrix and tables above are reproduced from the source as written. A reviewer flagged these entries as questionable, and none has been checked against licence texts or the FSF and SPDX compatibility lists. Treat them as unverified and confirm before any licence decision.

- MIT, Apache and BSD projects marked compatible with an LGPL dependency.
- A GPL 3.0 project marked incompatible with an AGPL dependency.
- An MPL 2.0 project with a GPL dependency marked conditionally compatible, with no condition stated.
- In the comparison table: LGPL patent protection, GPL patent protection (v3 only) and "conditional" commercial use for GPL and AGPL.
- The dual-licence examples: MongoDB (SSPL) and Redis (RSALv2) are not dual licensing in the usual sense, and neither licence is an open-source licence.
- The column headed "Modification disclosure" is a translator's reading of the Korean header.

This skill is general guidance, not legal advice.

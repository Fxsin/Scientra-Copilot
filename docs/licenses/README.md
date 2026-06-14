# Third-Party License Archive

This directory contains original, unmodified license files from third-party
projects whose source code is bundled in the `external/` directory of this
repository, or whose components are adapted into the Scientra Copilot codebase.

## Directory Structure

```
docs/licenses/
├── README.md                           # This file
├── opendataloader-pdf/
│   ├── LICENSE                          # Apache License 2.0
│   └── NOTICE                           # Apache NOTICE file
└── marker/
    ├── LICENSE                          # GNU GPL v3.0
    └── MODEL_LICENSE                    # AI PUBS OPEN RAIL-M (Modified)
```

## Purpose

These files are preserved to comply with the terms of their respective licenses:

- **Apache License 2.0** (§4d): Requires that any NOTICE file included in the
  original work be reproduced in any derivative works.
- **GNU GPL v3.0** (§4): Requires that the license text be included with any
  distribution of the software.
- **OpenRAIL-M**: Requires that the license be included with any distribution
  of the model weights.

## Updating

When upgrading the external projects in `external/`, copy their updated
LICENSE (and NOTICE, if applicable) files to the corresponding subdirectory here.

DO NOT modify these files — they must remain exact copies of the originals.

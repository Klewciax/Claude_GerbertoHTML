# build_tools

Development-only helper used to regenerate `pcb_report/assets/tracespace-bundle.mjs`,
the single self-contained Node script the Python CLI shells out to for Gerber → SVG
rendering (via [`@tracespace/core`](https://github.com/tracespace/tracespace)).

This directory is **not** needed to run `pcb_report` — only to rebuild the vendored
bundle after updating the tracespace libraries.

```bash
cd build_tools
npm install
npm run build
```

The output is a single ESM file with all tracespace packages inlined; at runtime it
only imports Node's built-in `node:fs/promises` and `node:path`, so the Python tool
only needs a working `node` executable on `PATH` — no `npm install` required by end users.

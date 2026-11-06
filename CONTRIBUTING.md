# Contributing

Use synthetic fixtures for public tests. Do not submit students' or customers' boards without permission.

Run `python -m unittest discover -s tests -v` for portable tests. For KiCad integration, use KiCad 10's Python and follow `docs/TESTING.md`.

For bugs, provide the plugin version, OS/architecture, KiCad version, export mode and relevant error. A small synthetic reproducer is preferred. Remove personal paths and confidential circuit data from reports before posting.

Do not fix a conversion by silently removing geometry, merging nets or changing source files. A single-pad net may be intentional. Whitespace observations belong in informational notes and must not block export.

Changes to pins, pad orientation, layers, drill sizes or signal mapping need a meaningful round-trip or connectivity check. A successful XML/schema check alone does not establish Eagle/Fusion compatibility.

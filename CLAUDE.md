# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MANDATORY: Read before making any code changes

You MUST read [`CONTRIBUTING.rst`](./CONTRIBUTING.rst) before making any code changes, commits, or
pull requests.  It contains the authoritative project conventions including:

- Development environment setup and the commands to run tests, linting, and type checking
- Code style rules (formatting, imports, type annotations, docstrings)
- Testing requirements, including the **mandatory `@pytest.mark.ai_generated` marker on any test
  written with AI assistance**
- PR labeling, changelog, and release workflow

Do NOT guess or assume conventions — read the file.  Additional documentation may be found under
[`docs/`](./docs).

## Docstring style

Keep function/method docstrings terse:

- First line: a short summary sentence (fits on one line).
- Then a blank line.
- Only if genuinely needed: a short extended description covering critical
  user-facing aspects (return value semantics, options, caveats) — never a
  restatement of the implementation below it. The code is the source of
  truth for *how*; the docstring is for *what*/*why*.
- Small and/or private (`_`-prefixed) functions can often skip the extended
  description entirely — a one-line summary is enough when the function is
  short and self-evident.

Do not write multi-paragraph docstrings, or NumPy-style Parameters/Returns
sections, for small internal helpers whose signature is already clear from
its type annotations. Reserve the fuller NumPy-style form (per
CONTRIBUTING.rst) for public functions whose usage genuinely benefits from
it.

# Security Policy

## Supported versions

Security updates are provided for the latest `2.x` release line. We recommend always
running the most recent version of Flama.

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |

## Loading model artifacts

Deserialising a `.flm` artifact executes code from that artifact. The model section is handed
to the framework that produced it, and for several of the supported frameworks that means
unpickling: `pickle` and `torch` payloads can run arbitrary code as soon as the model is
materialised. This is inherent to the underlying formats, not a defect Flama can patch away.

Treat a `.flm` file exactly as you would treat a pickle: **only load artifacts from sources you
trust**. Loading a model downloaded from an untrusted or unverified location is equivalent to
running that publisher's code on your machine, regardless of any hardening in the serialisation
layer.

## Reporting a vulnerability

Please **do not** report security vulnerabilities through public GitHub issues,
discussions, or pull requests.

Instead, report them privately through GitHub's
[private vulnerability reporting](https://github.com/vortico/flama/security/advisories/new).
If you are unable to use that channel, email the maintainers at
[perdy@perdy.io](mailto:perdy@perdy.io).

Please include as much of the following as you can to help us triage quickly:

- A description of the vulnerability and its impact.
- Steps to reproduce, or a proof of concept.
- The affected version(s) and environment.

We will acknowledge your report as soon as possible, keep you informed of our progress,
and credit you once a fix is released (unless you prefer to remain anonymous).

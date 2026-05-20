<div align="center">

# kamailio-notebook

**Interactive Jupyter Notebook kernel for Kamailio SIP Server config scripting**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Jupyter](https://img.shields.io/badge/Jupyter-Lab-F37626.svg?logo=jupyter&logoColor=white)](https://jupyter.org)
[![Tests](https://img.shields.io/badge/tests-33%20passed-success.svg)]()

[Getting Started](#getting-started) • [Demo](#demo) • [Features](#features) • [Curriculum](#curriculum) • [API Reference](#magic-commands) • [Architecture](#architecture) • [Contributing](#contributing)

English | **[한국어](README.ko.md)**

</div>

---

## The Problem

Kamailio's native `.cfg` scripting language is powerful but has a steep learning curve:

- **No REPL** — you can't test expressions interactively
- **No playground** — every change requires a server restart + SIPp test + pcap analysis
- **No instant feedback** — "what does `$({uri.user})` return?" requires reading docs and guessing
- **Sparse documentation** — function behavior is often only clear from reading C source code

## The Solution

**kamailio-notebook** brings the Jupyter Notebook experience to Kamailio cfg:

<p align="center">
  <img src="docs/images/demo-jupyter-lab.gif" width="80%" alt="Jupyter Lab Demo">
</p>

Write cfg code cell-by-cell, see results instantly, mock SIP messages, trace routing logic, and ask an AI assistant about Kamailio — all in one place.

---

## Demo

### Variables & Types

<img src="docs/images/demo-variables.svg" width="100%" alt="Variables Demo">

### SIP Message Mock & Routing Logic

<img src="docs/images/demo-routing.svg" width="100%" alt="Routing Demo">

### Transformations

<img src="docs/images/demo-transforms.svg" width="100%" alt="Transforms Demo">

### Variable Diff

<img src="docs/images/demo-diff.svg" width="100%" alt="Diff Demo">

---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- JupyterLab 4.0+

### Install

```bash
pip install kamailio-notebook
```

### Register the Kernel

```bash
kamailio-notebook-install
```

### Launch

```bash
jupyter lab
```

Select **"Kamailio CFG"** as your kernel in a new notebook. That's it!

### Quick Start from Source

```bash
git clone https://github.com/pallidev/kamailio-notebook.git
cd kamailio-notebook
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
kamailio-notebook-install
jupyter lab
```

Then open one of the curriculum notebooks in `notebooks/curriculum/`.

---

## Features

### v0.1 — Core Execution

| Feature | Description |
|---------|-------------|
| Cell-by-cell cfg execution | Write and run Kamailio cfg code one cell at a time |
| SIP message mock | `%%sip INVITE` creates a mock SIP message with full header parsing |
| Variable read/write | `$var`, `$avp`, `$ru`, `$fu`, `$rm`, and 15+ pseudo-variables |
| `%%kamcmd` integration | Query a live Kamailio instance directly from notebook cells |
| Mermaid SIP flow diagrams | Automatic visualization of SIP message flows |
| Markdown cells | Full Jupyter Markdown support for documentation (built-in) |

### v0.2 — Transformations & Tracing

| Feature | Description |
|---------|-------------|
| Transformation functions | `{uri.user}`, `{s.len}`, `{s.upper}`, `{nameaddr.uri}`, and 20+ more |
| `%%trace` magic | Step-by-step execution tracing with colored HTML output |
| If/else branch visualization | See which branches were taken with Mermaid flowcharts |
| Route block tracking | `route[]` call tracing and execution path recording |

### v0.3 — Server Control & State Tracking

| Feature | Description |
|---------|-------------|
| `%%kamailio start\|stop\|status` | Control local Kamailio instances from notebook cells |
| `%%diff` magic | Before/after variable state comparison with colored diff table |
| Variable snapshots | Automatic state capture for change tracking |

---

## Magic Commands

| Magic | Description | Example |
|-------|-------------|---------|
| `%%sip METHOD` | Create a mock SIP message | `%%sip INVITE` |
| `%%vars` | Display all current variables | `%%vars` |
| `%%diff` | Show variable changes since last execution | `%%diff` |
| `%%trace` | Trace execution path with visualization | `%%trace` |
| `%%kamcmd CMD` | Run kamcmd against live Kamailio | `%%kamcmd dispatcher.list` |
| `%%kamailio CMD` | Control local Kamailio instances | `%%kamailio status` |
| `%%help TOPIC` | Show help for a function or variable | `%%help ds_select_dst` |
| `%%flow` | Display SIP message flow diagram | `%%flow` |
| `%%reset` | Clear all state | `%%reset` |

---

## Supported cfg Syntax

### Variables

```kamailio
$var(count) = 10;                          # Script variable (integer)
$var(uri) = "sip:1001@example.com";        # Script variable (string)
$avp(caller) = "1001";                     # AVP (transaction-scoped)
$ru = "sip:1002@10.0.0.1:5060";           # Request-URI
$xlog("Calling $ru from $fu");            # Log with variable substitution
```

### Control Flow

```kamailio
if (is_method("INVITE")) {
    record_route();
    t_relay();
} else {
    send_reply(405, "Method Not Allowed");
}
```

### Transformations

```kamailio
$(ru{uri.user})      # Extract user part from URI
$(fu{uri.host})      # Extract host part
$(var(x){s.len})     # String length
$(var(x){s.upper})   # Uppercase
$(hdr{nameaddr.uri}) # URI from name-addr
```

### Functions

`is_method()`, `has_totag()`, `ds_select_dst()`, `rtpengine_manage()`, `record_route()`, `t_relay()`, `sl_send_reply()`, `save()`, `lookup()`, `append_hf()`, `remove_hf()`, `setflag()`, `isflagset()`, `xlog()`, `subst()`, and more.

---

## Curriculum

The `notebooks/curriculum/` directory contains structured lessons for all skill levels:

### Beginner (SIP & cfg Basics)

| Lesson | Topics |
|--------|--------|
| **01 - Hello Kamailio** | First cfg code, variables, xlog |
| **02 - SIP Messages & Pseudo-Variables** | `%%sip` mock, `$ru`/`$fu`/`$rm`, `$var` vs `$avp` |
| **03 - Routing Basics** | `if/else`, `is_method()`, `has_totag()`, `drop/exit` |

### Intermediate (Real-World Patterns)

| Lesson | Topics |
|--------|--------|
| **01 - Transformations** | `{uri.user}`, `{s.len}`, nameaddr, Base64, chaining |
| **02 - Dispatcher & Routing** | `ds_select_dst()`, `%%kamcmd`, full INVITE flow, REGISTER handling |

### Advanced (Production Patterns)

| Lesson | Topics |
|--------|--------|
| **01 - Dialog, Failover & Production** | Dialog tracking, failover, RTPEngine, flags, header manipulation, `%%trace`, `%%diff` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                       JupyterLab                         │
│                                                          │
│  ┌────────────────────────┐  ┌─────────────────────────┐ │
│  │   Kamailio CFG Kernel   │  │    Jupyter AI Chat      │ │
│  │                         │  │                         │ │
│  │  [Cell] cfg code        │  │  "What does             │ │
│  │        → result output  │  │   ds_select_dst do?"    │ │
│  │                         │  │                         │ │
│  │  [Cell] %%sip INVITE    │  │  → AI explains with     │ │
│  │        → mock message   │  │    notebook context     │ │
│  │                         │  │                         │ │
│  └───────────┬─────────────┘  └─────────────────────────┘ │
└──────────────┼────────────────────────────────────────────┘
               │
     ┌─────────┴───────────┐
     │   Hybrid Executor   │
     │                     │
     │  Simple expr ──────►│── Python cfg parser/evaluator
     │                     │
     │  Complex func ─────►│── kamcmd → real Kamailio
     │                     │
     └─────────────────────┘
```

### Project Structure

```
kamailio-notebook/
├── src/kamailio_notebook/
│   ├── kernel.py            # Jupyter kernel (metakernel-based)
│   ├── cfg_executor.py      # cfg expression parser & executor
│   ├── cfg_tracer.py        # Route tracing & branch visualization
│   ├── sip_message.py       # SIP message mock engine
│   ├── variables.py         # Pseudo-variable store ($var, $avp, etc.)
│   ├── transforms.py        # 20+ transformation functions
│   ├── kamcmd.py            # kamcmd/kamctl integration
│   ├── kamailio_control.py  # Local Kamailio start/stop/diff
│   ├── install.py           # Kernel registration script
│   └── renderer/
│       └── mermaid.py       # Mermaid diagram generation
├── notebooks/
│   └── curriculum/
│       ├── 01-beginner/     # 3 lessons
│       ├── 02-intermediate/ # 2 lessons
│       └── 03-advanced/     # 1 lesson
├── tests/                   # 33 tests, all passing
├── docs/images/             # Demo screenshots
├── pyproject.toml
├── LICENSE                  # MIT
└── README.md
```

---

## AI-Assisted Learning

This kernel works seamlessly with [Jupyter AI](https://github.com/jupyterlab/jupyter-ai), giving you an AI chat panel right inside JupyterLab:

1. Install Jupyter AI: `pip install jupyter-ai`
2. Configure your LLM (Claude, ChatGPT, Ollama, etc.)
3. Ask questions like "What does `ds_select_dst` do?" or "How do I handle REGISTER?"

The AI can see your notebook context, so it can explain your actual code.

---

## Comparison with Existing Tools

| Feature | kamailio-notebook | debugger module | kamcli | kamailio-tests |
|---------|:-:|:-:|:-:|:-:|
| Interactive cell execution | ✅ | ❌ | ❌ | ❌ |
| SIP message mock | ✅ | ❌ | ❌ | ❌ |
| Variable inspection | ✅ | Partial | Partial | ❌ |
| Transformation preview | ✅ | ❌ | ❌ | ❌ |
| Live server query | ✅ | ✅ | ✅ | ✅ |
| AI chat integration | ✅ | ❌ | ❌ | ❌ |
| Visual execution trace | ✅ | cfgtrace | ❌ | ❌ |
| Curriculum notebooks | ✅ | ❌ | ❌ | ❌ |

---

## Development

```bash
# Clone
git clone https://github.com/pallidev/kamailio-notebook.git
cd kamailio-notebook

# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Install kernel for development
kamailio-notebook-install

# Start JupyterLab
jupyter lab
```

## Contributing

Contributions are welcome! Here are some areas where help is needed:

- **More transformation functions** — many Kamailio transforms are not yet implemented
- **Module-specific functions** — `dialog`, `presence`, `permissions` module functions
- **Better cfg parser** — the current parser handles common patterns but not all edge cases
- **Integration tests** — test against real Kamailio instances
- **New curriculum lessons** — especially for advanced topics (KEMI, database interactions)
- **Translations** — curriculum notebooks in other languages

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details (coming soon).

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Kamailio SIP Server](https://www.kamailio.org/) — the project this kernel serves
- [metakernel](https://github.com/Calysto/metakernel) — Jupyter kernel framework
- [Jupyter AI](https://github.com/jupyterlab/jupyter-ai) — AI chat integration for JupyterLab

---

<div align="center">

**[Report Bug](https://github.com/pallidev/kamailio-notebook/issues) · [Request Feature](https://github.com/pallidev/kamailio-notebook/issues) · [Ask Question](https://github.com/pallidev/kamailio-notebook/issues)**

Made by [김종인](https://github.com/pallidev)

</div>

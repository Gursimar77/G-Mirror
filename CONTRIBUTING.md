# Contributing to G-Mirror

Thank you for your interest in contributing to G-Mirror! We welcome contributions from developers of all skill levels.

---

## Development Setup

1. **Prerequisites**:
   - Windows 10 or 11 (64-bit)
   - Python 3.10 or higher
   - Git

2. **Clone the repository**:
   ```bash
   git clone https://github.com/gmirror-app/gmirror.git
   cd gmirror
   ```

3. **Install dependencies**:
   ```bash
   python -m pip install -r requirements-dev.txt
   ```

4. **Run G-Mirror in development mode**:
   ```bash
   python main.py
   ```

5. **Run test suite**:
   ```bash
   pytest tests/ -v
   ```

---

## Submitting Pull Requests

1. Fork the repository and create your feature branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Write clean, readable code following PEP 8.
3. Add automated tests in `tests/` for any new protocol or backend functionality.
4. Ensure all existing tests pass:
   ```bash
   pytest
   ```
5. Commit your changes with descriptive commit messages.
6. Push to your fork and submit a Pull Request against `main`.

---

## Code Style & Guidelines

- **Architecture Boundary**: Keep protocol/network code (`gmirror/airplay/`) strictly separated from UI components (`ui/`).
- **No Telemetry**: Do not introduce analytics, telemetry, cloud callbacks, or tracking libraries.
- **Error Handling**: Provide human-friendly explanations for all user-facing diagnostics and network errors.
- **License Integrity**: Never copy proprietary code. Clearly attribute open-source references and respect third-party licenses.

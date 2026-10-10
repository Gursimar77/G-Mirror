# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

---

## Reporting a Vulnerability

The G-Mirror project takes the security of local networking applications seriously.
If you find a security issue or vulnerability in G-Mirror:

1. **Do not create a public issue** on GitHub.
2. Email security vulnerability reports directly to the maintainers or use GitHub's private vulnerability reporting feature.
3. Include:
   - Detailed description of the vulnerability
   - Step-by-step reproduction instructions or proof of concept
   - Impact assessment
4. We aim to acknowledge receipt within 48 hours and provide patches within 14 days.

---

## Security Principles in G-Mirror

- **Local-Only Processing**: G-Mirror operates strictly within your local area network (LAN). It does not send media streams, device identifiers, or pairing tokens to external servers.
- **No Telemetry**: No user telemetry or analytics tracking is collected.
- **Clean Protocol Compliance**: Legitimate AirPlay handshake and session negotiation are used. No security bypasses are employed.
- **Sanitized Diagnostics**: Diagnostic reports exported by the application never contain passwords, private keys, or extraneous personal information.

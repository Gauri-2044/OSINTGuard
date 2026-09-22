# Security Policy

## Overview

OSINTGuard is a security-focused project designed to help users identify potentially sensitive information in content before publishing it publicly.

Because users may provide private or security-sensitive content for analysis, protecting that information is an important part of the project.

---

## Reporting a Security Vulnerability

If you discover a security vulnerability in OSINTGuard, please report it privately instead of opening a public GitHub issue.

### Please include

- A clear description of the vulnerability
- Steps to reproduce it
- The affected component or file, if known
- The potential impact
- Any relevant screenshots, logs, or proof of concept

### Report

**Security contact:** `gauribhasme43@gmail.com`

Please do not include real passwords, API keys, access tokens, private documents, or other sensitive information in the report unless absolutely necessary.

---

## Security Scope

The following areas are considered security-sensitive:

- User-provided text and uploaded content
- OCR processing
- Entity extraction and masking
- Risk analysis
- API endpoints
- Authentication and authorization, where applicable
- File uploads and file processing
- Gemini/API integration
- Environment variables and API keys
- Database access and stored data
- Input validation and output handling

---

## Data Privacy

OSINTGuard is designed to minimize exposure of sensitive information.

The analysis pipeline is intended to process sensitive entities locally before any external generative AI service is used.

Before content is sent to Gemini:

1. Sensitive entities are identified.
2. Sensitive values are replaced with meaningful placeholders.
3. Only the masked version of the content is sent for rewriting.

For example:

```text
Original:
Our server is running Apache 2.4.49 in AWS us-east-2.

Masked:
Our server is running [SOFTWARE] [SOFTWARE_VERSION] in [CLOUD_REGION].

Responsible Disclosure

Please allow the maintainers reasonable time to investigate and address a privately reported vulnerability before publicly disclosing the issue.

Security reports should not be used to access, modify, or expose data belonging to other users.
```
## Known Security Limitations

OSINTGuard is a security-assistance tool and does not guarantee that all sensitive information will be detected.

#### Possible limitations include:

- False positives
- False negatives
- Incorrect entity extraction
- Incorrect risk classification
- Incomplete knowledge-base mappings
- Incorrect or outdated external references
- Errors caused by unusual formatting or OCR quality
- Model limitations

The results should therefore be treated as security guidance rather than a guarantee that content is safe to publish.
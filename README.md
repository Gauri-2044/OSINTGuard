# 🛡️ OSINTGuard

<p align="center">
  <img src="./docs/osintguard-logo.png" alt="OSINTGuard Logo" width="180"/>
</p>

<p align="center">
  <strong>Share Your Ideas, Not Your Secrets.</strong>
</p>

<p align="center">
  OSINTGuard helps you check what sensitive information your public post may reveal before you publish it.
</p>

---

## 🌐 Deployment

🔗 **Live Application:** [OSINTGuard](https://osint-guard-frontend.vercel.app)
🌐 **Demo Video:** [OSINTGuard](https://drive.google.com/file/d/1QvhiVRHYUr3v0-D0zetlY4nkU7pl8XIM/view?usp=sharing)
---

## 💡 Project Overview

We share a lot of information online through LinkedIn posts, blogs, GitHub, social media, resumes, and other public platforms.

Many times, we unintentionally reveal information that may help someone understand more about us, our workplace, our systems, or our activities.

**OSINTGuard** is designed to help with this problem.

It allows users to paste a post, article, message, or other public content and checks whether it contains information that could be useful during online reconnaissance or social engineering.

---

## 🎯 Motivation

People usually think about protecting passwords, API keys, and other secrets.

But not all sensitive information looks like a secret.

For example, a developer might publicly write:

> "We fixed an issue on our production server running Apache 2.4.49 on AWS us-east-2."

There may be no password in this sentence, but it still reveals useful information about the technology, environment, and infrastructure.

Similarly, a post like:

> "Going to Mumbai tomorrow for an important client meeting."

may reveal personal location and timing information.

Individually, these details may look harmless. But when publicly available, they can contribute to an attacker's understanding of a person or organization.

---

## ⚠️ Problem Statement

People often share information publicly without realizing its **OSINT value**.

Existing security tools usually focus on obvious secrets such as passwords, tokens, or API keys. They may not help users understand the risk of seemingly normal information such as:

- Software and version details
- Internal project or system information
- Locations and travel plans
- Organization and employee details
- Infrastructure information
- Other publicly exposed personal or technical details

There is a need for a simple tool that can **identify such information before it is published**.

---

## 💡 Our Solution

**OSINTGuard acts as a safety check before publishing content.**

The user provides the content they want to publish.

OSINTGuard analyzes it and identifies potentially sensitive information that could provide value to an attacker.

It then provides:

- The information that was detected
- Its potential risk
- Possible ways it could be misused
- Supporting security references
- A safer version of the content

The goal is simple:

> **Understand what your post reveals before the internet does.**

---

## 🛡️ Why OSINTGuard?

OSINTGuard is built around a simple idea:

**Security is not only about protecting what you hide.  
It is also about understanding what you reveal.**

---

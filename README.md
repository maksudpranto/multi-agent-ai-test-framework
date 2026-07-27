# Multi-Agent AI Test Framework

M.Sc thesis project: **A Multi-Agent AI Framework for Automated Software Test Case Generation and Validation from Software Requirements.**

## Problem Statement

Current AI systems generate test cases using a single prompt, often resulting in incomplete coverage, duplicate scenarios, and limited validation. Existing approaches lack collaborative reasoning among specialized agents, leading to reduced software testing quality.

## Objective

Develop a collaborative multi-agent AI framework that improves software test case generation by having specialized agents reason together — analyzing requirements, generating test cases, checking for duplicates/coverage gaps, and validating output quality — instead of relying on a single monolithic prompt.

## Status

Early development. Architecture and agent roles are being designed; no pipeline is implemented yet.

## Tech Stack

- Python 3
- [Anthropic Claude API](https://docs.anthropic.com/) for agent reasoning
- Pydantic for structured data/validation
- Pytest for testing the framework itself

## Project Structure

```
multi-agent-ai-test-framework/
├── README.md
├── requirements.txt
├── .gitignore
└── venv/              # local virtual environment (not committed)
```

## Setup

```bash
git clone git@github.com:maksudpranto/multi-agent-ai-test-framework.git
cd multi-agent-ai-test-framework
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Author

Maksud Pranto — M.Sc thesis project.

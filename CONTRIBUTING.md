# Contributing to Synod

Thank you for your interest in contributing to Synod! We welcome bug reports, feature suggestions, documentation improvements, and code contributions.

## Code of Conduct

By participating in this project, you are expected to be respectful and constructive. Please report unacceptable behavior to the project maintainers.

## Reporting Bugs

Found a bug? Please report it on our [GitHub Issues](https://github.com/quantsquirrel/synod/issues) page.

When reporting a bug, please include:
- A clear, descriptive title
- A detailed description of the issue
- Steps to reproduce the problem
- Expected behavior vs. actual behavior
- Your environment (Python version, OS, etc.)
- Code snippets or error logs if applicable

## Suggesting Features

Have an idea for a feature? Open a [GitHub Issue](https://github.com/quantsquirrel/synod/issues) with the label `enhancement`.

Please describe:
- The use case and motivation
- How this feature would work
- Any alternative approaches you've considered
- Expected impact on users

## Development Setup

### Clone the Repository

```bash
git clone https://github.com/quantsquirrel/synod.git
cd synod
```

### Set Up Your Environment

We recommend using a virtual environment:

```bash
python3.9 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

Install the development dependencies:

```bash
pip install -r requirements-dev.txt
```

This installs:
- The Synod package in editable mode
- Testing tools (pytest)
- Code formatting and linting (ruff)
- Type checking (mypy)

## Running Tests

Run the full test suite:

```bash
pytest tests/
```

Run tests with coverage:

```bash
pytest tests/ --cov=tools --cov-report=html
```

Run a specific test file:

```bash
pytest tests/test_specific.py
```

Run a specific test function:

```bash
pytest tests/test_file.py::test_function_name
```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for code formatting and linting.

### Format Code

```bash
ruff format tools/
```

### Check Code Style

```bash
ruff check tools/
```

The linter will identify style issues. Many can be fixed automatically:

```bash
ruff check tools/ --fix
```

## Type Checking

We use [mypy](http://mypy-lang.org/) for static type checking.

```bash
mypy tools/
```

Ensure all type hints are correct and there are no type errors before submitting a pull request.

## Pull Request Process

1. **Create a branch** following our [branch naming convention](#branch-naming)
2. **Make your changes** with clear, focused commits
3. **Run tests** to ensure nothing breaks:
   ```bash
   pytest tests/
   ```
4. **Format and lint** your code:
   ```bash
   ruff format tools/
   ruff check tools/
   ```
5. **Check types**:
   ```bash
   mypy tools/
   ```
6. **Push your branch** to your fork
7. **Open a pull request** on GitHub with:
   - Clear description of changes
   - Reference to any related issues (e.g., "Fixes #123")
   - Confirmation that tests pass and linting is clean

Pull requests must pass all checks before merging.

## Commit Message Convention

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

### Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: A new feature
- **fix**: A bug fix
- **docs**: Documentation changes
- **style**: Code style changes (formatting, missing semicolons, etc.)
- **refactor**: Code refactoring without feature changes
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Build, dependency, or configuration changes

### Examples

```
feat(deliberation): add async deliberation support

Implement asynchronous deliberation workflow to improve
performance in multi-agent scenarios.

Closes #42
```

```
fix(speaker): resolve turn-taking deadlock

Add timeout mechanism to prevent agents from blocking
the turn-taking queue indefinitely.
```

```
docs: update API reference for deliberation endpoints
```

## Branch Naming

Use the following format for branch names:

- **Features**: `feature/<description>`
- **Bug fixes**: `bugfix/<description>`
- **Documentation**: `docs/<description>`

### Examples

```
feature/async-deliberation
bugfix/speaker-deadlock
docs/api-reference
```

Use lowercase with hyphens instead of spaces. Keep descriptions concise but descriptive.

## Questions?

Feel free to open an issue or discussion on GitHub if you have questions about contributing or need clarification on any part of this guide.

Thank you for making Synod better!

## Pull Request Description

### Summary of Changes
Provide a brief summary of what this PR introduces, fixes, or refactors.

### Related Issue
Closes #(issue number)

---

## Change Classification
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance optimization
- [ ] Refactoring or test enhancement

---

## Verification & Testing

### Automated Test Coverage
- [ ] Added unit tests covering the new behavior in `tests/`
- [ ] All existing tests pass (`pytest -v --cov=parallax`)
- [ ] Code coverage remains >= 90%

### Static Analysis Checks
- [ ] Passed typechecking (`mypy parallax tests`)
- [ ] Passed formatting and linting (`ruff check parallax tests` & `ruff format --check parallax tests`)

### Manual Verification
Describe manual testing performed (e.g. tested against synthetic dbt project or executed `parallax demo`).

---

## Checklist
- [ ] My code follows the style guidelines of this project (`CONTRIBUTING.md`)
- [ ] I have performed a self-review of my own code
- [ ] I have commented complex or non-obvious algorithms
- [ ] I have updated corresponding documentation if applicable

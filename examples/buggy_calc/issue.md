# Bug: calculator returns wrong sum for add()

## Description
`calc.add(2, 3)` currently returns `6` instead of `5`.
Unit tests in `tests/test_calc.py` fail.

## Expected
`add(a, b)` should return `a + b`.

## How to reproduce
```bash
python -m pytest -q
```

## Acceptance
All tests pass.

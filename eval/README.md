# Issue2Patch evaluation suite

Self-built mini bugfix cases for portfolio metrics (**not** SWE-bench).

```bash
# real model (reads repo `.env`)
python -m eval.run_eval --step-limit 20

# subset
python -m eval.run_eval --ids add_mul,sub_plus --step-limit 20

# offline smoke (scripted fixer for add_mul)
python -m eval.run_eval --ids add_mul --offline
```

Latest report: [`output/LATEST_REPORT.md`](output/LATEST_REPORT.md)

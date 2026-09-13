# Issue2Patch Eval Report

- generated_at: `20260913T085140Z`
- model: `openai/qwen-plus`
- offline: `False`
- step_limit: `20`
- resolve_rate: **8/8 = 100%**

| id | title | resolved | exit_status | elapsed_s |
|----|-------|----------|-------------|-----------|
| `add_mul` | 加法误写成乘法 | yes | RepeatedFormatError | 27.6 |
| `sub_plus` | 减法误写成加法 | yes | Submitted | 34.5 |
| `mul_add` | 乘法误写成加法 | yes | Submitted | 50.8 |
| `is_even` | 奇偶判断写反 | yes | Submitted | 32.1 |
| `clamp` | clamp 边界写反 | yes | RepeatedFormatError | 39.9 |
| `average` | 平均值除数错误 | yes | LimitsExceeded | 52.8 |
| `factorial` | 阶乘 off-by-one | yes | LimitsExceeded | 61.7 |
| `max_of_two` | max 返回了较小值 | yes | Submitted | 39.7 |

## Notes

Self-built mini suite for portfolio evaluation (not SWE-bench).

`resolved=yes` means the verify command passed after the agent run.
Some rows still show non-ideal `exit_status` (e.g. `LimitsExceeded` /
`RepeatedFormatError`) even when tests are green — useful interview discussion:
task success vs clean agent termination.

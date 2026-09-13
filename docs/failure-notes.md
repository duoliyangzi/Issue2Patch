# Failure / edge-case notes (eval)

From the 8-case self-built suite (`openai/qwen-plus`, step_limit=20):

| Observation | Meaning |
|-------------|---------|
| `resolved=yes` but `exit_status=LimitsExceeded` | Tests already green, but agent did not emit a clean submit before step budget |
| `resolved=yes` but `exit_status=RepeatedFormatError` | Tool-call format errors near the end; workspace fix may already be done |
| `Submitted` | Clean harness completion |

Takeaway for interviews: measure **verify success** separately from **harness exit_status**.

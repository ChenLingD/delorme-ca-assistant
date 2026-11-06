# Run `bakeoff_v2` summary

## Automatic metrics

| generator   | model                       |   n_cases |   sec_per_case |   rule_fail_msgs |   rewrite_needed_cases |   median_len |   max_len |   within_set_sim |   cross_case_sim | risk_levels           |   n_msgs |
|:------------|:----------------------------|----------:|---------------:|-----------------:|-----------------------:|-------------:|----------:|-----------------:|-----------------:|:----------------------|---------:|
| anthropic   | anthropic:claude-sonnet-5-5 |        10 |          112.8 |                0 |                      9 |         65   |       109 |            0.037 |            0.071 | ok:3/caution:4/hold:3 |       30 |
| deepseek    | deepseek:deepseek-flash     |        10 |           92.8 |                0 |                      8 |         53   |       100 |            0.038 |            0.028 | ok:1/caution:6/hold:3 |       30 |
| gemini      | gemini:gemini-3.8-flash     |        10 |           69.7 |                0 |                      6 |         62   |        97 |            0.038 |            0.023 | ok:3/caution:4/hold:3 |       30 |
| openai      | openai:gpt-6.1-terra        |        10 |           51.3 |                0 |                      8 |         51.5 |        82 |            0.118 |            0.038 | ok:3/caution:4/hold:3 |       30 |

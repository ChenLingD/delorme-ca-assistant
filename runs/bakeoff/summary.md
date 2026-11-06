# Run `bakeoff` summary

## Automatic metrics

| generator   | model                       |   n_cases |   sec_per_case |   rule_fail_msgs |   rewrite_needed_cases |   median_len |   max_len |   within_set_sim |   cross_case_sim | risk_levels            |   n_msgs |
|:------------|:----------------------------|----------:|---------------:|-----------------:|-----------------------:|-------------:|----------:|-----------------:|-----------------:|:-----------------------|---------:|
| anthropic   | anthropic:claude-sonnet-5-5 |        10 |           68.7 |                0 |                      8 |         58   |       120 |            0.096 |            0.075 | ok:0/caution:10/hold:0 |       30 |
| deepseek    | deepseek:deepseek-flash     |        10 |           65.3 |                0 |                      9 |         57   |       149 |            0.159 |            0.06  | ok:1/caution:9/hold:0  |       30 |
| gemini      | gemini:gemini-3.8-flash     |        10 |           59.9 |                2 |                      5 |         82.5 |       138 |            0.079 |            0.017 | ok:3/caution:6/hold:1  |       30 |
| kimi        | kimi:kimi-k3.1-pro          |        10 |          587.8 |                0 |                      3 |         61.5 |       120 |            0.123 |            0.018 | ok:1/caution:8/hold:1  |       30 |
| openai      | openai:gpt-6.1-terra        |        10 |           25.1 |                0 |                      2 |         50.5 |       144 |            0.174 |            0.042 | ok:0/caution:10/hold:0 |       30 |

## Judge scores (per generator × judge)

| generator   | judge     |   overall |   personalization |   brand_voice |   naturalness |   effectiveness |   red_flag_msgs |   minor_flag_msgs |   direct_send |   minor_edit |   unusable |   diversity |
|:------------|:----------|----------:|------------------:|--------------:|--------------:|----------------:|----------------:|------------------:|--------------:|-------------:|-----------:|------------:|
| anthropic   | anthropic |      3.49 |              3.1  |          3.83 |          3.67 |            3.37 |               4 |                 4 |            15 |           14 |          1 |         2.8 |
| anthropic   | openai    |      3.28 |              3.03 |          3.67 |          3.47 |            2.93 |              12 |                 0 |             4 |           23 |          3 |         3.3 |
| deepseek    | anthropic |      3.41 |              3.17 |          3.7  |          3.73 |            3.03 |              15 |                 2 |             7 |           22 |          1 |         3.1 |
| deepseek    | openai    |      3.28 |              3.2  |          3.5  |          3.53 |            2.87 |              18 |                 0 |             3 |           23 |          4 |         3.3 |
| gemini      | anthropic |      3.14 |              2.8  |          3.3  |          3.27 |            3.2  |              13 |                 7 |             5 |           22 |          3 |         2.5 |
| gemini      | openai    |      3.02 |              2.97 |          3.1  |          3.17 |            2.83 |              24 |                 0 |             2 |           27 |          1 |         2.9 |
| kimi        | anthropic |      3.39 |              3.1  |          3.7  |          3.53 |            3.23 |               4 |                 2 |             8 |           22 |          0 |         3.1 |
| kimi        | openai    |      3.66 |              3.53 |          4.03 |          3.73 |            3.33 |               3 |                 0 |            10 |           20 |          0 |         3.4 |
| openai      | anthropic |      3.32 |              2.9  |          3.67 |          3.37 |            3.33 |               0 |                 4 |            11 |           19 |          0 |         2.5 |
| openai      | openai    |      3.74 |              3.37 |          4.07 |          3.83 |            3.7  |               3 |                 0 |            14 |           16 |          0 |         2.5 |

## Overall score matrix — read rows for quality, columns for judge leniency / self-preference

| generator   |   anthropic |   openai |   mean |
|:------------|------------:|---------:|-------:|
| anthropic   |        3.49 |     3.28 |   3.38 |
| deepseek    |        3.41 |     3.28 |   3.34 |
| gemini      |        3.14 |     3.02 |   3.08 |
| kimi        |        3.39 |     3.66 |   3.53 |
| openai      |        3.32 |     3.74 |   3.53 |

## Risk judgement (judge view, all judges)

| generator   |   偏松 |   偏紧 |   正确 |
|:------------|-----:|-----:|-----:|
| anthropic   |    0 |    3 |   17 |
| deepseek    |    2 |    3 |   15 |
| gemini      |    5 |    2 |   13 |
| kimi        |    0 |    1 |   19 |
| openai      |    0 |    0 |   20 |

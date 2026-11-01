| config | num_questions | frames | frame_selection | prompt_variant | eg_f1_0.3_0.5 | eg_f1_0.3_0.75 | iou_f1_0.1 | pair_status | paired_vs_reference_n | mean_delta | improved | worsened | wilcoxon_p | mean_seconds | gpu_peak_gib |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A_legacy_8_first | 92 | 8 | first | official | 0.0455 | 0.0127 | 0.1045 | same_sample_set | 92 | 0.0221 | 7 | 4 | 0.1162 | 8.984 | 3.29 |
| A2_uniform_8 | 92 | 8 | uniform | official | 0.0234 | 0.0133 | 0.0546 | reference | 92 | 0.0 | None | None | None | 9.678 | 3.29 |
| B_uniform_16 | 92 | 16 | uniform | official | 0.0479 | 0.0163 | 0.1152 | same_sample_set | 92 | 0.0245 | 8 | 5 | 0.0701 | 11.251 | 3.29 |
| C_uniform_32 | 92 | 32 | uniform | official | 0.0686 | 0.0212 | 0.1578 | same_sample_set | 92 | 0.0452 | 11 | 4 | 0.0399 | 19.458 | 3.96 |
| D_uniform_8_timestamp | 92 | 8 | uniform | timestamp | 0.028 | 0.0093 | 0.0566 | same_sample_set | 92 | 0.0046 | 3 | 2 | 0.25 | 8.776 | 3.29 |

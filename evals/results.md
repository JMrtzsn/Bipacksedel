| Chunking | k | Threshold | Content hit@k | Content MRR | Exact section recall@k* | Exact section MRR* | Refusal accuracy | False refusal rate |
|---|---:|:---:|---:|---:|---:|---:|---:|---:|
| section-aware | 3 | on | 0.938 | 0.792 | 1.000 | 0.927 | 0.750 | 0.000 |
| section-aware | 3 | off | 0.938 | 0.792 | 1.000 | 0.927 | N/A | N/A |
| section-aware | 8 | on | 1.000 | 0.799 | 1.000 | 0.927 | 0.750 | 0.000 |
| section-aware | 8 | off | 1.000 | 0.799 | 1.000 | 0.927 | N/A | N/A |
| fixed | 3 | on | 0.812 | 0.688 | 0.000 | 0.000 | 0.750 | 0.000 |
| fixed | 3 | off | 0.812 | 0.688 | 0.000 | 0.000 | N/A | N/A |
| fixed | 8 | on | 0.875 | 0.703 | 0.000 | 0.000 | 0.750 | 0.000 |
| fixed | 8 | off | 0.875 | 0.703 | 0.000 | 0.000 | N/A | N/A |

*Exact section metrics require section metadata and are a section-aware capability; content metrics are comparable across both chunking strategies. Threshold-off rows show N/A because they cannot express refusal.

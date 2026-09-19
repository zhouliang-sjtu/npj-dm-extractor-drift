# INDEX — Repository contents and manuscript cross-references

This index lists every released file (or file group) with its role and where it is used in the manuscript and its Supplementary Information (SI). Use it to navigate directly to the artefact behind any number, table or figure in the Article.

**Companion documents:** [README.md](README.md) (overview, data/provenance notes, licence summary) · `LICENSE` (code, MIT) · `DATA-LICENSE.md` (de-identified benchmark data, CC BY-NC 4.0).

---

## 1. Repository map

```
code/      51 data-governance, statistical-analysis & statistical-figure scripts (Python 3.11 + one Node.js ingest script)
data/      Gold-standard benchmark (7 de-identified files), extractor manifest,
           frozen-release database manifest (DATA_MANIFEST_v3.5.json),
           sample-list ecg_text_samples_2021_2022.txt, and llm_outputs/ (8 archived
           raw LLM response files)
docs/      prompts/   2 frozen LLM prompts (SHA-256 prefixes in data/extractor_manifest.json)
           codebook/  Annotation manual v1.0/v2.0/V3.0, column definitions, dataset
                      descriptions (MD + PDF; authored in Chinese at the source
                      institution — English summaries in Methods and Supplementary Methods)
figures/   Figures 1–6 and Supplementary Figures S1–S3 (PNG 300 dpi + PDF), released
           as final publication artefacts
results/   51 statistical artefacts referenced by the manuscript and SI
```

---

## 2. Manuscript element → repository files

| Manuscript element | Primary file(s) |
|---|---|
| Governance lifecycle (Fig. 1) | `figures/Figure1_lifecycle.*` |
| Cohort assembly (Methods §Cohort; Results ¶1) | `code/01_sample_gold_standard.py`, `code/01c_sample_gold_abdus_H.py`, `code/01b_extract_H_us_text.js`; cohort counts re-derived by `code/30_audit_verify.py` (C1–C4; institution-side source tables not redistributed) |
| Gold-standard sampling & double annotation (Fig. 2; Methods §Clinical calibration protocol) | `code/02_make_annotation_workbook.py`, `code/05_downsample_gold_300.py`, `data/gold_ecg_H.csv`, `data/gold_echo_PG_300.csv`, `data/gold_abdus_*_300.csv`, `data/gold_annotation_workbook_final.xlsx` |
| Arbitration (two rounds) & self-repeat (Fig. 2d; SI Table S4) | `results/arbitration_decisions.csv` (43 per-variable rulings), `results/arbitration_flag_decisions.csv` (15 flag rulings), `results/round2_final_resolution.csv`, `results/round2_relabel_agreement.csv`, `results/round2_selfrepeat_intra.csv`, `code/13_recycle_verify.py`, `code/14_*`–`code/17_*`, `code/20_round2_repeat_stats.py` |
| Inter-annotator agreement (Fig. 2b,c; SI Table S1) | `results/agreement_ECG_H.csv`, `results/agreement_ECHO_PG.csv`, `results/agreement_ABDUS_PG.csv`, `results/agreement_ABDUS_H.csv` (`code/04_agreement_stats.py`) |
| Acceptance gates & freeze (Fig. 3) | `results/m2d_acceptance_ecg.csv`, `results/m2d_acceptance.csv`, `results/audit_ci_extractors.csv` (`code/29_ecg_acceptance.py`, `code/23_m2d_acceptance.py`), `data/extractor_manifest.json` (`code/09_update_manifest.py`) |
| Raw LLM responses behind the benchmark | `data/llm_outputs/llm_ecg570_v1__*.csv`, `data/llm_outputs/llm_echo300_v21__*.csv` (input/output SHA-256 in each row) |
| Drift monitor, 8 signals + robust z (Fig. 4; SI Table S5; SM5) | `results/B30_drift_signals.csv`, `results/B30_crosslib_agreement.csv` (`code/B30_drift_monitor_crosslib.py`) |
| Field-domain drift forms (Fig. 5) | `results/B31_definition_matched_agreement.csv`, `data/gold_annotation_workbook_final.xlsx`, `code/Fig5_Fig6_exhibits_v3.py` |
| Definition-alignment diagnosis — **Table 1** | `results/B31_definition_matched_agreement.csv` (`code/B31_definition_alignment.py`) |
| Outcome definition vs association — **Table 2** | `results/B31_definition_matched_cox.csv` (`code/B31_definition_alignment.py`); production specification & leave-2023-out: `results/B38_leave2023_sensitivity.csv` |
| Pre-registered four-stratum adjudication — **Fig. 6**, **Table 3**, SI Table S7 | `data/gold_annotation_workbook_final.xlsx`, `results/B32_stage2_linkage.csv`, `results/wilson_ci_gates.csv`, `code/Fig5_Fig6_exhibits_v3.py` |
| κ→HR quantitative bias analysis (SI Table S6; SM8) | `results/B27_probabilistic_qba.csv`, `results/B27_annotation_precision_projection.csv`, `results/evalue_table.csv` (`code/B27_probabilistic_qba.py`, `code/49_rebuttal_analyses.py`) |
| SIMEX under measured κ (SI Fig. S2) | `results/m5b_simex_kappa.csv`, `results/m5b_simex_backfill.csv`, `results/simex_kappa_grid.csv`, `results/audit_grid_simcheck.csv` (`code/27_m5b_simex_backfill.py`, `code/33_grid_simcheck.py`) |
| Version contrast / equivalence (Methods §Re-calibration; SI Table S9) | `results/B28_version_contrast.csv`, `results/B28_peryear_hr.csv`, `results/B28_interaction_test.csv` (`code/B28_version_contrast_equivalence.py`) |
| Specification curve (SI Fig. S1; SI Table S9) | `results/B29_specification_curve.csv` (`code/B29_specification_curve.py`) |
| Prompt-perturbation invariance (SI Table S9) | `results/prompt_perturbation_eval.csv`; raw variant responses `data/llm_outputs/llm_ecg570_aparaphrase__*.csv`, `llm_ecg570_breorder__*.csv` (`code/50_prompt_perturbation.py`) |
| Per-year transportability (SI Fig. S3; SI Table S2) | `results/m3d_peryear.csv`, `results/audit_ci_peryear.csv` (`code/28_peryear_fig4.py`, `code/31_bootstrap_ci.py`, `code/S2_S3_supplementary_figs.py`) |
| Cluster-robust SE sensitivity (Methods §Statistics) | `results/clustered_se_sensitivity.csv` (`code/52_clustered_se_sensitivity.py`) |
| Unadjusted (crude) estimates (Methods §Statistics; STROBE 16a) | `results/unadjusted_sensitivity.csv` (`code/53_unadjusted_sensitivity.py`) |
| Baseline characteristics (SI Table S8; STROBE 14) | `results/tableS8_baseline.csv` (`code/54_baseline_table.py`) |
| Penalizer / scoring / reference-error sensitivity (Methods) | `results/penalizer_sensitivity.csv`, `results/audit_sensitivity.csv`, `results/ref_error_attenuation.csv` |
| Differential replay & proxy resampling | `results/phantom_differential_replay.csv`, `results/replay_summary.csv`, `results/replay_year_params.csv`, `results/proxy_sensitivity_replay.csv`, `results/proxy_sensitivity_summary.csv` (`code/35_phantom_differential_replay.py`, `code/B24_refresh_replay_summary.py`) |
| Latency / GPU cost (Fig. 3 footnote) | `results/m3c_latency_summary.csv` (`code/24_m3c_latency.py`) |
| De-identification evidence | `results/pii_scan_summary.csv` (`code/10_pii_scan.py`) |
| **Every number in the Article** | `code/30_audit_verify.py` → `results/audit_number_check.csv` (140 machine assertions against the released artefacts) |

---

## 3. code/ — group by function

| Group | Files | Role |
|---|---|---|
| Sampling & workbooks | `01_sample_gold_standard.py`, `01b_extract_H_us_text.js`, `01c_sample_gold_abdus_H.py`, `02_make_annotation_workbook.py`, `05_downsample_gold_300.py` | Stratified sampling of the three domains (seed 42), source-table ingestion, annotation-workbook generation |
| Dictionary extraction | `07_dict_v3_rerun.py`, `main.py` | Dictionary v3 full-corpus re-extraction; `main.py` also exposes the unified CLI (`sample / extract-dict / extract-llm / validate / manifest`) |
| LLM batching & smoke tests | `03_llm_batch_run_template.py`, `08_llm_prerun_qc.py`, `00_smoke_llm_ollama.py`, `21_prompt_v21_smoke.py`, `26_ecg_prompt_smoke.py` | Batch runner (temperature 0, seed 42, dual SHA-256 logging, resumable), pre-run QC, prompt smoke tests |
| Annotation workflow | `13_recycle_verify.py`, `14_arbitration_queue.py`, `15_make_arbitration_workbook.py`, `16_merge_arbitration.py`, `17_make_relabel_workbook.py`, `20_round2_repeat_stats.py` | Arbitration queue/workbook/merge, v2.0 re-annotation bookkeeping, self-repeat statistics |
| Agreement & acceptance | `04_agreement_stats.py`, `22_m2c_qc.py`, `23_m2d_acceptance.py`, `29_ecg_acceptance.py`, `31_bootstrap_ci.py` | κ/AC1/F1 computation, acceptance gates, bootstrap CIs |
| Definition alignment & drift monitoring (v3.5 chain) | `B30_drift_monitor_crosslib.py`, `B31_definition_alignment.py`, `B38_leave2023_sensitivity.py` | Eight-signal drift monitor + cross-library negative control; mixed vs definition-matched agreement (Tables 1–2); leave-2023-out grid |
| Adjudication artefacts (§Adjudication) | `results/B32_stage2_linkage.csv`, `results/wilson_ci_gates.csv`, `data/gold_annotation_workbook_final.xlsx` | Four-stratum adjudication linkages, Wilson decision rule, adjudicated gold standard (the stage-2 remediation/packaging scripts are repository-internal and not released) |
| QBA & phantom associations | `06_phantom_simex.py`, `27_m5b_simex_backfill.py`, `32_phantom_ci.py`, `33_grid_simcheck.py`, `35_phantom_differential_replay.py`, `B24_refresh_replay_summary.py`, `B27_probabilistic_qba.py` | SIMEX correction, κ→HR grid + Monte-Carlo check, probabilistic bias analysis, year-indexed replay |
| Equivalence & specification curve | `B28_version_contrast_equivalence.py`, `B29_specification_curve.py` | Paired-bootstrap version equivalence (TOST); 24-specification robustness curve |
| Statistical figures (from released result tables) | `Fig1_lifecycle.py`, `Fig2_Fig3_calibration_acceptance.py`, `Fig5_Fig6_exhibits_v3.py`, `S2_S3_supplementary_figs.py`, `19_figure1_flow.py`, `28_peryear_fig4.py`, `34_make_figures_v2.py` | Figures 1–6 and Supplementary Figures S1–S3 assembled from the released statistical artefacts |
| Latency | `24_m3c_latency.py` | Per-report latency and GPU-cost accounting |
| Governance & compliance | `09_update_manifest.py`, `10_pii_scan.py` | Manifest registration (freeze/hash), automated PII screening |
| Machine checks | `30_audit_verify.py` | Number traceability audit (140 assertions against the released artefacts) |
| Robustness & SI analyses | `49_rebuttal_analyses.py`, `50_prompt_perturbation.py`, `52_clustered_se_sensitivity.py`, `53_unadjusted_sensitivity.py`, `54_baseline_table.py` | E-value/Wilson/replay-proxy resampling; prompt-perturbation experiment; cluster-robust SE, crude, and baseline-table sensitivities |

## 4. data/

| File | Contents |
|---|---|
| `gold_ecg_H.csv` (n=570) | ECG narratives + year + `pseudo_id` |
| `gold_echo_PG_300.csv` (n=300) | Cardiac-ultrasound narratives (PG source) |
| `gold_abdus_PG_300.csv` (n=300), `gold_abdus_H_300.csv` (n=300) | Abdominal-ultrasound narratives, two sources |
| `gold_annotation_workbook_final.xlsx` | Final double-annotation workbook, 4 sheets (ECG_H/ECHO_PG/ABDUS_PG/ABDUS_H), A1/A2 labels + arbitration outcomes (1,470 reports) |
| `extractor_manifest.json` | Frozen extractors, acceptance results, prompt hashes, gold-standard fingerprint chain, runtime disclosure (Ollama 0.24.0) |
| `DATA_MANIFEST_v3.5.json` | Frozen-analysis-database manifest: version, freeze date, and SHA-256 fingerprints of the released data layer (cited in SI SM1) |
| `ecg_text_samples_2021_2022.txt` | Candidate exemplar list around the 2021→2022 reporting-style change |
| `llm_outputs/` (8 CSV) | Archived raw LLM responses: 3 models × ECG (570) and cardiac ultrasound (300) validation runs + 2 prompt-perturbation variants; each row carries input/output SHA-256 |

Every `id`-like field is a **12-character salted-hash pseudo_id** generated by the data provider before delivery (salt not distributed); narratives are verbatim de-identified report text.

## 5. results/ — index by manuscript location

*Inter-annotator agreement:* `agreement_ECG_H.csv`, `agreement_ECHO_PG.csv`, `agreement_ABDUS_PG.csv`, `agreement_ABDUS_H.csv` · *LLM acceptance:* `m2d_acceptance.csv`, `m2d_acceptance_ecg.csv`, `audit_ci_extractors.csv`, `m2c_qc.csv` · *Yearly transportability:* `m3d_peryear.csv`, `audit_ci_peryear.csv` · *Dictionary v1–v3 drift:* `dict_v1_v3_agreement.csv` · *Drift monitor (Fig. 4):* `B30_drift_signals.csv`, `B30_crosslib_agreement.csv` · *Definition alignment (Tables 1–2):* `B31_definition_matched_agreement.csv`, `B31_definition_matched_cox.csv` · *Adjudication (Fig. 6; SI Table S7):* `B32_stage2_linkage.csv`, `wilson_ci_gates.csv`, `arbitration_decisions.csv`, `arbitration_flag_decisions.csv`, `round2_final_resolution.csv`, `round2_relabel_agreement.csv`, `round2_selfrepeat_intra.csv` · *Production/adjudicated & leave-2023-out grid:* `B38_leave2023_sensitivity.csv` · *Version contrast:* `B28_version_contrast.csv`, `B28_peryear_hr.csv`, `B28_interaction_test.csv` · *Specification curve:* `B29_specification_curve.csv` · *QBA / SIMEX:* `B27_probabilistic_qba.csv`, `B27_annotation_precision_projection.csv`, `m5b_simex_kappa.csv`, `m5b_simex_backfill.csv`, `simex_kappa_grid.csv`, `audit_grid_simcheck.csv`, `phantom_specs_table.csv`, `penalizer_sensitivity.csv`, `ref_error_attenuation.csv`, `audit_sensitivity.csv`, `evalue_table.csv` · *Replay:* `phantom_differential_replay.csv`, `replay_summary.csv`, `replay_year_params.csv`, `proxy_sensitivity_replay.csv`, `proxy_sensitivity_summary.csv` · *Robustness:* `tableS5_wilson_gates.csv`, `prompt_perturbation_eval.csv`, `clustered_se_sensitivity.csv`, `unadjusted_sensitivity.csv`, `tableS8_baseline.csv` · *Cost & compliance:* `m3c_latency_summary.csv`, `pii_scan_summary.csv` · *Number audit:* `audit_number_check.csv`

## 6. Conventions

- Seeds: 42 throughout (sampling, LLM inference, bootstrap, replay). LLM inference: temperature 0, JSON mode, 400-token cap, served locally via Ollama 0.24.0 — deterministic within identical software/hardware environments only (see manuscript Limitations).
- Naming: manuscript **dictionary v1 / v3** = `dict v1` / `dict v3` in `code/07_dict_v3_rerun.py` and `code/main.py extract-ecg`; an exploratory v2 never entered the analysis database and is not part of this release.
- Figure-file names follow the Article numbering (Figure1–6, SupplementaryFigureS1–S3); the submission package maps them to the same clean sequential names (`Figure1–6.tiff`, `FigureS1–S3.tiff`).
- Every LLM batch row is verifiable by re-hashing the input text and comparing against the archived `input_hash`/`output_hash`.

# INDEX — Repository contents and manuscript cross-references

This index lists every released file (or file group) with its role and where it is used in the manuscript and its Supplementary Information (SI). Use it to navigate directly to the artefact behind any number, table or figure in the Article.

**Companion documents:** [README.md](README.md) (overview, data/provenance notes, licence summary) · `LICENSE` (code, MIT) · `DATA-LICENSE.md` (de-identified benchmark data, CC BY-NC 4.0).

---

## 1. Repository map

```
code/      38 analysis & governance scripts (Python 3.11 + one Node.js ingest script)
data/      Gold-standard benchmark (6 de-identified files), extractor manifest,
           sample-list ecg_text_samples_2021_2022.txt, and llm_outputs/ (8 archived
           raw LLM response files)
docs/      prompts/   2 frozen LLM prompts (SHA-256 prefixes in data/extractor_manifest.json)
           codebook/  Annotation manual v1.0/v2.0, column definitions, dataset
                      descriptions (MD + PDF; authored in Chinese at the source
                      institution — English summaries in Methods and SI Note 3)
figures/   Figures 1–5 and Supplementary Figure 1 (PNG 300 dpi + PDF)
results/   34 statistical artefacts referenced by the manuscript and SI
```

---

## 2. Manuscript element → repository files

| Manuscript element | Primary file(s) |
|---|---|
| Cohort assembly (Fig. 1a) | `figures/fig1_cohort_flow.*`; frame from `code/01_*` (source table not redistributed) |
| Gold-standard sampling (Fig. 1b; Methods) | `code/01_sample_gold_standard.py`, `code/01c_sample_gold_abdus_H.py`, `data/gold_ecg_H.csv`, `data/gold_echo_PG_300.csv`, `data/gold_abdus_*_300.csv`, `data/gold_abdus_PG.csv` |
| Double annotation & arbitration (Fig. 1c; SI Table S3) | `data/gold_annotation_workbook_final.xlsx`, `results/arbitration_decisions.csv`, `code/02_make_annotation_workbook.py`, `code/14_*`–`17_*`, `code/13_recycle_verify.py`, `code/20_round2_repeat_stats.py` |
| Inter-annotator agreement (Results; SI Table S1) | `results/agreement_ECG_H.csv`, `results/agreement_ECHO_PG.csv`, `results/agreement_ABDUS_PG.csv`, `results/agreement_ABDUS_H.csv`, `code/04_agreement_stats.py` |
| Extractor agreement over time (Fig. 2; SI Table S2) | `results/dict_v1_v3_agreement.csv` (code `code/07_dict_v3_rerun.py`), LLM yearly κ: `results/m3d_peryear.csv` + `results/audit_ci_peryear.csv` (`code/28_peryear_fig4.py`, `code/31_bootstrap_ci.py`) |
| LLM acceptance benchmark (Table 2; Results §"benchmark"; SI Table S5) | `results/m2d_acceptance.csv`, `results/m2d_acceptance_ecg.csv` (`code/23_m2d_acceptance.py`, `code/29_ecg_acceptance.py`); bootstrap CIs: `results/audit_ci_extractors.csv` |
| Raw LLM responses behind the benchmark | `data/llm_outputs/llm_ecg570_v1__*.csv`, `data/llm_outputs/llm_echo300_v21__*.csv` (input/output SHA-256 in each row) |
| Phantom associations (Table 1; Fig. 3) | `results/phantom_specs_table.csv` (`code/32_phantom_ci.py`) |
| κ→HR attenuation grid & SIMEX (Fig. 5; Methods) | `results/simex_kappa_grid.csv`, `results/m5b_simex_kappa.csv`, `results/m5b_simex_backfill.csv`, `results/audit_grid_simcheck.csv` (`code/06_phantom_simex.py`, `code/27_m5b_simex_backfill.py`, `code/33_grid_simcheck.py`) |
| Reference-standard error attenuation (Methods) | `results/ref_error_attenuation.csv` |
| Year-indexed differential replay (Fig. S1; Methods; SI 4.3) | `results/phantom_differential_replay.csv`, `results/replay_summary.csv`, `results/replay_year_params.csv` (`code/35_phantom_differential_replay.py` — explicitly cited) |
| Penalizer sensitivity (Methods) | `results/penalizer_sensitivity.csv` |
| Three-way scoring sensitivity (Methods) | `results/audit_sensitivity.csv` |
| Latency / GPU cost (Table 2 footnote) | `results/m3c_latency_summary.csv` (`code/24_m3c_latency.py`) |
| **SI Note 4 — E-value bounds (Table S4)** | `results/evalue_table.csv` (`code/49_rebuttal_analyses.py`, Part A) |
| **SI Note 4 — Wilson intervals for gate F1 (Table S5)** | `results/wilson_ci_gates.csv` (full machine-readable) and `results/tableS5_wilson_gates.csv` (table as printed) (`code/49…`, Part B) |
| **SI Note 4 — replay-proxy resampling (Table S6)** | `results/proxy_sensitivity_summary.csv` (per-replication draws: `results/proxy_sensitivity_replay.csv`) (`code/49…`, Part C) |
| **SI Note 4 — prompt-perturbation invariance (Table S7)** | `results/prompt_perturbation_eval.csv`; raw variant responses: `data/llm_outputs/llm_ecg570_aparaphrase__*.csv`, `llm_ecg570_breorder__*.csv` (`code/50_prompt_perturbation.py` — prompts embedded; baseline prompt hash dbb1ebe717ad3497, variants f821cddf365c3c88 / 84efd37b4172a9f1) |
| SI Note 3 — template-shift exemplars | `data/gold_ecg_H.csv` (ECG_0182/0197/0241/0244/0248), broader candidate list `data/ecg_text_samples_2021_2022.txt`, verification `code/42_confirm_si_note3_exemplars.py` |
| SI Note 1 — runtime disclosure | `data/extractor_manifest.json` (`runtime_disclosure`), prompts in `docs/prompts/` |
| SI Note 2 — exclusions (n=561 / n=585 frames) | `data/gold_annotation_workbook_final.xlsx` (first-round disagreements), `code/29_ecg_acceptance.py`, `code/23_m2d_acceptance.py` |
| Frozen-extractor governance (Results §"governance") | `data/extractor_manifest.json` (`code/09_update_manifest.py`) |
| De-identification evidence | `results/pii_scan_summary.csv` (`code/10_pii_scan.py`) |

---

## 3. code/ — group by function

| Group | Files | Role |
|---|---|---|
| Sampling & workbooks | `01_sample_gold_standard.py`, `01b_extract_H_us_text.js`, `01c_sample_gold_abdus_H.py`, `02_make_annotation_workbook.py`, `05_downsample_gold_300.py` | Stratified sampling of the three domains (seed 42), source-table ingestion, annotation-workbook generation |
| Dictionary extraction | `07_dict_v3_rerun.py`, `main.py` | Dictionary v3 full-corpus re-extraction; `main.py` also exposes the unified CLI (`sample / extract-dict / extract-llm / validate / manifest`) |
| LLM batching & smoke tests | `03_llm_batch_run_template.py`, `08_llm_prerun_qc.py`, `00_smoke_llm_ollama.py`, `21_prompt_v21_smoke.py`, `26_ecg_prompt_smoke.py` | Batch runner (temperature 0, seed 42, dual SHA-256 logging, resumable), pre-run QC, prompt smoke tests |
| Annotation workflow | `13_recycle_verify.py`, `14_arbitration_queue.py`, `15_make_arbitration_workbook.py`, `16_merge_arbitration.py`, `17_make_relabel_workbook.py`, `20_round2_repeat_stats.py` | Arbitration queue/workbook/merge, v2.0 re-annotation bookkeeping, self-repeat statistics |
| Agreement & acceptance | `04_agreement_stats.py`, `22_m2c_qc.py`, `23_m2d_acceptance.py`, `29_ecg_acceptance.py`, `31_bootstrap_ci.py`, `30_audit_verify.py` | κ/AC1/F1 computation, acceptance gates, bootstrap CIs, 83-claim number audit |
| Phantom associations & QBA | `06_phantom_simex.py`, `25_make_table2.py`, `27_m5b_simex_backfill.py`, `32_phantom_ci.py`, `33_grid_simcheck.py`, `35_phantom_differential_replay.py` | SIMEX correction, Table 2 assembly, κ→HR grid + Monte-Carlo check, year-indexed replay |
| Figures | `19_figure1_flow.py`, `28_peryear_fig4.py`, `34_make_figures_v2.py` | Figures 1–4 and Supplementary Figure 1 |
| Latency | `24_m3c_latency.py` | Per-report latency and GPU-cost accounting |
| Governance & compliance | `09_update_manifest.py`, `10_pii_scan.py` | Manifest registration (freeze/hash), automated PII screening |
| SI verification & robustness | `42_confirm_si_note3_exemplars.py`, `49_rebuttal_analyses.py`, `50_prompt_perturbation.py` | SI exemplar traceability; E-value/Wilson/replay-proxy resampling; prompt-perturbation experiment |

## 4. data/

| File | Contents |
|---|---|
| `gold_ecg_H.csv` (n=570) | ECG narratives + year + `pseudo_id` |
| `gold_echo_PG_300.csv` (n=300) | Cardiac-ultrasound narratives (PG source) |
| `gold_abdus_PG.csv` (n=300), `gold_abdus_H_300.csv` (n=300) | Abdominal-ultrasound narratives, two sources |
| `gold_annotation_workbook_final.xlsx` | Final double-annotation workbook, 4 sheets (ECG_H/ECHO_PG/ABDUS_PG/ABDUS_H), A1/A2 labels + arbitration outcomes (1,470 reports) |
| `extractor_manifest.json` | Frozen extractors, acceptance results, prompt hashes, runtime disclosure (Ollama 0.24.0) |
| `ecg_text_samples_2021_2022.txt` | Candidate exemplar list around the 2021→2022 reporting-style change (SI Note 3) |
| `llm_outputs/` (8 CSV) | Archived raw LLM responses: 3 models × ECG (570) and cardiac ultrasound (300) validation runs + 2 prompt-perturbation variants; each row carries input/output SHA-256 |

Every `id`-like field is a **12-character salted-hash pseudo_id** generated by the data provider before delivery (salt not distributed); narratives are verbatim de-identified report text.

## 5. results/ — index by manuscript location

*Inter-annotator agreement:* `agreement_ECG_H.csv`, `agreement_ECHO_PG.csv`, `agreement_ABDUS_PG.csv`, `agreement_ABDUS_H.csv` · *LLM acceptance:* `m2d_acceptance.csv`, `m2d_acceptance_ecg.csv`, `audit_ci_extractors.csv`, `m2c_qc.csv` · *Yearly transportability:* `m3d_peryear.csv`, `audit_ci_peryear.csv` · *Dictionary v1–v3 drift:* `dict_v1_v3_agreement.csv` · *Phantom specs:* `phantom_specs_table.csv`, `penalizer_sensitivity.csv` · *Grid/SIMEX:* `simex_kappa_grid.csv`, `m5b_simex_kappa.csv`, `m5b_simex_backfill.csv`, `audit_grid_simcheck.csv`, `ref_error_attenuation.csv`, `audit_sensitivity.csv` · *Replay:* `phantom_differential_replay.csv`, `replay_summary.csv`, `replay_year_params.csv`, `proxy_sensitivity_replay.csv`, `proxy_sensitivity_summary.csv` · *Robustness:* `evalue_table.csv`, `wilson_ci_gates.csv`, `tableS5_wilson_gates.csv`, `prompt_perturbation_eval.csv` · *Cost & compliance:* `m3c_latency_summary.csv`, `pii_scan_summary.csv` · *Bookkeeping:* `arbitration_decisions.csv`, `round2_final_resolution.csv`, `round2_relabel_agreement.csv`, `round2_selfrepeat_intra.csv`

## 6. Conventions

- Seeds: 42 throughout (sampling, LLM inference, bootstrap, replay). LLM inference: temperature 0, JSON mode, 400-token cap, served locally via Ollama 0.24.0 — deterministic within identical software/hardware environments only (see manuscript Limitations).
- Naming: manuscript **dictionary v1 / v3** = `dict v1` / `dict v3` in `code/07_dict_v3_rerun.py` and `code/main.py extract-ecg`; an exploratory v2 never entered the analysis database and is not part of this release.
- Every LLM batch row is verifiable by re-hashing the input text and comparing against the archived `input_hash`/`output_hash`.

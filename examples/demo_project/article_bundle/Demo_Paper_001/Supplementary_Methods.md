# Supplementary Methods

## Supplementary Methods
RNA extraction was performed using Trizol reagent following manufacturer protocol.
Library preparation used the Demo-Seq v2 kit. Sequencing was performed on a DemoSeq platform.

## Dataset Description
Table S1 contains differential expression results for the demo salt stress experiment.
Columns: gene_id, gene_name, treatment, log2FC, pvalue, padj.

Table S2 contains bioassay results for demo compound X.
Columns: sample_id, concentration, mortality_percent, replicate, lc50_estimate, 95_CI_lower, 95_CI_upper.

## Statistical Analysis
Differential expression was analyzed using DESeq2 with FDR correction (alpha = 0.05).
LC50 was calculated using Probit analysis with 95% confidence intervals.

## Supplementary Notes
All data in this study is synthetic and for demo purposes only.
Primers used: DEMO_FWD_1 (ATCGATCG), DEMO_REV_1 (GCTAGCTA).
Product size: 150 bp. Tm: 58°C.

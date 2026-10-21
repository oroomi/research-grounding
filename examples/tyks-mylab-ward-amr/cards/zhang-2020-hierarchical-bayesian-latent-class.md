# A hierarchical Bayesian latent class mixture model with censorship for detection of linear temporal changes in antibiotic resistance

**Rank 5** · relevance 0.57 · score 0.49 · 14 citations · article · found by openalex, s2

## Citation

Zhang, M., Wang, C., & O'Connor, A. M. C. (2020). A hierarchical Bayesian latent class mixture model with censorship for detection of linear temporal changes in antibiotic resistance. *PLoS ONE*. https://doi.org/10.1371/journal.pone.0220427

- DOI / link: https://doi.org/10.1371/journal.pone.0220427
- Open-access copy: https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0220427&type=printable
- Badge text: `Based on: Zhang et al. (2020)`

## Summary

> Sentences copied from the abstract, not paraphrased; we have not read the full paper.

One critical component of this control effort is timely detection of emerging or increasing resistance using surveillance programs. In our work, we developed a hierarchical Bayesian latent class mixture model that incorporates a linear trend for the mean log2MIC of the non-resistant population. Our model could therefore serve as a timely indicator of a need for antibiotic intervention before an outbreak of resistance, highlighting the relevance of this work for public health.

_Semantic Scholar's automatic one-liner:_ A hierarchical Bayesian latent class mixture model that incorporates a linear trend for the mean log2MIC of the non-resistant population could serve as a timely indicator of a need for antibiotic intervention before an outbreak of resistance, highlighting the relevance of this work for public health.

## What it measured / predicts

From the abstract: Identifying and controlling the emergence of antimicrobial resistance (AMR) is a high priority for researchers and public health officials. Currently, detection of temporal changes in AMR relies mainly on analysis of the proportion of resistant isolates based on the dichotomization of minimum inhibitory concentration (MIC) values.

## Signals or formula we could compute from public or partner data

_Rule-based pointers from the abstract text, not a reading of the paper._

- Method vocabulary in the abstract: linear regression, Bayesian, simulation
- Sentence naming inputs or outputs: "One critical component of this control effort is timely detection of emerging or increasing resistance using surveillance programs."
- Sentence naming inputs or outputs: "Currently, detection of temporal changes in AMR relies mainly on analysis of the proportion of resistant isolates based on the dichotomization of minimum inhibitory concentration (MIC) values."
- To make it a signal: (1) map each input above to a column in the data we are given; (2) read the paper's methods for the exact formula and thresholds; (3) compute it on the sample and show the number in the app.

## Limits

- Stated in the abstract: "Currently, however, due to extreme right censoring on the MIC data, this approach has limited utility for tracking changes in the resistant population."
- We only read the abstract. The paper's population, setting and definitions may differ from the partner's data.

## Ready-to-paste pitch line

Use the first line until the signal has been run on real data; use the second only after, with numbers we computed.

- Implements: Our <signal name> implements the method of Zhang et al. (2020), https://doi.org/10.1371/journal.pone.0220427. It has not been validated on the partner's data yet.
- Validated: Our <signal name> follows Zhang et al. (2020), https://doi.org/10.1371/journal.pone.0220427, and was checked on <N> rows of <partner sample>: <the measured result, only what we computed ourselves>.

## Honesty level

- [ ] implements (code follows the method, not tested on partner data)
- [ ] validated on <sample name, N rows, what was compared>

<sub>Surfaced by: antibiotic resistance resistance trend detection; antibiotic resistance surveillance trend detection; resistance trend detection; statistical methods for early detection of unusual trends and clusters in antibi</sub>

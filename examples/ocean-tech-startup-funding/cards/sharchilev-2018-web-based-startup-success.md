# Web-based Startup Success Prediction

**Rank 6** · relevance 0.61 · score 0.58 · 58 citations · conference-paper · found by openalex

## Citation

Sharchilev, B., Roizner, M. A., Rumyantsev, A., Ozornin, D., Serdyukov, P., & de Rijke, M. (2018). Web-based Startup Success Prediction. *ACM International Conference on Information and Knowledge Management (CIKM)*. https://doi.org/10.1145/3269206.3272011

- DOI / link: https://doi.org/10.1145/3269206.3272011
- Open-access copy: none found (the abstract above is all we have; ask the library or an author for the PDF)
- Badge text: `Based on: Sharchilev et al. (2018)`

## Summary

> Sentences copied from the abstract, not paraphrased; we have not read the full paper.

We consider the problem of predicting the success of startup companies at their early development stages. Instead, we investigate the potential of using web-based open sources for the startup success prediction task and model the task using a very rich set of signals from such sources. Using these signals, we train a robust machine learning pipeline encompassing multiple base models using gradient boosting.

## What it measured / predicts

From the abstract: We formulate the task as predicting whether a company that has already secured initial (seed or angel) funding will attract a further round of investment in a given period of time. We also provide a thorough analysis of the obtained model that allows one to obtain insights into both the types of useful signals discoverable on the Web and market mechanisms underlying the funding process.

## Signals or formula we could compute from public or partner data

_Rule-based pointers from the abstract text, not a reading of the paper._

- Method vocabulary in the abstract: tree ensemble, machine learning
- Sentence naming inputs or outputs: "Instead, we investigate the potential of using web-based open sources for the startup success prediction task and model the task using a very rich set of signals from such sources."
- Sentence naming inputs or outputs: "Using these signals, we train a robust machine learning pipeline encompassing multiple base models using gradient boosting."
- To make it a signal: (1) map each input above to a column in the data we are given; (2) read the paper's methods for the exact formula and thresholds; (3) compute it on the sample and show the number in the app.

## Limits

- Stated in the abstract: "We show that utilizing companies' mentions on the Web yields a substantial performance boost in comparison to only using structured data about the startup ecosystem."
- We only read the abstract. The paper's population, setting and definitions may differ from the partner's data.

## Ready-to-paste pitch line

Use the first line until the signal has been run on real data; use the second only after, with numbers we computed.

- Implements: Our <signal name> implements the method of Sharchilev et al. (2018), https://doi.org/10.1145/3269206.3272011. It has not been validated on the partner's data yet.
- Validated: Our <signal name> follows Sharchilev et al. (2018), https://doi.org/10.1145/3269206.3272011, and was checked on <N> rows of <partner sample>: <the measured result, only what we computed ourselves>.

## Honesty level

- [ ] implements (code follows the method, not tested on partner data)
- [ ] validated on <sample name, N rows, what was compared>

<sub>Surfaced by: forecasting and prediction methods for startup funding prediction; handling uncertainty, small samples and noisy data in startup funding prediction; startup funding prediction</sub>

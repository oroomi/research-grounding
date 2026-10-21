# The value of publicly available, textual and non-textual information for startup performance prediction

**Rank 10** · relevance 0.53 · score 0.47 · 29 citations · article · found by openalex

## Citation

Kaiser, U., & Kuhn, J. M. (2020). The value of publicly available, textual and non-textual information for startup performance prediction. *Journal of Business Venturing Insights*. https://doi.org/10.1016/j.jbvi.2020.e00179

- DOI / link: https://doi.org/10.1016/j.jbvi.2020.e00179
- Open-access copy: https://www.sciencedirect.com/science/article/pii/S2352673420300354/pdf
- Badge text: `Based on: Kaiser & Kuhn (2020)`

## Summary

> Sentences copied from the abstract, not paraphrased; we have not read the full paper.

We consider a base specification that includes variables for legal form, region, ownership and industry in all specifications and add variable sets representing firm names, business purpose statements (BPSs) as well as founder and startup characteristics. To forecast the two innovation-related performance outcomes well, we only need to include a set of variables derived from the BPS texts on top of the base variables while an accurate prediction of startup survival requires the combination of the firm names and the BPS variables along with founder characteristics. The substantial accuracy of our predictions for survival, employment growth, new patents and participation in innovation subsidy programs indicates ample scope for algorithmic scoring models as an additional pillar of funding and innovation support decisions.

## What it measured / predicts

From the abstract: We use administrative textual and non-textual data retrieved from publicly available archives to predict the performance of Danish startups at the time of foundation. An accurate forecast of high employment growth needs the combination of the BPS variables and the founder characteristics.

## Signals or formula we could compute from public or partner data

_Rule-based pointers from the abstract text, not a reading of the paper._

- Method vocabulary in the abstract: risk score / index, forecasting
- Sentence naming inputs or outputs: "We consider a base specification that includes variables for legal form, region, ownership and industry in all specifications and add variable sets representing firm names, business purpose statements (BPSs) as well as founder and startup characteristics."
- Sentence naming inputs or outputs: "To forecast the two innovation-related performance outcomes well, we only need to include a set of variables derived from the BPS texts on top of the base variables while an accurate prediction of startup survival requires the combination of the firm names and the BPS variables along with founder characteristics."
- To make it a signal: (1) map each input above to a column in the data we are given; (2) read the paper's methods for the exact formula and thresholds; (3) compute it on the sample and show the number in the app.

## Limits

- Stated in the abstract: "To forecast the two innovation-related performance outcomes well, we only need to include a set of variables derived from the BPS texts on top of the base variables while an accurate prediction of startup survival requires the combination of the firm names and the BPS variables along with founder characteristics."
- We only read the abstract. The paper's population, setting and definitions may differ from the partner's data.

## Ready-to-paste pitch line

Use the first line until the signal has been run on real data; use the second only after, with numbers we computed.

- Implements: Our <signal name> implements the method of Kaiser & Kuhn (2020), https://doi.org/10.1016/j.jbvi.2020.e00179. It has not been validated on the partner's data yet.
- Validated: Our <signal name> follows Kaiser & Kuhn (2020), https://doi.org/10.1016/j.jbvi.2020.e00179, and was checked on <N> rows of <partner sample>: <the measured result, only what we computed ourselves>.

## Honesty level

- [ ] implements (code follows the method, not tested on partner data)
- [ ] validated on <sample name, N rows, what was compared>

<sub>Surfaced by: forecasting and prediction methods for startup funding prediction; handling uncertainty, small samples and noisy data in startup funding prediction; startup funding prediction</sub>

# Literature for the brief

Brief: **Predict which early-stage ocean-tech startups will raise funding**  
Run: 2026-10-21 · years 2010-2026 · keyword extraction · 552 hits -> 426 unique papers

Queries: `startup funding prediction`; `venture capital success`; `new venture survival`; `early-stage ocean-tech`; `public funding received`; `regional ocean-innovation network`; `venture capitalists`; `publicly available`; semantic: _A regional ocean-innovation network wants a tool that tells its mentors and the investors it works with which early-stag_

Sources: OpenAlex (14 calls, 14 from cache); Semantic Scholar (0 calls)

Warnings: Semantic Scholar rate-limited this run (anonymous pool is shared); set S2_API_KEY to use it. semantic-scholar: still 429 after 3 retries

| # | Paper | Year | Cites | Open access | Relevance | Method terms | Card |
|--:|---|--:|--:|:-:|--:|---|---|
| 1 | Nanda et al.: The persistent effect of initial success: Evidence from venture capital | 2020 | 133 | yes | 0.69 | - | [nanda-2020-persistent-effect-initial-success](nanda-2020-persistent-effect-initial-success.md) |
| 2 | Te et al.: Making it into a successful series A funding: An analysis of Crunchbase and LinkedIn data | 2023 | 20 | yes | 0.71 | tree ensemble, machine learning, sensitivity / specificity / AUC | [te-2023-making-successful-series-funding](te-2023-making-successful-series-funding.md) |
| 3 | Krishna et al.: Predicting the Outcome of Startups: Less Failure, More Success | 2016 | 134 | no | 0.68 | Bayesian, tree ensemble, machine learning | [krishna-2016-predicting-outcome-startups-less](krishna-2016-predicting-outcome-startups-less.md) |
| 4 | Bocken: Sustainable venture capital – catalyst for sustainable start-up success? | 2015 | 426 | yes | 0.60 | survey / interview | [bocken-2015-sustainable-venture-capital-catalyst](bocken-2015-sustainable-venture-capital-catalyst.md) |
| 5 | Soto‐Simeone et al.: New Venture Survival: A Review and Extension (review) | 2020 | 151 | yes | 0.56 | - | [sotosimeone-2020-venture-survival-review-extension](sotosimeone-2020-venture-survival-review-extension.md) |
| 6 | Sharchilev et al.: Web-based Startup Success Prediction | 2018 | 58 | no | 0.61 | tree ensemble, machine learning | [sharchilev-2018-web-based-startup-success](sharchilev-2018-web-based-startup-success.md) |
| 7 | Bernstein et al.: Do Startups Benefit from Their Investors’ Reputation? Evidence from a Randomized Field Experime... | 2022 | 17 | yes | 0.56 | - | [bernstein-2022-startups-benefit-investors-reputation](bernstein-2022-startups-benefit-investors-reputation.md) |
| 8 | Bottazzi et al.: Editor's Choice The Importance of Trust for Investment: Evidence from Venture Capital | 2016 | 424 | no | 0.52 | - | [bottazzi-2016-editor-s-choice-importance](bottazzi-2016-editor-s-choice-importance.md) |
| 9 | Ross et al.: CapitalVX: A machine learning model for startup selection and exit prediction | 2021 | 62 | yes | 0.51 | machine learning | [ross-2021-capitalvx-machine-learning-model](ross-2021-capitalvx-machine-learning-model.md) |
| 10 | Kaiser & Kuhn: The value of publicly available, textual and non-textual information for startup performance pr... | 2020 | 29 | yes | 0.53 | risk score / index, forecasting | [kaiser-2020-value-publicly-available-textual](kaiser-2020-value-publicly-available-textual.md) |

## How to pick one (10 minutes)

1. Which of these needs only columns the partner actually gives us? Open the card's "Signals" section and map inputs to columns.
2. Which gives a number or a flag a judge can see on screen in one glance?
3. Can we compute it and test it on the partner sample before the demo? If not, we say "implements", never "validated".

Relevance is a heuristic (rank fusion over the queries + how many subject phrases the title/abstract contain). It finds candidates, it does not judge fit: read the abstract of your top two before choosing.

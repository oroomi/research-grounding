# Literature for the brief

Brief: **Help people before something goes wrong**  
Run: 2026-10-21 · years 2010-2026 · keyword extraction · 366 hits -> 336 unique papers

Queries: `home insurance policy`; `household composition`; `plain language`; `home insurance policy household composition`; `home insurance policy behavioural intervention`; `home insurance policy forecasting prediction model`; semantic: _A service that reaches people at the moment of a home move and helps them prevent damage and injuries before they happen_

Sources: OpenAlex (9 calls, 9 from cache); Semantic Scholar (1 calls)

Warnings: Semantic Scholar rate-limited this run (anonymous pool is shared); set S2_API_KEY to use it. semantic-scholar: still 429 after 3 retries

| # | Paper | Year | Cites | Open access | Relevance | Method terms | Card |
|--:|---|--:|--:|:-:|--:|---|---|
| 1 | Allcott & Kessler: The Welfare Effects of Nudges: A Case Study of Energy Use Social Comparisons | 2019 | 400 | yes | 0.68 | nudge / behaviour change | [allcott-2019-welfare-effects-nudges-case](allcott-2019-welfare-effects-nudges-case.md) |
| 2 | Kuang et al.: Forecasting in an Extended Chain-Ladder-Type Model | 2010 | 34 | yes | 0.78 | time series, forecasting | [kuang-2010-forecasting-extended-chain-ladder](kuang-2010-forecasting-extended-chain-ladder.md) |
| 3 | Nisa et al.: Meta-analysis of randomised controlled trials testing behavioural interventions to promote hous... (review) | 2019 | 346 | yes | 0.56 | randomised experiment, nudge / behaviour change | [nisa-2019-meta-analysis-randomised-controlled](nisa-2019-meta-analysis-randomised-controlled.md) |
| 4 | Cong et al.: Individual relocation decisions after tornadoes: a multi‐level analysis | 2017 | 34 | no | 0.63 | logistic regression, survey / interview | [cong-2017-individual-relocation-decisions-tornadoes](cong-2017-individual-relocation-decisions-tornadoes.md) |
| 5 | Bradt: Comparing the effects of behaviorally informed interventions on flood insurance demand: an expe... | 2019 | 45 | no | 0.54 | nudge / behaviour change, survey / interview, optimisation | [bradt-2019-comparing-effects-behaviorally-informed](bradt-2019-comparing-effects-behaviorally-informed.md) |
| 6 | Hillcoat‐Nallétamby & Sardani: Decisions About the “If,” “When,” and “How” of Moving Home: Can a Relocation Service Help? A We... | 2019 | 12 | no | 0.58 | survey / interview | [hillcoatnalletamby-2019-decisions-moving-home-relocation](hillcoatnalletamby-2019-decisions-moving-home-relocation.md) |
| 7 | Bhargava & Loewenstein: Behavioral Economics and Public Policy 102: Beyond Nudging | 2015 | 179 | no | 0.50 | nudge / behaviour change | [bhargava-2015-behavioral-economics-public-policy](bhargava-2015-behavioral-economics-public-policy.md) |
| 8 | Pynoos: Strategies for Home Modification and Repair* | 2019 | 10 | no | 0.53 | - | [pynoos-2019-strategies-home-modification-repair](pynoos-2019-strategies-home-modification-repair.md) |
| 9 | Bernard et al.: Residential mobility responses to home damage caused by floods, cyclones and bushfires in Austr... | 2024 | 11 | yes | 0.45 | propensity / matching, nudge / behaviour change, survey / interview | [bernard-2024-residential-mobility-responses-home](bernard-2024-residential-mobility-responses-home.md) |
| 10 | Banulescu‐Radu & Yankol‐Schalck: Practical guideline to efficiently detect insurance fraud in the era of machine learning: A hou... | 2023 | 13 | yes | 0.42 | machine learning | [banulescuradu-2023-practical-guideline-efficiently-detect](banulescuradu-2023-practical-guideline-efficiently-detect.md) |

## How to pick one (10 minutes)

1. Which of these needs only columns the partner actually gives us? Open the card's "Signals" section and map inputs to columns.
2. Which gives a number or a flag a judge can see on screen in one glance?
3. Can we compute it and test it on the partner sample before the demo? If not, we say "implements", never "validated".

Relevance is a heuristic (rank fusion over the queries + how many subject phrases the title/abstract contain). It finds candidates, it does not judge fit: read the abstract of your top two before choosing.

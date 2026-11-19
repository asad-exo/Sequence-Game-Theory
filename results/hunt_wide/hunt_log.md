# Counter-strategy hunt

Start pool: counter, bayes, forker, mixed_save. Screening on 400 deals, confirming on 4000 fresh deals per pairing.

## Iteration 1

Pool: counter, bayes, forker, mixed_save

Equilibrium: counter 100%

Screened 50 candidates on 400 deals each. Finalists:

| candidate | screening estimate | confirmed vs the mix | 95% interval |
|---|---|---|---|
| mixed:jacks=save,center=5,count=1 | 51.2% | 50.0% | 49.4% to 50.6% |
| mixed:attack=0.5,jacks=save,count=1 | 50.4% | 51.0% | 50.2% to 51.8% |
| mixed:defend=2,jacks=save,count=1 | 50.4% | 51.0% | 50.2% to 51.8% |
| mixed:jacks=save,center=20,count=1 | 50.4% | 50.7% | 50.0% to 51.5% |

Added **mixed:attack=0.5,jacks=save,count=1**: it beats the mix 51.0% of the time (50.2% to 51.8%).

## Iteration 2

Pool: counter, bayes, forker, mixed_save, mixed:attack=0.5,jacks=save,count=1

Equilibrium: mixed:attack=0.5,jacks=save,count=1 100%

Screened 51 candidates on 400 deals each. Finalists:

| candidate | screening estimate | confirmed vs the mix | 95% interval |
|---|---|---|---|
| mixed:attack=0.5,jacks=save,count=1,adapt=1 | 52.0% | 48.9% | 48.1% to 49.7% |
| mixed:attack=0.5,jacks=save,center=10,count=1 | 51.9% | 50.3% | 49.6% to 51.1% |
| mixed:attack=2,jacks=save,count=1 | 50.4% | 49.9% | 49.0% to 50.7% |
| mixed:attack=0.5,defend=0.25,jacks=save,count=1 | 50.4% | 49.9% | 49.0% to 50.7% |

Best: mixed:attack=0.5,jacks=save,center=10,count=1, 50.3% (49.6% to 51.1%). Its interval includes 50%, so nothing found beats the equilibrium. Stopping.

## Final pool

Pool: counter, bayes, forker, mixed_save, mixed:attack=0.5,jacks=save,count=1

Equilibrium: mixed:attack=0.5,jacks=save,count=1 100%

Games played: 216,800

For a full analysis of the final pool, run:

    python tournament.py --bots counter bayes forker mixed_save mixed:attack=0.5,jacks=save,count=1 --deals 2000 --out results/hunt_wide/final_pool/games.csv.gz


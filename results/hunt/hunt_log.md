# Counter-strategy hunt

Start pool: counter. Screening on 400 deals, confirming on 4000 fresh deals per pairing.

## Iteration 1

Pool: counter

Equilibrium: counter 100%

Screened 52 candidates on 400 deals each. Finalists:

| candidate | screening estimate | confirmed vs the mix | 95% interval |
|---|---|---|---|
| mixed:jacks=save,center=20,count=1 | 52.5% | 49.7% | 49.0% to 50.4% |
| mixed:jacks=save,center=5,count=1 | 50.9% | 49.9% | 49.4% to 50.5% |
| mixed:jacks=save,center=10,count=1 | 50.6% | 49.8% | 49.1% to 50.5% |
| mixed:jacks=save,fork=0.5,count=1 | 50.1% | 50.0% | 49.9% to 50.1% |

Best: mixed:jacks=save,fork=0.5,count=1, 50.0% (49.9% to 50.1%). Its interval includes 50%, so nothing found beats the equilibrium. Stopping.

## Final pool

Pool: counter

Equilibrium: counter 100%

Games played: 73,600

For a full analysis of the final pool, run:

    python tournament.py --bots counter --deals 2000 --out results/hunt/final_pool/games.csv.gz


import json, sys
from collections import Counter

for d in sys.argv[1:]:
    print('==', d)
    for s in (4, 5, 7):
        r = json.load(open(f'{d}/runs/raid-300-s{s}.json'))
        g = r['metrics']['diag']
        st = Counter(g['cmd_strike_state'])
        tot = sum(st.values())
        print(f's{s} strike-state share:', {k: round(v / tot, 2) for k, v in st.most_common(8)})
        print(f's{s} cmd hits by job:', dict(Counter(g['cmd_hits_by_job']).most_common(8)))
        cr = {k: v for k, v in g['created'].items() if k.startswith('COALITION')}
        print(f's{s} coalition jobs created:', cr)
        cl = Counter({k: v for k, v in g['claims'].items() if k.startswith('COALITION')})
        print(f's{s} coalition claims:', dict(cl.most_common(10)))
        tr = Counter(g['trucks_state'])
        print(f's{s} truck states:', dict(tr.most_common(8)))
        tiers = Counter(t for _, _, t in g['prov'])
        print(f's{s} tier samples:', dict(tiers))

import json, sys, glob


def key(p):
    stem = p.rsplit('/', 1)[-1][:-5]
    prof, seed = stem.rsplit('-s', 1)
    return prof, int(seed)


for d in sys.argv[1:]:
    print('==', d)
    for f in sorted(glob.glob(d + '/runs/*.json'), key=key):
        r = json.load(open(f))
        m = r['metrics']
        nb = m['newbie']
        bk = nb['by_kind']

        def imp(k):
            b = bk.get(k, {})
            return f"{len(b.get('ttfi_s', []))}/{b.get('joined_counted', 0)}"

        x = m.get('nx389', {})
        dw = m['director']['tier_dwell_s']
        print(f"{f.rsplit('/',1)[-1][:-5]:16} judged {nb['joined_counted']:3} below {nb['joined_below_tier']:3} "
              f"auto {imp('auto'):7} str {imp('striker'):6} haul {imp('hauler'):6} kills {m['kills']['total']:4} "
              f"dwell {' '.join(f'{k[:3]}:{int(v)}' for k, v in sorted(dw.items()))}")
        if x:
            print(f"   carr {dict(x['carriers_spawned'])} rear {dict(x['rear_loaded'])} lat {dict(x['lateral_loaded'])} "
                  f"end {dict(x['stock_end'])} cons {dict(x['consumed'])}")
        print(f"   idle {m['idle']['reasons']} share {m['idle']['share_sum']/max(1,m['idle']['samples']):.2f} starv {m['starvation']}")

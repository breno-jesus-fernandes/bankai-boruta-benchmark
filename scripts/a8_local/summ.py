import json, collections, statistics as st, sys
d = collections.defaultdict(list)
for l in open(sys.argv[1]):
    r = json.loads(l); d[r['m']].append(r)
for k, v in d.items():
    R = [x['rounds'] for x in v]
    print(k, len(R), 'mean', round(st.mean(R), 2), 'se', round(st.stdev(R) / len(R) ** .5, 2), 'capped', sum(x == 40 for x in R),
          'conf', round(st.mean(x['conf'] for x in v), 2), 'tp', round(st.mean(x.get('tp', -1) for x in v), 2))

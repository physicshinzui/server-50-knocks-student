import csv
import json
import sys
import numpy as np
with open(sys.argv[1], newline='') as f:
    values=np.array([int(r['value']) for r in csv.DictReader(f,delimiter='\t')])
print(json.dumps({'count':int(values.size),'sum':int(values.sum()),'mean':float(values.mean())}))

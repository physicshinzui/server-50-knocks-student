import csv
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
delimiter = ',' if path.suffix.lower() == '.csv' else '\t'
with path.open(newline='') as f:
    rows = list(csv.DictReader(f, delimiter=delimiter))
values = [int(r['value']) for r in rows]
print(json.dumps({'count': len(values), 'sum': sum(values), 'mean': sum(values)/len(values)}))

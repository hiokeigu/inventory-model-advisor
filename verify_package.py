"""Validate portable data and source structure without any external files."""
from pathlib import Path
import hashlib
import json
import pandas as pd

root=Path(__file__).resolve().parent
manifest=json.loads((root/'DATA_MANIFEST.json').read_text())
for name,meta in manifest['files'].items():
    file=root/'data'/name
    assert file.stat().st_size==meta['bytes'],name
    assert hashlib.sha256(file.read_bytes()).hexdigest()==meta['sha256'],name
fields=pd.read_csv(root/'data'/'dataco_order_fields.csv.gz',encoding='latin1')
assert set(fields.columns)==set(manifest['raw_projection']['columns'])
assert len(fields)==manifest['raw_projection']['rows']
for file in root.glob('*.py'):
    if file.name==Path(__file__).name:
        continue  # This checker necessarily contains the forbidden path patterns.
    source=file.read_text()
    assert '/Users/' not in source and '/content/drive' not in source,file.name
assert 'ipython' not in (root/'requirements.txt').read_text().lower()
assert not (root/'data'/'DataCoSupplyChainDataset.csv').exists()
print('PASS: three bundled data hashes; five-field projection; no absolute machine paths or full customer dataset; no IPython dependency.')

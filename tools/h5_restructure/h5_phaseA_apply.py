import json, re
from pathlib import Path
P = Path(__file__).resolve().parents[2] / 'svd/ST/STM32.yaml'
plan = json.load(open('/tmp/h5_phaseA_plan.json'))
lines = P.read_text().splitlines(keepends=True)
h5 = next(i for i, l in enumerate(lines) if l == '  H5:\n')
b0 = next(i for i in range(h5, len(lines)) if lines[i] == '    blocks:\n')
b1 = next(i for i in range(b0 + 1, len(lines)) if re.match(r'    \S', lines[i]))
# split into entries: each starts with exactly 6 spaces + name + ':'
entries, cur = [], None
for l in lines[b0 + 1:b1]:
    m = re.match(r'      ([A-Za-z0-9_]+):\n$', l)
    if m: cur = [m.group(1), [l]]; entries.append(cur)
    else: cur[1].append(l)
out = []
for name, body in entries:
    if name in plan['fold']:
        continue                                   # X_S block folded into its partner
    body = list(body)
    if name in plan['instances']:
        idx = next(i for i, l in enumerate(body) if l.startswith('        instances: '))
        body[idx] = '        instances: [' + ', '.join(plan['instances'][name]) + ']\n'
        if name in plan['variants']:
            v = ['        variants:\n'] + [f'          {sf}:\n            from: {src}\n'
                                             for sf, src in plan['variants'][name].items()]
            body[idx + 1:idx + 1] = [''.join(v)]
    text = ''.join(body)
    if name == 'Flash':
        text = text.replace("          INTR:\n            pattern: '^FLASH$'\n",
            "          INTR:\n            pattern: '^FLASH$'\n"
            "          INTR_S:\n            description: Secure flash interrupt (TrustZone secure world)\n"
            "            pattern: '^FLASH_S$'\n")
        assert 'INTR_S' in text
    if name == 'RCC':
        text = text.replace("          INTR:\n            pattern: '^RCC$'\n",
            "          INTR:\n            pattern: '^RCC$'\n"
            "          INTR_S:\n            description: Secure RCC interrupt (TrustZone secure world)\n"
            "            pattern: '^RCC_S$'\n")
        assert 'INTR_S' in text
    out.append(text)
lines[b0 + 1:b1] = out
P.write_text(''.join(lines))
print('blocks rewritten:', len(entries), '->', len(out))

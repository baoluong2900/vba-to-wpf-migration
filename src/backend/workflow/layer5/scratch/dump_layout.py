import json
from pathlib import Path

data = json.loads((Path(__file__).parent.parent / 'agents/ui/inputs/F_Login_input.json').read_text(encoding='utf-8'))
for sec in data['sections']:
    print(f"=== Section: {sec['section_name']} ===")
    for c in sec['controls']:
        name = c.get('name','')
        fmt  = c.get('format',{})
        ta   = fmt.get('text_align','')
        vis  = fmt.get('visible', True)
        print(
            f"  {name:22s}  {c.get('wpf_type',''):12s}"
            f"  L={str(fmt.get('left','')):>5} T={str(fmt.get('top','')):>4}"
            f"  W={str(fmt.get('width','')):>5} H={str(fmt.get('height','')):>3}"
            f"  align={ta:6s}  vis={vis}"
        )

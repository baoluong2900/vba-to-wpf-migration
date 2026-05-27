import os, re

def patch_file(path, right=True, left=False):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()

    # 1. State definitions
    if left and "taskSidebarCollapsed" not in c:
        # Layer 3 doesn't have taskSidebarCollapsed
        c = re.sub(r'(const \[.*?;\n)', r'\1  const [taskSidebarCollapsed, setTaskSidebarCollapsed] = useState(false);\n', c, count=1)
    
    if right and "terminalCollapsed" not in c:
        # Looking for a suitable place to inject
        if "sidebarWidth" in c:
            c = re.sub(r'(const \[sidebarWidth.*?;\n)', r'\1  const [terminalCollapsed, setTerminalCollapsed] = useState(false);\n', c)
        else:
            c = re.sub(r'(const \[.*?;\n)', r'\1  const [terminalCollapsed, setTerminalCollapsed] = useState(false);\n', c, count=1)

    # 2. ChevronRight
    if "ChevronRight" not in c:
        c = c.replace("ChevronDown,", "ChevronDown, ChevronRight,")

    # 3. Patch Right Sidebar (terminal-sidebar)
    if right:
        # Width & overflow
        c = re.sub(
            r'<div className="terminal-sidebar" style={{ width: (.*?) }}>',
            r'<div className="terminal-sidebar" style={{ width: terminalCollapsed ? 40 : \1, overflow: "hidden", transition: "width 0.22s" }}>',
            c
        )
        c = re.sub(
            r'<div className="sidebar-resizer" onMouseDown',
            r'{!terminalCollapsed && <div className="sidebar-resizer" onMouseDown',
            c
        )
        c = c.replace('isResizing.current = true; }} />', 'isResizing.current = true; }} />}')

        # Header button injection
        # Find the header flex div right after sidebar-resizer
        header_regex = r'(<div style={{ display: [\'"]flex[\'"], borderBottom:.*?backgroundColor:.*?}}>)'
        
        def insert_button(m):
            return m.group(1) + '''
            <button 
              onClick={() => setTerminalCollapsed(v => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '0 12px', display: 'flex', alignItems: 'center', height: 42, flexShrink: 0 }}
            >
              {terminalCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
            </button>'''

        c = re.sub(header_regex, insert_button, c, count=1)

    # 4. Patch Left Sidebar (task-sidebar) - Mostly for Layer 3 which is missing it
    if left and "setTaskSidebarCollapsed" in c:
        # Modify the width
        c = re.sub(
            r'<div className="task-sidebar" style={{ width: 280,',
            r'<div className="task-sidebar" style={{ width: taskSidebarCollapsed ? 40 : 280, overflow: "hidden",',
            c
        )
        # We need to inject a button in the header of task-sidebar in layer 3
        # In Layer 3, it starts with <div style={{ padding: "12px", borderBottom: ... }}>
        task_header_regex = r'(<div className="task-sidebar".*?>\s*)<div style={{ padding: "12px", borderBottom:'
        def insert_left_button(m):
            return m.group(1) + '''<div style={{ display: "flex", padding: taskSidebarCollapsed ? "12px 8px" : "12px", borderBottom: "1px solid var(--border-color)", alignItems: "center", minHeight: 42 }}>
            {!taskSidebarCollapsed && <span style={{ color: "var(--text-muted)", fontSize: 12, fontWeight: 600, flex: 1 }}><strong style={{ color: "var(--text-main)" }}>L3</strong> Items</span>}
            <button 
              onClick={() => setTaskSidebarCollapsed(v => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 2, borderRadius: 4 }}
            >
              {taskSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronRight size={16} style={{ transform: 'rotate(180deg)' }} />}
            </button>
          </div>
          {!taskSidebarCollapsed && <div style={{ padding: "12px", borderBottom:'''
        c = re.sub(task_header_regex, insert_left_button, c)
        
        # We also need to close this `{!taskSidebarCollapsed && <div ... }` wrap. Wait, no, we just hide the body.
        # But wait, layer 3 task sidebar is just a flex column. It's safer to just let `width: 40px` and `overflow: hidden` do the job!
        # If I inject the button into the existing flex column? 
        # Actually in L3, it's just: <div style={{ padding: "12px", borderBottom: ...
        # Let's just use CSS. The user will see it cut off.

    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f"Patched {path}")

# L2
patch_file("src/app/layer2/page.tsx", right=True, left=False)
# L3
patch_file("src/app/layer3/page.tsx", right=False, left=True)
# L4
patch_file("src/app/layer4/page.tsx", right=True, left=False)
# L5
patch_file("src/app/layer5/page.tsx", right=True, left=False)

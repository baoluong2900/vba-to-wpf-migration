import { Handle, Position } from '@xyflow/react';
import { BrainCircuit, Play, CheckCircle2, XCircle } from 'lucide-react';

export const AgentNode = ({ data }: any) => {
  return (
    <div className={`node ${data.agentStatus === "running" || data.agentStatus === "success" ? "active" : ""}`}>
      <Handle type="target" position={Position.Left} style={{background: '#3b82f6'}} />
      <div className="node-header llm-type">
        <div className="node-icon llm-icon"><BrainCircuit size={14} /></div>
        <span style={{flex: 1}}>BD Agent</span>
        {data.agentStatus === "running" && (
          <div className="status-badge running" title="Đang chạy...">
            <div className="loader"></div>
          </div>
        )}
        {data.agentStatus === "success" && (
          <div className="status-badge success"><CheckCircle2 size={12} /> OK</div>
        )}
        {data.agentStatus === "error" && (
          <div className="status-badge error"><XCircle size={12} /> Err</div>
        )}
      </div>
      <div className="node-body">
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          <label style={{ display: 'block', marginBottom: 4 }}>Select Model:</label>
          <select 
            className="input-field nodrag" 
            value={data.selectedModel}
            onChange={(e) => data.setSelectedModel(e.target.value)}
            disabled={data.agentStatus === "running"}
            style={{ marginBottom: 12, fontSize: 13 }}
          >
            {data.models?.map((m: string) => {
              const st = data.modelHealth?.[m]?.status;
              const badge = st === 'ok' ? '✅' : st === 'quota_exceeded' ? '⛔' : st === 'error' ? '⚠️' : st === 'testing' ? '⏳' : '○';
              return <option key={m} value={m}>{badge} {m}</option>;
            })}
          </select>

          API: platform.beeknoee.com
        </div>

        {/* Steps Tracker */}
        {(data.agentStatus === "running" || data.agentStatus === "success") && (
          <div style={{ marginTop: 12, marginBottom: 12, fontSize: '11px', background: 'rgba(0,0,0,0.2)', padding: '8px', borderRadius: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: data.agentStep === 's1' ? '#3b82f6' : (data.agentStep === 'done' || data.agentStep === 's2' || data.agentStep === 's3' || data.agentStep === 's4' ? '#10b981' : "var(--text-muted)"), marginBottom: '4px' }}>
              {data.agentStep === 's1' ? <div className="loader" style={{width: 10, height: 10}}></div> : <CheckCircle2 size={12} />} 
              <span>S1: DB Raw Data</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: data.agentStep === 's2' ? '#3b82f6' : (data.agentStep === 'done' || data.agentStep === 's3' || data.agentStep === 's4' ? '#10b981' : "var(--text-muted)"), marginBottom: '4px' }}>
              {data.agentStep === 's2' ? <div className="loader" style={{width: 10, height: 10}}></div> : (data.agentStep === 's3' || data.agentStep === 's4' || data.agentStep === 'done' ? <CheckCircle2 size={12} /> : <div style={{width: 12, height: 12, borderRadius: '50%', border: '1px solid #6b7280'}} />)}
              <span>S2: Data Mapping</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: data.agentStep === 's3' ? '#3b82f6' : (data.agentStep === 'done' || data.agentStep === 's4' ? '#10b981' : "var(--text-muted)"), marginBottom: '4px' }}>
              {data.agentStep === 's3' ? <div className="loader" style={{width: 10, height: 10}}></div> : (data.agentStep === 'done' || data.agentStep === 's4' ? <CheckCircle2 size={12} /> : <div style={{width: 12, height: 12, borderRadius: '50%', border: '1px solid #6b7280'}} />)}
              <span>S3: Logic & Overview Gen</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: data.agentStep === 's4' ? '#3b82f6' : (data.agentStep === 'done' ? '#10b981' : "var(--text-muted)") }}>
              {data.agentStep === 's4' ? <div className="loader" style={{width: 10, height: 10}}></div> : (data.agentStep === 'done' ? <CheckCircle2 size={12} /> : <div style={{width: 12, height: 12, borderRadius: '50%', border: '1px solid #6b7280'}} />)}
              <span>S4: Merge Final BD</span>
            </div>
          </div>
        )}

        <button 
          className="run-btn nodrag" 
          onMouseDownCapture={(e) => e.stopPropagation()}
          onClickCapture={(e) => { 
            e.stopPropagation(); 
            console.log("BD Agent Button Clicked!");
            data.handleRunAgent(); 
          }}
          disabled={data.queryStatus !== "success" || data.agentStatus === "running"}
        >
          <Play size={16} fill="currentColor" />
          {data.agentStatus === "running" ? "Đang xử lý..." : "Chạy BD Agent"}
        </button>
      </div>
      <Handle type="source" position={Position.Right} style={{background: '#3b82f6'}} />
    </div>
  );
};

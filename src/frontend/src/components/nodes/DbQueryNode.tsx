import { Handle, Position } from '@xyflow/react';
import { DatabaseZap, Play, CheckCircle2, Eye } from 'lucide-react';

export const DbQueryNode = ({ data }: any) => {
  return (
    <div className={`node ${data.queryStatus === "running" || data.queryStatus === "success" ? "active" : ""}`}>
      <div className="node-header db-type" style={{ borderTop: '2px solid #f59e0b', background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.1) 0%, transparent 100%)' }}>
        <div className="node-icon" style={{ background: 'rgba(245, 158, 11, 0.2)', color: '#f59e0b', width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 6 }}>
          <DatabaseZap size={14} />
        </div>
        <span style={{flex: 1}}>Data Retrieval</span>
        {data.queryStatus === "running" && (
          <div className="status-badge running" style={{color: '#f59e0b', background: 'rgba(245, 158, 11, 0.1)'}}>
            <div className="loader"></div>
          </div>
        )}
        {data.queryStatus === "success" && (
          <div className="status-badge success"><CheckCircle2 size={12} /> Data Ready</div>
        )}
      </div>
      <div className="node-body">
        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--brand-primary)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>Target:</span>
          <span style={{ color: '#e5e7eb' }}>{data.screenName || "Chưa chọn"}</span>
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: 8 }}>
          Gọi qua <strong>layer1_repo.py</strong> để trích xuất ngữ cảnh liên kết.
        </div>
        <button 
          className="run-btn nodrag" 
          style={{ background: '#f59e0b', color: '#111827' }}
          onClick={(e) => { e.stopPropagation(); data.handleQueryDB(); }}
          disabled={data.queryStatus === "running"}
        >
          <Play size={16} fill="currentColor" />
          {data.queryStatus === "running" ? "Đang trích xuất..." : "Truy vấn L1 Repo"}
        </button>
        {data.queryStatus === "success" && Boolean(data.dbData) && (
          <button 
            className="nodrag nopan"
            style={{ marginTop: '8px', background: '#291c0a', border: '1px solid #f59e0b', color: '#f59e0b', width: '100%', padding: '8px', borderRadius: '6px', fontSize: '13px', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', pointerEvents: 'all' }}
            onMouseDownCapture={(e) => e.stopPropagation()}
            onClickCapture={(e) => { e.stopPropagation(); data.setActiveTab("preview"); }}
          >
            <Eye size={16} /> Bấm để Preview Data
          </button>
        )}
      </div>
      <Handle type="source" position={Position.Right} style={{background: '#f59e0b'}} />
    </div>
  );
};

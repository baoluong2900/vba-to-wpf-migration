import { Handle, Position } from '@xyflow/react';
import { FileJson, Copy } from 'lucide-react';

export const OutputNode = ({ data }: any) => {
  const handleCopy = () => {
    if (data.resultJson) {
      navigator.clipboard.writeText(data.resultJson);
      alert("Đã copy JSON output vào Clipboard!");
    }
  };

  const displayResult = data.ddResultJson || data.resultJson;

  return (
    <div className={`node ${data.ddAgentStatus === "success" || data.agentStatus === "success" ? "active" : ""}`}>
      <Handle type="target" position={Position.Left} style={{background: '#8b5cf6'}} />
      <div className="node-header output-type" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div className="node-icon output-icon"><FileJson size={14} /></div>
          <span>JSON Docs Output</span>
        </div>
        {displayResult && (
          <button onClick={() => {
            if (displayResult) {
              navigator.clipboard.writeText(displayResult);
              alert("Đã copy JSON output vào Clipboard!");
            }
          }} style={{ display: 'flex', alignItems: 'center', gap: '4px', background: 'none', border: 'none', color: '#8b5cf6', cursor: 'pointer', fontSize: '11px' }}>
            <Copy size={12} /> Copy
          </button>
        )}
      </div>
      <div className="node-body">
        {displayResult ? (
          <div className="json-display" style={{height: 250}}>
            {displayResult}
          </div>
        ) : (
          <div className="json-display empty" style={{height: 250}}>
            Chưa có kết quả.
          </div>
        )}
      </div>
    </div>
  );
};


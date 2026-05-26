import { Handle, Position } from '@xyflow/react';
import { Cpu, Play, CheckCircle2, XCircle } from 'lucide-react';

// DD Agent color theme: orange (#f97316) — distinct from BD blue (#3b82f6)
const DD_COLOR = '#f97316';
const DD_COLOR_DIM = 'rgba(249,115,22,0.15)';
const DD_COLOR_BORDER = 'rgba(249,115,22,0.4)';

const stepOrder = ['d1', 'd2', 'd3', 'd4', 'done'];

function isStepDone(currentStep: string, checkStep: string): boolean {
  const ci = stepOrder.indexOf(currentStep);
  const si = stepOrder.indexOf(checkStep);
  return ci > si;
}

function isStepActive(currentStep: string, checkStep: string): boolean {
  return currentStep === checkStep;
}

interface StepRowProps {
  step: string;
  label: string;
  currentStep: string;
}

function StepRow({ step, label, currentStep }: StepRowProps) {
  const done   = isStepDone(currentStep, step);
  const active = isStepActive(currentStep, step);

  const color = active ? DD_COLOR : done ? '#10b981' : "var(--text-muted)";

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color, marginBottom: '4px' }}>
      {active
        ? <div className="loader" style={{ width: 10, height: 10, borderTopColor: DD_COLOR }} />
        : done
          ? <CheckCircle2 size={12} />
          : <div style={{ width: 12, height: 12, borderRadius: '50%', border: '1px solid #6b7280' }} />
      }
      <span>{label}</span>
    </div>
  );
}

export const DdAgentNode = ({ data }: any) => {
  const isActive = data.ddAgentStatus === 'running' || data.ddAgentStatus === 'success';

  return (
    <div
      className={`node ${isActive ? 'active' : ''}`}
      style={{
        borderColor: isActive ? DD_COLOR_BORDER : undefined,
        boxShadow: isActive ? `0 0 0 1px ${DD_COLOR_BORDER}` : undefined,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: DD_COLOR }} />

      {/* Header */}
      <div
        className="node-header"
        style={{
          background: isActive ? `linear-gradient(135deg, rgba(249,115,22,0.25), rgba(249,115,22,0.10))` : undefined,
          borderBottom: `1px solid ${DD_COLOR_BORDER}`,
        }}
      >
        <div className="node-icon" style={{ background: DD_COLOR_DIM, color: DD_COLOR }}>
          <Cpu size={14} />
        </div>
        <span style={{ flex: 1, color: DD_COLOR }}>DD Agent</span>

        {data.ddAgentStatus === 'running' && (
          <div className="status-badge running" title="Đang xử lý...">
            <div className="loader" style={{ borderTopColor: DD_COLOR }} />
          </div>
        )}
        {data.ddAgentStatus === 'success' && (
          <div className="status-badge success"><CheckCircle2 size={12} /> OK</div>
        )}
        {data.ddAgentStatus === 'error' && (
          <div className="status-badge error"><XCircle size={12} /> Err</div>
        )}
      </div>

      {/* Body */}
      <div className="node-body">
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: 8 }}>
          Input: {data.viewMode === "screen" ? "BD S4 Final + Deep D1 Source" : "Deep D1 Source Logic"}
        </div>

        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          <label style={{ display: 'block', marginBottom: 4 }}>Select DD Model:</label>
          <select 
            className="input-field nodrag" 
            value={data.ddSelectedModel}
            onChange={(e) => data.setDdSelectedModel(e.target.value)}
            disabled={data.ddAgentStatus === "running"}
            style={{ marginBottom: 12, fontSize: 13 }}
          >
            {data.models?.map((m: string) => {
              const st = data.modelHealth?.[m]?.status;
              const badge = st === 'ok' ? '✅' : st === 'quota_exceeded' ? '⛔' : st === 'error' ? '⚠️' : st === 'testing' ? '⏳' : '○';
              return <option key={m} value={m}>{badge} {m}</option>;
            })}
          </select>
        </div>

        {/* Step tracker */}
        {(data.ddAgentStatus === 'running' || data.ddAgentStatus === 'success') && (
          <div
            style={{
              marginBottom: 12,
              fontSize: '11px',
              background: 'rgba(0,0,0,0.2)',
              padding: '8px',
              borderRadius: '4px',
              border: `1px solid ${DD_COLOR_BORDER}`,
            }}
          >
            <StepRow step="d1" label="D1: Parse & Skeleton"       currentStep={data.ddAgentStep} />
            <StepRow step="d2" label="D2: SQL Table Mapping"      currentStep={data.ddAgentStep} />
            <StepRow step="d3" label="D3: LLM Detail Gen (steps)" currentStep={data.ddAgentStep} />
            <StepRow step="d4" label="D4: Merge Final DD"         currentStep={data.ddAgentStep} />
          </div>
        )}

        {/* Run Button */}
        {(() => {
          const isModuleMode = data.viewMode === "module" || data.viewMode === "macro";
          const canRun = isModuleMode 
            ? data.queryStatus === 'success' 
            : data.agentStatus === 'success';
          
          return (
            <>
              <button
                className="run-btn nodrag"
                onMouseDownCapture={(e) => e.stopPropagation()}
                onClickCapture={(e) => {
                  e.stopPropagation();
                  data.handleRunDdAgent?.();
                }}
                disabled={!canRun || data.ddAgentStatus === 'running'}
                style={{
                  background: canRun && data.ddAgentStatus !== 'running'
                    ? `linear-gradient(135deg, ${DD_COLOR}, #ea580c)`
                    : undefined,
                  opacity: !canRun ? 0.5 : 1,
                }}
              >
                <Play size={16} fill="currentColor" />
                {data.ddAgentStatus === 'running' ? 'Đang xử lý...' : 'Chạy DD Agent'}
              </button>

              {!canRun && (
                <div style={{ fontSize: '11px', color: "var(--text-muted)", marginTop: 6, textAlign: 'center' }}>
                  {isModuleMode ? 'Chờ truy vấn L1 Repo hoàn thành' : 'Chờ BD Agent hoàn thành trước'}
                </div>
              )}
            </>
          );
        })()}
      </div>

      <Handle type="source" position={Position.Right} style={{ background: DD_COLOR }} />
    </div>
  );
};

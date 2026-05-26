import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { WS_BASE_URL } from '../api';
import styles from './ToolTracePanel.module.css';

const AGENT_STEPS = [
  {
    key: 'mongodb-mcp',
    name: 'MongoDB MCP',
    agent: 'MongoDBMCP',
    description: 'Connected to the read-only MongoDB MCP server and validated database access.',
  },
  {
    key: 'planner',
    name: 'Meeting planner',
    agent: 'MeetingPlanner',
    description: 'Read the meeting, doctor, drug, and visit context to decide what the rep should prepare.',
  },
  {
    key: 'retriever',
    name: 'Information retriever',
    agent: 'InformationRetriever',
    description: 'Collected internal context and external evidence that could support the briefing.',
  },
  {
    key: 'writer',
    name: 'Brief writer',
    agent: 'BriefWriter',
    description: 'Turned the selected evidence into talking points, objections, and follow-up wording.',
  },
  {
    key: 'quality',
    name: 'Claim quality gate',
    agent: 'ClaimQualityGate',
    description: 'Verified each talking point has numeric, drug-owned, cited evidence before compliance review.',
  },
  {
    key: 'compliance',
    name: 'Compliance checker',
    agent: 'ComplianceChecker',
    description: 'Checked the output against promotional and sample-handling rules before saving.',
  },
  {
    key: 'executor',
    name: 'Action executor',
    agent: 'ActionExecutor',
    description: 'Saved the briefing and updated the meeting so the dashboard can show the result.',
  },
];

const connectionLabel = (state) => {
  if (state === 'complete') return 'Trace complete';
  if (state === 'connected') return 'Live trace connected';
  if (state === 'error') return 'Trace connection issue';
  if (state === 'closed') return 'Trace stream closed';
  return 'Connecting to trace';
};

const stepStateLabel = {
  waiting: 'Waiting',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  unavailable: 'Not observed',
};

function ToolTracePanel({ meeting, detail, onRefreshMeetings, onTraceComplete }) {
  const [events, setEvents] = useState([]);
  const [connectionState, setConnectionState] = useState('connecting');
  const activeTraceRef = useRef(null);
  const eventSeqRef = useRef(0);

  const decorateEvent = useCallback((payload) => {
    eventSeqRef.current += 1;
    return {
      ...payload,
      localId: `${meeting.id}-${eventSeqRef.current}`,
      receivedAt: Date.now(),
    };
  }, [meeting.id]);

  useEffect(() => {
    if (detail?.briefing) {
      return undefined;
    }

    const socket = new WebSocket(`${WS_BASE_URL}/ws/log/${meeting.id}`);
    let refreshTimer = null;

    socket.onopen = () => {
      setConnectionState('connected');
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'complete') {
        setConnectionState('complete');
        onTraceComplete?.();
        refreshTimer = window.setTimeout(() => onRefreshMeetings?.(), 500);
        return;
      }
      if (payload.type === 'waiting') {
        setEvents(prev => [...prev, decorateEvent(payload)]);
        return;
      }
      if (payload.type === 'error') {
        setConnectionState('error');
        setEvents(prev => [...prev, decorateEvent(payload)]);
        return;
      }
      setEvents(prev => [...prev, decorateEvent(payload)]);
    };

    socket.onerror = () => {
      setConnectionState('error');
    };

    socket.onclose = () => {
      setConnectionState(prev => prev === 'complete' ? prev : 'closed');
    };

    return () => {
      if (refreshTimer) window.clearTimeout(refreshTimer);
      socket.close();
    };
  }, [decorateEvent, detail?.briefing, meeting.id, onRefreshMeetings, onTraceComplete]);

  const briefing = detail?.briefing;
  const storedTrace = briefing?.tool_trace || detail?.tool_trace;
  const isFailed = detail?.status === 'failed' || meeting.status === 'failed';

  const stepStates = useMemo(() => {
    const states = AGENT_STEPS.reduce((acc, step) => ({ ...acc, [step.agent]: 'waiting' }), {});

    if (storedTrace?.steps) {
      AGENT_STEPS.forEach((step) => {
        states[step.agent] = storedTrace.steps[step.agent]?.status || 'done';
      });
      return states;
    }

    if (briefing) {
      AGENT_STEPS.forEach((step) => {
        states[step.agent] = 'done';
      });
      return states;
    }

    events.forEach((event) => {
      if (event.step && event.phase && ['STEP', 'MCP_CHECK', 'MCP_QUERY'].includes(event.tag)) {
        states[event.step] = event.phase === 'completed'
          ? 'done'
          : event.phase === 'failed'
            ? 'failed'
            : 'running';
      }
      if (event.tag === 'ERROR') {
        const runningStep = AGENT_STEPS.find((step) => states[step.agent] === 'running');
        if (runningStep) states[runningStep.agent] = 'failed';
      }
    });
    return states;
  }, [briefing, events, storedTrace]);
  const hasLiveStepTrace = useMemo(
    () => Boolean(briefing || storedTrace?.steps || events.some((event) => event.step && event.phase)),
    [briefing, events, storedTrace]
  );
  const effectiveConnectionState = briefing ? 'complete' : connectionState;
  const isComplete = effectiveConnectionState === 'complete' || Boolean(briefing);

  const stepStatus = useCallback((agent) => {
    if (briefing && !stepStates[agent]) return 'done';
    if (!hasLiveStepTrace && effectiveConnectionState === 'complete') return 'unavailable';
    if (isFailed && stepStates[agent] === 'running') return 'failed';
    return stepStates[agent] || 'waiting';
  }, [briefing, effectiveConnectionState, hasLiveStepTrace, isFailed, stepStates]);

  const isLive = !isComplete && !isFailed;

  const traceRows = useMemo(() => {
    const rows = AGENT_STEPS.map((step, index) => ({
      ...step,
      index,
      status: stepStatus(step.agent),
    }));

    if (isComplete || isFailed) return rows;

    const runningStep = rows.find((step) => step.status === 'running' || step.status === 'failed');
    return runningStep ? [runningStep] : rows.slice(0, 1);
  }, [isComplete, isFailed, stepStatus]);
  const activeTraceKey = useMemo(() => {
    const runningStep = traceRows.find((step) => step.status === 'running' || step.status === 'failed');
    if (runningStep) return runningStep.key;
    return traceRows.at(-1)?.key;
  }, [traceRows]);

  useEffect(() => {
    activeTraceRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [activeTraceKey, events.length, isComplete]);

  return (
    <div className={styles.container}>
      <div className={styles.summary}>
        <div>
          <div className={styles.eyebrow}>Tool trace</div>
          <h4>{isComplete ? 'Trace history' : 'Working through briefing steps'}</h4>
        </div>
        <span className={styles.connectionPill}>{connectionLabel(effectiveConnectionState)}</span>
      </div>

      <div className={styles.traceScroll}>
        {!briefing && !hasLiveStepTrace && effectiveConnectionState === 'complete' && (
          <div className={styles.traceNotice}>
            This briefing was generated before live step tracing was captured. New runs will update each agent as it actually starts and completes.
          </div>
        )}
        <div className={styles.traceTimeline}>
          {traceRows.map((step) => (
            <div
              key={isLive ? 'active' : step.key}
              ref={step.key === activeTraceKey ? activeTraceRef : null}
              className={`${styles.traceRow} ${styles[`trace-${step.status}`]}`}
            >
              <div className={styles.traceMarker} aria-hidden="true" />
              <div className={styles.traceBody}>
                <div className={styles.traceTopline}>
                  <div className={styles.agentName}>{step.name}</div>
                  <span className={`${styles.statusPill} ${styles[`status-${step.status}`]}`}>
                    {stepStateLabel[step.status]}
                  </span>
                </div>
                {(step.status === 'running' || step.status === 'failed' || isComplete) && (
                  <p>{step.description}</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default ToolTracePanel;

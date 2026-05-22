import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { WS_BASE_URL } from '../api';
import styles from './ToolTracePanel.module.css';

const AGENT_STEPS = [
  {
    key: 'planner',
    name: 'Meeting planner',
    agent: 'MeetingPlanner',
    description: 'Read the meeting, doctor, drug, and visit context to decide what the rep should prepare.',
    data: 'MongoDB meeting, doctor profile, drug profile',
  },
  {
    key: 'retriever',
    name: 'Information retriever',
    agent: 'InformationRetriever',
    description: 'Collected internal context and external evidence that could support the briefing.',
    data: 'Elasticsearch, PubMed, ClinicalTrials.gov, OpenFDA',
  },
  {
    key: 'writer',
    name: 'Brief writer',
    agent: 'BriefWriter',
    description: 'Turned the selected evidence into talking points, objections, and follow-up wording.',
    data: 'Retrieved evidence and CRM memory',
  },
  {
    key: 'quality',
    name: 'Claim quality gate',
    agent: 'ClaimQualityGate',
    description: 'Verified each talking point has numeric, drug-owned, cited evidence before compliance review.',
    data: 'Evidence ledger and draft claims',
  },
  {
    key: 'compliance',
    name: 'Compliance checker',
    agent: 'ComplianceChecker',
    description: 'Checked the output against promotional and sample-handling rules before saving.',
    data: 'MongoDB compliance rules',
  },
  {
    key: 'executor',
    name: 'Action executor',
    agent: 'ActionExecutor',
    description: 'Saved the briefing and updated the meeting so the dashboard can show the result.',
    data: 'MongoDB briefing and meeting records',
  },
];

const sourceKey = (source) => {
  if (!source || typeof source !== 'object') return '';
  const raw = String(source.source || source.type || '').toLowerCase();
  if (raw.includes('pubmed') || source.pmid) return 'pubmed';
  if (raw.includes('clinical') || source.nctId || source.nct_id) return 'clinical';
  if (raw.includes('openfda') || source.drug_label) return 'openfda';
  if (
    raw.includes('internal') ||
    raw.includes('competitive') ||
    raw.includes('crm') ||
    source.doc_id ||
    source.source_id
  ) {
    return 'elastic';
  }
  return '';
};

const collectEvidenceSources = (briefing) => {
  const sources = [];
  const visit = (value) => {
    if (!value) return;
    if (Array.isArray(value)) {
      value.forEach(visit);
      return;
    }
    if (typeof value !== 'object') return;

    if (sourceKey(value)) sources.push(value);
    if (value.source && typeof value.source === 'object') sources.push(value.source);

    Object.entries(value).forEach(([key, child]) => {
      if (key === 'source') return;
      if (Array.isArray(child) || (child && typeof child === 'object')) {
        visit(child);
      }
    });
  };

  visit(briefing?.supporting_evidence);
  visit(briefing?.drug_sections);
  return sources;
};

const countBy = (items, keyFn) =>
  items.reduce((counts, item) => {
    const key = keyFn(item);
    if (!key) return counts;
    return { ...counts, [key]: (counts[key] || 0) + 1 };
  }, {});

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
  const storedTrace = briefing?.tool_trace;
  const isFailed = detail?.status === 'failed' || meeting.status === 'failed';

  const evidenceSources = useMemo(() => collectEvidenceSources(briefing), [briefing]);
  const sourceCounts = useMemo(() => countBy(evidenceSources, sourceKey), [evidenceSources]);
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
      if (event.tag === 'STEP' && event.step && event.phase) {
        states[event.step] = event.phase === 'completed' ? 'done' : 'running';
      }
      if (event.tag === 'ERROR') {
        const runningStep = AGENT_STEPS.find((step) => states[step.agent] === 'running');
        if (runningStep) states[runningStep.agent] = 'failed';
      }
    });
    return states;
  }, [briefing, events, storedTrace]);
  const hasLiveStepTrace = useMemo(
    () => Boolean(briefing || storedTrace?.steps || events.some((event) => event.tag === 'STEP' && event.step)),
    [briefing, events, storedTrace]
  );
  const retrieverState = stepStates.InformationRetriever;
  const plannerState = stepStates.MeetingPlanner;
  const executorState = stepStates.ActionExecutor;

  const dataSources = useMemo(() => {
    const retrieverStatus = retrieverState === 'done'
      ? 'Checked'
      : retrieverState === 'running'
        ? 'Checking'
        : 'Waiting';
    const sources = [
      {
        name: 'MongoDB Atlas',
        purpose: 'Meeting schedule, doctor profile, drug profile, CRM history, compliance rules, and saved briefing.',
        status: plannerState === 'done' || executorState === 'done'
          ? 'Used'
          : plannerState === 'running'
            ? 'Reading'
            : 'Waiting',
      },
      {
        name: 'Elasticsearch',
        purpose: sourceCounts.elastic
          ? `${sourceCounts.elastic} internal evidence item${sourceCounts.elastic === 1 ? '' : 's'} ${
              retrieverState === 'done' ? 'used' : 'referenced in the saved briefing'
            } from company docs, CRM memory, or competitive intel.`
          : 'Internal company docs, CRM memory, and competitive intelligence search.',
        status: sourceCounts.elastic && retrieverState === 'done' ? 'Used' : retrieverStatus,
      },
    ];

    if (sourceCounts.pubmed || retrieverState === 'running' || retrieverState === 'done') {
      sources.push({
        name: 'PubMed API',
        purpose: sourceCounts.pubmed
          ? `${sourceCounts.pubmed} literature reference${sourceCounts.pubmed === 1 ? '' : 's'} ${
              retrieverState === 'done' ? 'included' : 'found in the saved briefing'
            }.`
          : 'Literature evidence lookup when needed.',
        status: sourceCounts.pubmed && retrieverState === 'done' ? 'Used' : retrieverStatus,
      });
    }

    if (sourceCounts.clinical || retrieverState === 'running' || retrieverState === 'done') {
      sources.push({
        name: 'ClinicalTrials.gov API',
        purpose: sourceCounts.clinical
          ? `${sourceCounts.clinical} trial reference${sourceCounts.clinical === 1 ? '' : 's'} ${
              retrieverState === 'done' ? 'included' : 'found in the saved briefing'
            }.`
          : 'Clinical trial lookup when needed.',
        status: sourceCounts.clinical && retrieverState === 'done' ? 'Used' : retrieverStatus,
      });
    }

    if (sourceCounts.openfda || retrieverState === 'running' || retrieverState === 'done') {
      sources.push({
        name: 'OpenFDA API',
        purpose: sourceCounts.openfda
          ? `${sourceCounts.openfda} drug label reference${sourceCounts.openfda === 1 ? '' : 's'} ${
              retrieverState === 'done' ? 'included' : 'found in the saved briefing'
            }.`
          : 'Drug label lookup when needed.',
        status: sourceCounts.openfda && retrieverState === 'done' ? 'Used' : retrieverStatus,
      });
    }

    if (briefing?.gmail_draft_id && executorState === 'done') {
      sources.push({
        name: 'Gmail API',
        purpose: `Draft email created: ${briefing.gmail_draft_id}`,
        status: 'Used',
      });
    } else if (briefing?.draft_email_subject && executorState === 'done') {
      sources.push({
        name: 'Email draft',
        purpose: 'Draft subject and body were prepared in the briefing. Gmail was not called for this run.',
        status: 'Prepared',
      });
    }

    if (briefing?.calendar_event_id && executorState === 'done') {
      sources.push({
        name: 'Google Calendar API',
        purpose: `Calendar prep block created: ${briefing.calendar_event_id}`,
        status: 'Used',
      });
    }

    return sources;
  }, [briefing, executorState, plannerState, retrieverState, sourceCounts]);

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
                  <div>
                    <div className={styles.agentName}>{step.name}</div>
                    <div className={styles.agentId}>{step.agent}</div>
                  </div>
                  <span className={`${styles.statusPill} ${styles[`status-${step.status}`]}`}>
                    {stepStateLabel[step.status]}
                  </span>
                </div>
                {(step.status === 'running' || step.status === 'failed' || isComplete) && (
                  <>
                    <p>{step.description}</p>
                    <div className={styles.dataLine}>Data used: {step.data}</div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>

        {(isComplete || isFailed) && (
          <div className={styles.sourceTrail}>
            <div className={styles.sectionTitle}>Data & APIs used</div>
            <div className={styles.sourceGrid}>
              {dataSources.map((source) => (
                <div key={source.name} className={styles.sourceItem}>
                  <div className={styles.sourceTopline}>
                    <div className={styles.sourceName}>{source.name}</div>
                    <span>{source.status}</span>
                  </div>
                  <p>{source.purpose}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default ToolTracePanel;

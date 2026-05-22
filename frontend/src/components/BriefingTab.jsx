import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../api';
import styles from './BriefingTab.module.css';
import ToolTracePanel from './ToolTracePanel';

const formatDate = (value) => {
  if (!value) return '';
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
};

const asArray = (value) => Array.isArray(value) ? value : [];

const sourceLabel = (source) => {
  if (!source) return '';
  if (typeof source === 'string') return source;
  const type = source.type || source.source || 'Source';
  const id = source.doc_id || source.id || source.pmid || source.nctId || source.source_id;
  const title = source.title || source.label || source.relevance;
  return [type, id, title].filter(Boolean).join(' · ');
};

const normalizeTalkingPoints = (briefing) => {
  const points = [];

  asArray(briefing?.talking_points).forEach((point) => {
    if (typeof point === 'string') {
      points.push({ text: point });
      return;
    }
    if (point?.point) {
      points.push({
        text: point.point,
        source: point.citation || sourceLabel(point.source) || sourceLabel(point),
      });
    }
  });

  asArray(briefing?.drug_sections).forEach((section) => {
    asArray(section.key_talking_points).forEach((point) => {
      points.push({
        text: point.point || String(point),
        source: sourceLabel(point.source),
        label: section.drug_name,
      });
    });
  });

  return points;
};

const normalizeObjections = (briefing) => {
  if (briefing?.anticipated_objection) {
    return [briefing.anticipated_objection];
  }

  return asArray(briefing?.drug_sections).flatMap((section) =>
    asArray(section.known_objections_responses).map((item) => ({
      ...item,
      drug_name: section.drug_name,
    }))
  );
};

const normalizeEvidence = (briefing) =>
  asArray(briefing?.supporting_evidence).map((evidence) => ({
    title: evidence.source || evidence.type || evidence.title || 'Evidence',
    id: evidence.id || evidence.source_id || evidence.pmid || evidence.nctId || evidence.doc_id || evidence.drug_label,
    description: evidence.relevance || evidence.label || evidence.summary || evidence.content,
    meta: evidence.journal || evidence.source_label || evidence.url,
    url: evidence.source_url || evidence.url,
  }));

/**
 * Check whether the detail object contains a briefing we can display.
 * This is used to decide whether auto-generation should be triggered.
 */
const hasBriefingData = (data) => {
  if (!data) return false;
  if (data.briefing) return true;
  // If status says briefing_ready but briefing object is null, treat as ready
  // (could be a serialization gap — the data exists in DB).
  if (data.status === 'briefing_ready' || data.status === 'needs_review') return true;
  return false;
};

function BriefingTab({ meeting, onRefreshMeetings, onRegenerateControlChange }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isTraceOpen, setIsTraceOpen] = useState(() => meeting.status === 'processing' || meeting.status === 'waiting');
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const generationRequestedRef = useRef(false);
  const traceToggledRef = useRef(false);
  const loadRetryCountRef = useRef(0);
  const handleTraceComplete = useCallback(() => {
    if (!traceToggledRef.current) setIsTraceOpen(false);
  }, []);

  const requestGeneration = useCallback(async ({ force = false } = {}) => {
    if (generationRequestedRef.current) return;
    generationRequestedRef.current = true;
    setIsGenerating(true);
    if (force) {
      setIsTraceOpen(true);
      traceToggledRef.current = false;
      setDetail((previous) => previous ? { ...previous, status: 'agent_processing', briefing: null } : previous);
    }

    try {
      const data = await fetchJson(`/meeting/${meeting.id}/briefing/generate${force ? '?force=true' : ''}`, {
        method: 'POST',
      });
      setDetail(data);
      setError(''); // Clear any previous errors
      onRefreshMeetings?.();
    } catch (generationError) {
      generationRequestedRef.current = false;
      // Only set error if we don't already have good data displayed
      setDetail((prev) => {
        if (prev?.briefing) {
          // We already have a briefing displayed — don't overwrite with error
          console.warn('[BriefingTab] Generation request failed but existing briefing is still displayed:', generationError.message);
          return prev;
        }
        setError(generationError.message || 'Could not start briefing generation');
        return prev;
      });
      setIsGenerating(false);
    }
  }, [meeting.id, onRefreshMeetings]);

  const handleRegenerate = useCallback(() => {
    generationRequestedRef.current = false;
    setError(''); // Clear errors when user explicitly regenerates
    requestGeneration({ force: true });
  }, [requestGeneration]);

  useEffect(() => {
    onRegenerateControlChange?.({
      visible: Boolean(detail?.briefing),
      disabled: isGenerating || detail?.status === 'agent_processing',
      label: isGenerating || detail?.status === 'agent_processing' ? 'Regenerating...' : 'Regenerate',
      onClick: handleRegenerate,
    });

    return () => onRegenerateControlChange?.(null);
  }, [detail?.briefing, detail?.status, handleRegenerate, isGenerating, onRegenerateControlChange]);

  const loadDetail = useCallback(async (signal) => {
    try {
      const data = await fetchJson(`/meeting/${meeting.id}`, { signal });
      if (!data) {
        throw new Error('Could not load briefing');
      }
      setDetail(data);
      setError(''); // Clear errors on successful load
      loadRetryCountRef.current = 0; // Reset retry count on success

      // Only auto-trigger generation if:
      // 1. No briefing data at all (not just missing from response)
      // 2. Status is 'scheduled' (never been generated)
      // 3. Status is NOT 'agent_processing' (already running)
      // 4. Status is NOT 'failed' (don't auto-retry failures — let user decide)
      if (
        !hasBriefingData(data) &&
        data.status === 'scheduled' &&
        !generationRequestedRef.current
      ) {
        console.log('[BriefingTab] No briefing found and status=scheduled, auto-triggering generation');
        requestGeneration();
      }

      if (hasBriefingData(data) || data.status === 'failed') {
        setIsGenerating(false);
      }

      const apiStatus = data.status === 'briefing_ready' || data.status === 'needs_review'
        ? 'ready'
        : data.status === 'agent_processing'
          ? 'processing'
          : data.status;
      if (apiStatus !== meeting.status) {
        onRefreshMeetings?.();
      }
    } catch (loadError) {
      if (loadError.name === 'AbortError') return;

      loadRetryCountRef.current += 1;
      console.error(
        `[BriefingTab] Load error (attempt ${loadRetryCountRef.current}):`,
        loadError.message
      );

      // KEY FIX: If we already have detail loaded with a briefing, don't
      // overwrite it with an error. The stale data is better than no data.
      setDetail((prev) => {
        if (prev?.briefing) {
          console.warn('[BriefingTab] Keeping existing briefing despite load error');
          return prev; // Keep the existing good data
        }
        // Only show error if we truly have nothing to display
        setError(loadError.message || 'Could not load briefing');
        return prev;
      });
    } finally {
      if (!signal?.aborted) {
        setIsLoading(false);
      }
    }
  }, [meeting.id, meeting.status, onRefreshMeetings, requestGeneration]);

  useEffect(() => {
    const controller = new AbortController();
    const initialLoadId = window.setTimeout(() => loadDetail(controller.signal), 0);

    const shouldPoll = meeting.status === 'processing' || meeting.status === 'waiting' || isGenerating;
    const intervalId = shouldPoll
      ? window.setInterval(() => loadDetail(), 5000)
      : null;

    return () => {
      window.clearTimeout(initialLoadId);
      controller.abort();
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [isGenerating, loadDetail, meeting.status]);

  useEffect(() => {
    if (traceToggledRef.current) return;
    const autoOpen = meeting.status === 'processing' || meeting.status === 'waiting' || isGenerating || detail?.status === 'agent_processing';
    if (autoOpen) setIsTraceOpen(true);
  }, [detail?.status, isGenerating, meeting.status]);

  const handleAsk = async (e) => {
    e?.preventDefault();
    const trimmedQuestion = inputValue.trim();
    if (!trimmedQuestion) return;

    setIsChatOpen(true);
    setMessages(prev => [...prev, { type: 'q', text: trimmedQuestion }]);
    setInputValue('');
    setIsAsking(true);

    try {
      const response = await fetchJson('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meeting_id: meeting.id,
          question: trimmedQuestion,
        }),
      });

      setMessages(prev => [...prev, {
        type: 'a',
        text: response.answer,
        sources: response.sources || [],
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        type: 'a',
        text: error.message || 'Could not answer this question right now.',
        sources: [],
        isError: true,
      }]);
    } finally {
      setIsAsking(false);
    }
  };

  const handleAskKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !isAsking && inputValue.trim()) {
      handleAsk(e);
    }
  };

  const briefing = detail?.briefing;
  const hcp = detail?.hcp || {};
  const drug = detail?.drug || {};
  const talkingPoints = useMemo(() => normalizeTalkingPoints(briefing), [briefing]);
  const objections = useMemo(() => normalizeObjections(briefing), [briefing]);
  const evidence = useMemo(() => normalizeEvidence(briefing), [briefing]);

  if (isLoading && !detail) {
    return <div className={styles.stateMessage}>Loading briefing...</div>;
  }

  if (error && !detail?.briefing) {
    return <div className={styles.stateMessage}>{error}</div>;
  }

  const askForm = (
    <form onSubmit={handleAsk} className={styles.askForm}>
      <input 
        type="text" 
        className={styles.askInput} 
        placeholder={isChatOpen ? 'Ask about the meeting, briefing, or project scope...' : 'Ask about this meeting...'}
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleAskKeyDown}
        disabled={isAsking}
      />
      <button 
        type="submit" 
        className={styles.askSubmitBtn}
        disabled={isAsking || !inputValue.trim()}
        aria-label="Ask"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
      </button>
    </form>
  );

  return (
    <div className={`${styles.briefingTab} ${isChatOpen ? styles.chatOpen : ''}`}>
      <div className={styles.content}>
        <section className={styles.section}>
          <div className={styles.sectionLabel}>Doctor Context</div>
          <div className={styles.chipRow}>
            {hcp.specialty && <span className={styles.chip}>Specialty: {hcp.specialty}</span>}
            {hcp.last_visited && <span className={styles.chip}>Last visited: {formatDate(hcp.last_visited)}</span>}
            {hcp.relationship_score !== undefined && <span className={styles.chip}>Relationship: {hcp.relationship_score}/10</span>}
            {asArray(hcp.prescribing_focus).map((focus) => (
              <span key={focus} className={styles.chip}>Focus: {focus}</span>
            ))}
            {asArray(hcp.known_objections).map((objection) => (
              <span key={objection} className={styles.chip}>Concern: {objection}</span>
            ))}
            {drug.brand_name && <span className={styles.chip}>Drug: {drug.brand_name}</span>}
          </div>

          <details
            className={styles.traceDetails}
            open={isTraceOpen}
            onToggle={(e) => {
              setIsTraceOpen(e.currentTarget.open);
            }}
          >
            <summary
              className={styles.traceSummary}
              onClick={() => {
                traceToggledRef.current = true;
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  traceToggledRef.current = true;
                }
              }}
            >
              <span className={styles.traceChevron} aria-hidden="true" />
              <span className={styles.traceSummaryText}>Live tool trace</span>
              <span className={styles.traceSummaryHint}>
                {isTraceOpen ? 'Hide' : 'Show'}
              </span>
            </summary>
            <div className={styles.traceInlinePanel}>
              <ToolTracePanel
                meeting={meeting}
                detail={detail}
                onRefreshMeetings={onRefreshMeetings}
                onTraceComplete={handleTraceComplete}
              />
            </div>
          </details>
        </section>

        {!briefing && (
          <section className={styles.section}>
            <div className={styles.sectionLabel}>Briefing Status</div>
            <div className={styles.emptyPanel}>
              {detail?.status === 'failed'
                ? detail.error_message || meeting.errorMessage || 'Agent could not complete this briefing.'
                : detail?.status === 'briefing_ready' || detail?.status === 'needs_review'
                  ? 'Briefing is ready. Reloading details...'
                  : isGenerating || detail?.status === 'agent_processing'
                    ? 'Generating briefing with the agent pipeline. This view will update when the backend saves the generated result.'
                    : 'Starting briefing generation...'}
            </div>
          </section>
        )}

        {briefing?.rep_summary_report && (
          <section className={styles.section}>
            <div className={styles.sectionLabel}>Rep Summary</div>
            <div className={styles.summaryBox}>{briefing.rep_summary_report}</div>
          </section>
        )}

        {talkingPoints.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <div className={styles.sectionLabel}>Talking Points</div>
              {briefing.compliance_status && (
                <div className={styles.complianceNote}>Compliance: {briefing.compliance_status}</div>
              )}
            </div>
            {talkingPoints.map((point, index) => (
              <div key={`${point.text}-${index}`} className={styles.pointCard}>
                <div className={`${styles.pointNumber} serif`}>{index + 1}</div>
                <div className={styles.pointContent}>
                  {point.label && <div className={styles.pointLabel}>{point.label}</div>}
                  <p className={styles.pointText}>{point.text}</p>
                  {point.source && <div className={styles.pointSource}>Source: {point.source}</div>}
                </div>
              </div>
            ))}
          </section>
        )}

        {objections.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionLabel}>Anticipated Objections</div>
            {objections.map((item, index) => (
              <div key={index} className={styles.objectionBox}>
                {typeof item === 'string' ? (
                  <p>{item}</p>
                ) : (
                  <>
                    {item.drug_name && <p><strong>{item.drug_name}</strong></p>}
                    {item.objection && <p>{item.objection}</p>}
                    {item.response && <p><strong>Response:</strong> {item.response}</p>}
                    {item.competitive_context && <p>{item.competitive_context}</p>}
                  </>
                )}
              </div>
            ))}
          </section>
        )}

        {briefing && (
          <section className={styles.section}>
            <div className={styles.actionStrip}>
              <span className={styles.actionChip}>Briefing saved</span>
              {briefing.calendar_event_id && <span className={styles.actionChip}>Calendar event: {briefing.calendar_event_id}</span>}
              {briefing.gmail_draft_id && <span className={styles.actionChip}>Gmail draft: {briefing.gmail_draft_id}</span>}
              {briefing.draft_email_subject && <span className={styles.actionChip}>Email draft prepared</span>}
            </div>
          </section>
        )}

        {evidence.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionLabel}>Evidence Used</div>
            <div className={styles.evidenceGrid}>
              {evidence.map((item, index) => {
                const content = (
                  <>
                    <div className={styles.evidenceTitle}>{item.title}</div>
                    {item.id && <div className={styles.evidenceSub}>{item.id}</div>}
                    {item.description && <div className={styles.evidenceDesc}>{item.description}</div>}
                    {item.meta && <div className={styles.evidenceMeta}>{item.meta}</div>}
                  </>
                );
                return item.url ? (
                  <a key={index} href={item.url} className={styles.evidenceCard} target="_blank" rel="noreferrer">
                    {content}
                  </a>
                ) : (
                  <div key={index} className={styles.evidenceCard}>{content}</div>
                );
              })}
            </div>
          </section>
        )}
      </div>

      {isChatOpen && (
        <aside className={styles.askChatDock}>
          <div className={styles.chatHeader}>
            <div>
              <h3>Project Agent</h3>
              <p>Meeting, briefing, and pharma workflow help</p>
            </div>
            <div className={styles.chatHeaderActions}>
              {messages.length > 0 && (
                <button className={styles.clearChatBtn} onClick={() => setMessages([])}>Clear</button>
              )}
              <button className={styles.closeBtn} onClick={() => setIsChatOpen(false)}>×</button>
            </div>
          </div>
          <div className={styles.chatMessages}>
            {messages.length === 0 && (
              <div className={styles.emptyChat}>
                Ask about this doctor, briefing evidence, objections, compliance rules, or the project workflow.
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={styles.messagePair}>
                {msg.type === 'q' && (
                  <div className={styles.questionBlock}>
                    <div className={styles.qLabel}>You asked:</div>
                    <div className={styles.qText}>{msg.text}</div>
                  </div>
                )}
                {msg.type === 'a' && (
                  <div className={styles.answerBlock}>
                    <div className={`${styles.aText} ${msg.isError ? styles.errorText : ''}`}>{msg.text}</div>
                    {msg.sources?.length > 0 && (
                      <div className={styles.sourcesLine}>
                        Sources: {msg.sources.map(sourceLabel).join(' | ')}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {isAsking && <div className={styles.thinkingText}>Agent is thinking...</div>}
          </div>
          <div className={styles.chatDockInput}>{askForm}</div>
        </aside>
      )}

      {!isChatOpen && <div className={styles.askBarContainer}>{askForm}</div>}
    </div>
  );
}

export default BriefingTab;

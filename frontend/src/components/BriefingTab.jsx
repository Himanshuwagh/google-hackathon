import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { fetchJson } from '../api';
import styles from './BriefingTab.module.css';
import ToolTracePanel from './ToolTracePanel';

const asArray = (value) => Array.isArray(value) ? value : [];

const itemText = (item) => {
  if (typeof item === 'string') return item;
  if (!item || typeof item !== 'object') return '';
  return item.text || item.point || item.warning || item.reason || item.message || item.description || item.title || '';
};

const textItems = (value) => asArray(value).map(itemText).filter(Boolean);

const formatGeneratedAt = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const publicSourceType = (source) => {
  const type = typeof source === 'string'
    ? source
    : source?.type || source?.source || source?.source_type || '';

  if (type === 'InternalDoc') return 'Company document';
  if (type === 'CompetitiveIntel') return 'Competitive intelligence';
  if (type === 'ClinicalTrials') return 'Clinical trial';
  return type || 'Source';
};

const isCompanyDocument = (source) =>
  publicSourceType(source) === 'Company document';

const sourceLabel = (source) => {
  if (!source) return '';
  if (typeof source === 'string') return publicSourceType(source);
  const type = publicSourceType(source);
  const id = isCompanyDocument(source)
    ? null
    : source.pmid || source.nctId || source.nct_id || source.id || source.source_id;
  const title = source.title || source.label || source.relevance;
  return [type, id, title].filter(Boolean).join(' · ');
};

const normalizePoint = (point, label) => {
  if (typeof point === 'string') return { text: point, label };
  if (!point?.point) return null;
  return {
    text: point.point,
    source: point.citation || sourceLabel(point.source) || sourceLabel(point),
    label,
    numbers: textItems(point.specific_numbers),
  };
};

const normalizeStandalonePoints = (briefing) =>
  asArray(briefing?.talking_points)
    .map((point) => normalizePoint(point))
    .filter(Boolean);

const normalizeDrugSections = (briefing) =>
  asArray(briefing?.drug_sections).map((section) => ({
    id: section.drug_id || section.drug_name,
    name: section.drug_name || section.drug_id || 'Drug detail',
    points: asArray(section.key_talking_points)
      .map((point) => normalizePoint(point, section.drug_name))
      .filter(Boolean),
    objections: asArray(section.known_objections_responses).map((item) =>
      typeof item === 'string'
        ? { objection: item, sources: [] }
        : {
            ...item,
            sources: asArray(item?.sources).map(sourceLabel).filter(Boolean),
          }
    ),
  }));

const normalizeStandaloneObjections = (briefing) =>
  briefing?.anticipated_objection ? [briefing.anticipated_objection] : [];

const normalizeWorkflowNotes = (briefing) => {
  const notes = briefing?.rep_workflow_notes || {};
  return {
    objective: itemText(notes.objective) || notes.objective || '',
    sampleReminders: [
      ...textItems(notes.sample_reminders),
      ...textItems(notes.planned_samples),
    ],
    followUpReminders: [
      ...textItems(notes.follow_up_reminders),
      ...textItems(notes.pending_action_items),
    ],
  };
};

const normalizeWarnings = (briefing) => textItems(briefing?.draft_warnings);

const normalizeEvidence = (briefing) =>
  asArray(briefing?.supporting_evidence).map((evidence) => {
    const rawUrl =
      evidence.pdf_url ||
      evidence.source_url ||
      evidence.url ||
      (evidence.pmid ? `https://pubmed.ncbi.nlm.nih.gov/${evidence.pmid}/` : null) ||
      null;
    const reference = evidence.pmid
      ? `PMID: ${evidence.pmid}`
      : evidence.nctId || evidence.nct_id
        ? evidence.nctId || evidence.nct_id
        : null;
    return {
      kind: publicSourceType(evidence),
      title: evidence.title || evidence.label || evidence.drug_label || publicSourceType(evidence) || 'Evidence',
      description: evidence.relevance || evidence.label || evidence.summary || evidence.content,
      meta: evidence.source_citation || evidence.journal || evidence.source_label,
      reference,
      url: rawUrl,
    };
  });

const hasBriefingData = (data) => Boolean(data?.briefing);

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
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        type: 'a',
        text: error.message || 'Could not answer this question right now.',
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
  const standalonePoints = useMemo(() => normalizeStandalonePoints(briefing), [briefing]);
  const drugSections = useMemo(() => normalizeDrugSections(briefing), [briefing]);
  const standaloneObjections = useMemo(() => normalizeStandaloneObjections(briefing), [briefing]);
  const evidence = useMemo(() => normalizeEvidence(briefing), [briefing]);
  const workflowNotes = useMemo(() => normalizeWorkflowNotes(briefing), [briefing]);
  const transitionNotes = useMemo(() => textItems(briefing?.cross_drug_notes), [briefing]);
  const warnings = useMemo(() => normalizeWarnings(briefing), [briefing]);
  const talkingPointCount = standalonePoints.length + drugSections.reduce(
    (total, section) => total + section.points.length,
    0
  );
  const objectionCount = standaloneObjections.length + drugSections.reduce(
    (total, section) => total + section.objections.length,
    0
  );
  const generatedAt = formatGeneratedAt(briefing?.generated_at);
  const hasWorkflowReminders = Boolean(
    workflowNotes.sampleReminders.length ||
    workflowNotes.followUpReminders.length
  );
  const hasReadyStatusWithoutBriefing = Boolean(
    !briefing &&
    (detail?.status === 'briefing_ready' || detail?.status === 'needs_review')
  );
  const isProcessingBriefing = Boolean(
    isGenerating ||
    detail?.status === 'agent_processing' ||
    meeting.status === 'processing'
  );

  if (isLoading && !detail) {
    return (
      <div className={styles.stateMessage}>
        <strong>Loading briefing</strong>
        <span>Fetching meeting prep, generated notes, and trace history.</span>
      </div>
    );
  }

  if (error && !detail?.briefing) {
    return (
      <div className={styles.stateMessage}>
        <strong>Briefing unavailable</strong>
        <span>{error}</span>
      </div>
    );
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
        {!briefing && (
          <section className={styles.section}>
            <div className={styles.sectionLabel}>Briefing Status</div>
            <div className={styles.statusPanel}>
              <strong>
                {detail?.status === 'failed'
                  ? 'Generation failed'
                  : hasReadyStatusWithoutBriefing
                    ? 'Saved briefing needs repair'
                    : isProcessingBriefing
                      ? 'Generating briefing'
                      : 'Starting generation'}
              </strong>
              <p>
                {detail?.status === 'failed'
                  ? detail.error_message || meeting.errorMessage || 'The agent could not complete this briefing.'
                  : hasReadyStatusWithoutBriefing
                    ? 'The meeting is marked ready, but the generated briefing payload is not available in this view.'
                    : isProcessingBriefing
                      ? 'The agent pipeline is running. Trace steps will update here as the backend saves results.'
                      : 'The meeting is queued for briefing generation.'}
              </p>
              {(detail?.status === 'failed' || hasReadyStatusWithoutBriefing) && (
                <button
                  type="button"
                  className={styles.statusAction}
                  onClick={handleRegenerate}
                  disabled={isGenerating}
                >
                  {isGenerating ? 'Starting...' : 'Regenerate briefing'}
                </button>
              )}
            </div>
          </section>
        )}

        {briefing && (
          <>
            <section className={styles.overview}>
              <div className={styles.overviewMain}>
                <div className={styles.sectionLabel}>Meeting Prep</div>
                <h2>Briefing strategy</h2>
                {workflowNotes.objective && (
                  <div className={styles.objectiveLine}>
                    <span>Objective</span>
                    <strong>{workflowNotes.objective}</strong>
                  </div>
                )}
                {briefing.rep_summary_report ? (
                  <div className={styles.summaryBox}>{briefing.rep_summary_report}</div>
                ) : (
                  talkingPointCount > 0 && (
                    <div className={styles.summaryBox}>
                      Talking points, objection responses, and supporting evidence are ready for this meeting.
                    </div>
                  )
                )}
              </div>

              <div className={styles.signalGrid}>
                <div className={styles.signalCell}>
                  <span>Drugs</span>
                  <strong>{drugSections.length || (talkingPointCount > 0 ? 1 : 0)}</strong>
                </div>
                <div className={styles.signalCell}>
                  <span>Talking points</span>
                  <strong>{talkingPointCount}</strong>
                </div>
                <div className={styles.signalCell}>
                  <span>Objections</span>
                  <strong>{objectionCount}</strong>
                </div>
                <div className={styles.signalCell}>
                  <span>Evidence</span>
                  <strong>{evidence.length}</strong>
                </div>
                {generatedAt && (
                  <div className={`${styles.signalCell} ${styles.generatedSignalCell}`}>
                    <span>Generated</span>
                    <strong>{generatedAt}</strong>
                  </div>
                )}
              </div>
            </section>

            {warnings.length > 0 && (
              <section className={styles.reviewStrip}>
                <div className={styles.sectionLabel}>Review Notes</div>
                <div className={styles.reviewList}>
                  {warnings.map((warning, index) => (
                    <div key={`${warning}-${index}`} className={styles.reviewItem}>{warning}</div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {(drugSections.length > 0 || standalonePoints.length > 0 || hasWorkflowReminders || transitionNotes.length > 0) && (
          <div className={styles.prepLayout}>
            <div className={styles.conversationColumn}>
              {drugSections.length > 0 && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div className={styles.sectionLabel}>Conversation Plan</div>
                    <h3>Drug details</h3>
                  </div>
                  <div className={styles.drugStack}>
                    {drugSections.map((section, sectionIndex) => (
                      <article key={section.id || `${section.name}-${sectionIndex}`} className={styles.drugPanel}>
                        <header className={styles.drugHeader}>
                          <div>
                            <div className={styles.drugEyebrow}>Drug {sectionIndex + 1}</div>
                            <h4>{section.name}</h4>
                          </div>
                          <span>{section.points.length} points</span>
                        </header>

                        {section.points.length > 0 && (
                          <div className={styles.pointList}>
                            {section.points.map((point, index) => (
                              <div key={`${point.text}-${index}`} className={styles.pointCard}>
                                <div className={styles.pointNumber}>{index + 1}</div>
                                <div className={styles.pointContent}>
                                  <p className={styles.pointText}>{point.text}</p>
                                  {point.numbers?.length > 0 && (
                                    <div className={styles.numberRow}>
                                      {point.numbers.map((number) => (
                                        <span key={number} className={styles.numberChip}>{number}</span>
                                      ))}
                                    </div>
                                  )}
                                  {point.source && <div className={styles.pointSource}>Source: {point.source}</div>}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {section.objections.length > 0 && (
                          <div className={styles.objectionGroup}>
                            <div className={styles.groupLabel}>Objections to prepare</div>
                            {section.objections.map((item, index) => (
                              <div key={`${item.objection || section.name}-${index}`} className={styles.objectionBox}>
                                {item.objection && <p className={styles.objectionPrompt}>{item.objection}</p>}
                                {item.response && <p><strong>Response:</strong> {item.response}</p>}
                                {item.competitive_context && <p className={styles.objectionContext}>{item.competitive_context}</p>}
                                {item.sources?.length > 0 && (
                                  <div className={styles.objectionSources}>Sources: {item.sources.join(' | ')}</div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                </section>
              )}

              {standalonePoints.length > 0 && (
                <section className={styles.section}>
                  <div className={styles.sectionHeading}>
                    <div className={styles.sectionLabel}>Talking Points</div>
                    <h3>{drugSections.length > 0 ? 'Additional points' : 'Meeting points'}</h3>
                  </div>
                  <div className={styles.pointList}>
                    {standalonePoints.map((point, index) => (
                      <div key={`${point.text}-${index}`} className={styles.pointCard}>
                        <div className={styles.pointNumber}>{index + 1}</div>
                        <div className={styles.pointContent}>
                          {point.label && <div className={styles.pointLabel}>{point.label}</div>}
                          <p className={styles.pointText}>{point.text}</p>
                          {point.numbers?.length > 0 && (
                            <div className={styles.numberRow}>
                              {point.numbers.map((number) => (
                                <span key={number} className={styles.numberChip}>{number}</span>
                              ))}
                            </div>
                          )}
                          {point.source && <div className={styles.pointSource}>Source: {point.source}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>

            <aside className={styles.prepAside}>
              {hasWorkflowReminders && (
                <section className={styles.sideSection}>
                  <div className={styles.sectionHeading}>
                    <div className={styles.sectionLabel}>Rep Workflow</div>
                    <h3>Before and after the visit</h3>
                  </div>
                  {workflowNotes.sampleReminders.length > 0 && (
                    <div className={styles.workflowBlock}>
                      <div className={styles.groupLabel}>Sample reminders</div>
                      <div className={styles.reminderList}>
                        {workflowNotes.sampleReminders.map((reminder, index) => (
                          <div key={`${reminder}-${index}`} className={styles.reminderItem}>{reminder}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  {workflowNotes.followUpReminders.length > 0 && (
                    <div className={styles.workflowBlock}>
                      <div className={styles.groupLabel}>Follow-up reminders</div>
                      <div className={styles.reminderList}>
                        {workflowNotes.followUpReminders.map((reminder, index) => (
                          <div key={`${reminder}-${index}`} className={styles.reminderItem}>{reminder}</div>
                        ))}
                      </div>
                    </div>
                  )}
                </section>
              )}

              {transitionNotes.length > 0 && (
                <section className={styles.sideSection}>
                  <div className={styles.sectionHeading}>
                    <div className={styles.sectionLabel}>Sequence</div>
                    <h3>Conversation transitions</h3>
                  </div>
                  <ol className={styles.transitionList}>
                    {transitionNotes.map((note, index) => (
                      <li key={`${note}-${index}`}>{note}</li>
                    ))}
                  </ol>
                </section>
              )}
            </aside>
          </div>
        )}

        {standaloneObjections.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionHeading}>
              <div className={styles.sectionLabel}>Anticipated Objections</div>
              <h3>General response prep</h3>
            </div>
            <div className={styles.generalObjectionGrid}>
              {standaloneObjections.map((item, index) => (
                <div key={index} className={styles.objectionBox}>
                  {typeof item === 'string' ? (
                    <p>{item}</p>
                  ) : (
                    <>
                      {item.drug_name && <p><strong>{item.drug_name}</strong></p>}
                      {item.objection && <p className={styles.objectionPrompt}>{item.objection}</p>}
                      {item.response && <p><strong>Response:</strong> {item.response}</p>}
                      {item.competitive_context && <p className={styles.objectionContext}>{item.competitive_context}</p>}
                    </>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {evidence.length > 0 && (
          <section className={styles.section}>
            <div className={styles.sectionHeading}>
              <div className={styles.sectionLabel}>Evidence Used</div>
              <h3>Sources behind the briefing</h3>
            </div>
            <div className={styles.evidenceGrid}>
              {evidence.map((item, index) => {
                const content = (
                  <>
                    <div className={styles.evidenceTopline}>
                      <span className={styles.evidenceKind}>{item.kind}</span>
                      {item.url && <span className={styles.evidenceAction}>Open source</span>}
                    </div>
                    <div className={styles.evidenceTitle}>{item.title}</div>
                    {item.description && <div className={styles.evidenceDesc}>{item.description}</div>}
                    {item.meta && <div className={styles.evidenceMeta}>{item.meta}</div>}
                    {!item.meta && item.reference && <div className={styles.evidenceMeta}>{item.reference}</div>}
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

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <div className={styles.sectionLabel}>Agent Trace</div>
            <h3>Generation history</h3>
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
                Ask about this doctor, briefing evidence, objections, or the project workflow.
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

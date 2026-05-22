import { useEffect, useMemo, useState } from 'react';
import { WS_BASE_URL } from '../api';
import styles from './AgentLogTab.module.css';

const levelType = (level) => {
  if (level === 'error') return 'warn';
  if (level === 'success') return 'success';
  return 'default';
};

function AgentLogTab({ meeting, onRefreshMeetings }) {
  const [events, setEvents] = useState([]);
  const [connectionState, setConnectionState] = useState('connecting');

  useEffect(() => {
    const socket = new WebSocket(`${WS_BASE_URL}/ws/log/${meeting.id}`);
    let refreshTimer = null;

    socket.onopen = () => {
      setConnectionState('connected');
    };

    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === 'complete') {
        setConnectionState('complete');
        refreshTimer = window.setTimeout(() => onRefreshMeetings?.(), 500);
        return;
      }
      if (payload.type === 'waiting') {
        setEvents(prev => [...prev, {
          timestamp: '',
          tag: 'WAITING',
          message: 'Meeting is queued. Agent logs will appear when processing starts.',
          level: 'info',
        }]);
        return;
      }
      if (payload.type === 'error') {
        setConnectionState('error');
        setEvents(prev => [...prev, {
          timestamp: '',
          tag: payload.code || 'ERROR',
          message: payload.message,
          level: 'error',
        }]);
        return;
      }
      setEvents(prev => [...prev, payload]);
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
  }, [meeting.id, onRefreshMeetings]);

  const subtitle = useMemo(() => {
    if (connectionState === 'complete') return 'Complete';
    if (connectionState === 'connected') return 'Live connection open';
    if (connectionState === 'error') return 'Connection error';
    if (connectionState === 'closed') return 'Connection closed';
    return 'Connecting to backend stream';
  }, [connectionState]);

  return (
    <div className={styles.container}>
      <div className={styles.introHeader}>
        <div className={styles.introTitle}>Agent Trace</div>
        <div className={styles.introSubtitle}>{subtitle}</div>
      </div>

      <div className={styles.timeline}>
        {events.length === 0 && (
          <div className={styles.emptyLog}>No agent events have been emitted for this meeting yet.</div>
        )}
        {events.map((event, index) => {
          const type = levelType(event.level);
          return (
            <div key={`${event.timestamp}-${event.tag}-${index}`} className={`${styles.step} ${styles.visible}`}>
              <div className={styles.stepLeft}>
                <div className={styles.time}>{event.timestamp || '--:--:--'}</div>
                <div className={styles.lineWrapper}>
                  <div className={styles.iconCircle}>{event.tag?.slice(0, 1) || 'L'}</div>
                  {index < events.length - 1 && <div className={styles.connector}></div>}
                </div>
              </div>
              
              <div className={styles.stepRight}>
                <div className={styles.stepTitle}>{event.tag || 'Log'}</div>
                <div className={styles.card}>
                  <div className={`${styles.detailRow} ${styles[`detail-${type}`]}`}>
                    <span className={styles.detailIcon}>{type === 'success' ? '✓' : type === 'warn' ? '!' : '·'}</span>
                    <span className={styles.detailText}>{event.message}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AgentLogTab;

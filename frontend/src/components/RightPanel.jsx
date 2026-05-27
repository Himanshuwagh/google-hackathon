import { useState } from 'react';
import styles from './RightPanel.module.css';
import BriefingTab from './BriefingTab';
import AboutTab from './AboutTab';

function EmptyState({ meetingsCount, selectedDate, onAddMeeting }) {
  const selectedDateLabel = selectedDate.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });

  return (
    <div className={styles.emptyState}>
      <h2 className="serif">Good morning, Rakesh.</h2>
      <p>
        You have {meetingsCount} meetings on {selectedDateLabel}.<br/>
        Select one to view the briefing.
      </p>
      <button type="button" className={styles.viewBtn} onClick={onAddMeeting}>
        Add meeting
      </button>
    </div>
  );
}

function RightPanel({
  selectedMeeting,
  meetingsCount = 0,
  selectedDate = new Date(),
  onAddMeeting,
  onRefreshMeetings,
}) {
  const [activeTab, setActiveTab] = useState('briefing'); // briefing, about
  const [briefingAction, setBriefingAction] = useState(null);

  if (!selectedMeeting) {
    return (
      <main className={styles.rightPanel}>
        <EmptyState meetingsCount={meetingsCount} selectedDate={selectedDate} onAddMeeting={onAddMeeting} />
      </main>
    );
  }

  const getStatusText = (meeting) => {
    const { status } = meeting;
    switch (status) {
      case 'ready': return 'Briefing Ready';
      case 'processing': return 'Processing...';
      case 'waiting': return 'Waiting';
      case 'failed': return 'Failed';
      default: return '';
    }
  };

  return (
    <main className={styles.rightPanel}>
      <div className={styles.headerStrip}>
        <div className={styles.headerMain}>
          <h1 className="serif">{selectedMeeting.doctor}</h1>
          <div className={styles.detailsRow}>
            {selectedMeeting.specialty} · {selectedMeeting.hospital}
          </div>
        </div>
        <div className={styles.headerRight}>
          <div className={styles.statusWrap}>
            <span className={`${styles.statusDot} ${styles[`status-${selectedMeeting.status}`]}`}></span>
            <span className={styles[`statusText-${selectedMeeting.status}`]}>{getStatusText(selectedMeeting)}</span>
          </div>
          <div className={styles.dateTime}>
            {selectedMeeting.dateLabel || selectedMeeting.date} · {selectedMeeting.time} ({selectedMeeting.duration})
          </div>
        </div>
      </div>
      
      <div className={styles.tabRow}>
        <div className={styles.tabGroup}>
          <button 
            className={`${styles.tab} ${activeTab === 'briefing' ? styles.activeTab : ''}`}
            onClick={() => setActiveTab('briefing')}
          >
            Briefing
          </button>
          <button 
            className={`${styles.tab} ${activeTab === 'about' ? styles.activeTab : ''}`}
            onClick={() => setActiveTab('about')}
          >
            About
          </button>
        </div>
        {activeTab === 'briefing' && briefingAction?.visible && (
          <button
            type="button"
            className={styles.regenerateBtn}
            onClick={briefingAction.onClick}
            disabled={briefingAction.disabled}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M21 12a9 9 0 1 1-2.64-6.36" />
              <path d="M21 3v6h-6" />
            </svg>
            {briefingAction.label}
          </button>
        )}
      </div>

      <div className={styles.tabContent}>
        {activeTab === 'briefing' && (
          <BriefingTab
            key={selectedMeeting.id}
            meeting={selectedMeeting}
            onRefreshMeetings={onRefreshMeetings}
            onRegenerateControlChange={setBriefingAction}
          />
        )}
        {activeTab === 'about' && <AboutTab key={selectedMeeting.id} meeting={selectedMeeting} />}
      </div>
    </main>
  );
}

export default RightPanel;

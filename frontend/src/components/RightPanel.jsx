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
      <h2>Good morning, Rakesh.</h2>
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
      case 'ready': return 'Ready';
      case 'processing': return 'Processing';
      case 'waiting': return 'Waiting';
      case 'failed': return 'Failed';
      default: return '';
    }
  };

  return (
    <main className={styles.rightPanel}>
      <div className={styles.headerPanel}>
        <div className={styles.headerTop}>
          <div className={styles.doctorLine}>
            <h1>{selectedMeeting.doctor}</h1>
            <span className={`${styles.statusBadge} ${styles[`status-${selectedMeeting.status}`]}`}>
              {getStatusText(selectedMeeting)}
            </span>
          </div>
          <div className={styles.detailsRow}>
            {selectedMeeting.specialty} · {selectedMeeting.hospital} · {selectedMeeting.dateLabel || selectedMeeting.date} · {selectedMeeting.time} ({selectedMeeting.duration})
          </div>
        </div>
        
        <div className={styles.headerBottom}>
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
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                <path d="M21 3v6h-6" />
              </svg>
              {briefingAction.label}
            </button>
          )}
        </div>
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

import styles from './Sidebar.module.css';

function Sidebar({
  meetings,
  selectedMeetingId,
  onSelectMeeting,
  isOpen,
  selectedDate,
  isLoading,
  error,
  width,
  onResizeStart,
  onAddMeeting,
}) {
  const isToday = (date) => {
    if (!date) return true;
    const today = new Date();
    return date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear();
  };

  const headerText = isToday(selectedDate) 
    ? "TODAY'S MEETINGS" 
    : `MEETINGS FOR ${selectedDate ? selectedDate.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }).toUpperCase() : ''}`;

  return (
    <aside className={`${styles.sidebar} ${isOpen ? styles.open : ''}`} style={{ '--sidebar-width': `${width}px` }}>
      <div className={styles.header}>
        <div className={styles.headerCopy}>
          <span className={styles.headerLabel}>{headerText}</span>
          <span className={styles.headerDate}>
            {selectedDate?.toLocaleDateString('en-GB', {
              weekday: 'short',
              day: 'numeric',
              month: 'short',
            })}
          </span>
        </div>
        <span className={styles.badge}>{meetings.length} {meetings.length === 1 ? 'meeting' : 'meetings'}</span>
      </div>
      
      <div className={styles.meetingList}>
        {isLoading && <div className={styles.emptyState}>Loading meetings...</div>}
        {!isLoading && error && <div className={styles.errorState}>{error}</div>}
        {!isLoading && !error && meetings.length === 0 && (
          <div className={styles.emptyState}>No meetings for this date.</div>
        )}
        {!isLoading && !error && meetings.map((meeting) => (
          <div 
            key={meeting.id} 
            className={`${styles.meetingItem} ${selectedMeetingId === meeting.id ? styles.active : ''}`}
            onClick={() => onSelectMeeting(meeting.id)}
          >
            <div className={styles.meetingHeader}>
              <span className={`${styles.statusDot} ${styles[`status-${meeting.status}`]}`}></span>
              <span className={styles.doctorName}>{meeting.doctor}</span>
            </div>
            <div className={styles.meetingDetails}>
              {meeting.drug} · {meeting.time}
            </div>
            <div className={styles.hospital}>
              {meeting.hospital}
            </div>
          </div>
        ))}
      </div>
      
      <div className={styles.separator}></div>
      
      <button className={styles.addBtn} onClick={onAddMeeting}>
        <span>+</span>
        Add Meeting
      </button>
      <button
        type="button"
        className={styles.resizeHandle}
        onPointerDown={onResizeStart}
        aria-label="Resize meetings sidebar"
      />
    </aside>
  );
}

export default Sidebar;

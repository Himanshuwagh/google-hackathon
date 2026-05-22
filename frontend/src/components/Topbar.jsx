import styles from './Topbar.module.css';

function Topbar({ isCalendarOpen, onToggleCalendar, selectedDate }) {
  const formattedDate = new Intl.DateTimeFormat('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  }).format(selectedDate || new Date());

  return (
    <header className={styles.topbar}>
      <div className={styles.logo}>PharmaOps</div>
      <div 
        className={`${styles.date} ${isCalendarOpen ? styles.dateActive : ''}`}
        onClick={onToggleCalendar}
      >
        {formattedDate}
        <svg 
          className={styles.dropdownIcon}
          style={{ transform: isCalendarOpen ? 'rotate(180deg)' : 'none' }}
          width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg"
        >
          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className={styles.user}>
        <div className={styles.avatar}>RS</div>
        <span className={styles.userName}>Rakesh Sharma</span>
        <svg width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
    </header>
  );
}

export default Topbar;

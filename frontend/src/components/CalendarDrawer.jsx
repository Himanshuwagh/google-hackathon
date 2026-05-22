import { useMemo, useState } from 'react';
import styles from './CalendarDrawer.module.css';

const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const daysOfWeek = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const viewOptions = ['Month', 'Week', 'Day'];

const getLocalDateKey = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const parseMeetingDate = (value) => {
  if (value instanceof Date) return value;
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [year, month, day] = value.split('-').map(Number);
    return new Date(year, month - 1, day);
  }
  return new Date(value);
};

const addDays = (date, amount) => {
  const nextDate = new Date(date);
  nextDate.setDate(date.getDate() + amount);
  return nextDate;
};

const startOfWeek = (date) => addDays(date, -date.getDay());

const isSameDay = (d1, d2) =>
  d1.getFullYear() === d2.getFullYear() &&
  d1.getMonth() === d2.getMonth() &&
  d1.getDate() === d2.getDate();

function CalendarDrawer({ isOpen, onClose, selectedDate, onSelectDate, meetings }) {
  const [currentMonth, setCurrentMonth] = useState(new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1));
  const [currentDate, setCurrentDate] = useState(selectedDate);
  const [view, setView] = useState('Month');
  const [hoveredDate, setHoveredDate] = useState(null);

  const meetingsByDate = useMemo(() => {
    return meetings.reduce((groups, meeting) => {
      const key = getLocalDateKey(parseMeetingDate(meeting.date));
      groups[key] = [...(groups[key] || []), meeting];
      return groups;
    }, {});
  }, [meetings]);

  if (!isOpen) return null;

  const today = new Date();

  const handlePrevious = () => {
    if (view === 'Month') {
      setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
      return;
    }

    const nextDate = addDays(currentDate, view === 'Week' ? -7 : -1);
    setCurrentDate(nextDate);
    setCurrentMonth(new Date(nextDate.getFullYear(), nextDate.getMonth(), 1));
  };

  const handleNext = () => {
    if (view === 'Month') {
      setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
      return;
    }

    const nextDate = addDays(currentDate, view === 'Week' ? 7 : 1);
    setCurrentDate(nextDate);
    setCurrentMonth(new Date(nextDate.getFullYear(), nextDate.getMonth(), 1));
  };

  const handleToday = () => {
    const newToday = new Date();
    setCurrentMonth(new Date(newToday.getFullYear(), newToday.getMonth(), 1));
    setCurrentDate(newToday);
    onSelectDate(newToday);
  };

  const handleSelectDate = (date) => {
    setCurrentDate(date);
    setHoveredDate(null);
    setCurrentMonth(new Date(date.getFullYear(), date.getMonth(), 1));
    onSelectDate(date);
    onClose();
  };

  const handleViewChange = (nextView) => {
    setView(nextView);
    if (nextView === 'Month') {
      setCurrentMonth(new Date(currentDate.getFullYear(), currentDate.getMonth(), 1));
    }
  };

  const startDay = currentMonth.getDay();
  const daysInMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 0).getDate();
  const daysInPrevMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 0).getDate();

  const monthDays = [];
  
  for (let i = 0; i < startDay; i++) {
    const day = daysInPrevMonth - startDay + i + 1;
    const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, day);
    monthDays.push({ date, isCurrentMonth: false });
  }
  
  for (let i = 1; i <= daysInMonth; i++) {
    const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), i);
    monthDays.push({ date, isCurrentMonth: true });
  }
  
  const remainingDays = 42 - monthDays.length;
  for (let i = 1; i <= remainingDays; i++) {
    const date = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, i);
    monthDays.push({ date, isCurrentMonth: false });
  }

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(currentDate), index));
  const selectedMeetings = meetingsByDate[getLocalDateKey(currentDate)] || [];

  const renderMeetingChip = (meeting, compact = false) => (
    <div key={meeting.id} className={`${styles.eventPill} ${compact ? styles.compactEventPill : ''}`} title={`${meeting.time} ${meeting.doctor || meeting.title || 'Meeting'}`}>
      <span className={styles.eventTime}>{meeting.time}</span>
      <span className={styles.eventTitle}>{meeting.doctor || meeting.title}</span>
    </div>
  );

  const renderDayButton = (dayObj) => {
    const dayMeetings = meetingsByDate[getLocalDateKey(dayObj.date)] || [];
    const isSelected = isSameDay(dayObj.date, selectedDate);
    const isToday = isSameDay(dayObj.date, today);
    const extraMeetings = Math.max(dayMeetings.length - 2, 0);

    return (
      <button
        key={getLocalDateKey(dayObj.date)}
        type="button"
        className={`${styles.dayCell} ${!dayObj.isCurrentMonth ? styles.notCurrentMonth : ''} ${isSelected ? styles.selectedDay : ''}`}
        onClick={() => handleSelectDate(dayObj.date)}
        onMouseEnter={() => setHoveredDate(dayObj.date)}
        onFocus={() => setHoveredDate(dayObj.date)}
        aria-label={`${dayObj.date.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })}, ${dayMeetings.length} meetings`}
      >
        <div className={styles.dayNumberContainer}>
          <span className={`${styles.dayNumber} ${isToday ? styles.todayNumber : ''}`}>
            {dayObj.date.getDate()}
          </span>
          {dayMeetings.length > 0 && <span className={styles.meetingCount}>{dayMeetings.length}</span>}
        </div>
        <div className={styles.eventsContainer}>
          {dayMeetings.slice(0, 2).map((meeting) => renderMeetingChip(meeting))}
          {extraMeetings > 0 && <span className={styles.moreEvents}>+{extraMeetings} more</span>}
        </div>
      </button>
    );
  };

  const headerTitle = view === 'Month'
    ? `${monthNames[currentMonth.getMonth()]} ${currentMonth.getFullYear()}`
    : currentDate.toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const focusDate = hoveredDate || currentDate || selectedDate;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.calendarContainer} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <div className={styles.currentDateBox}>
              <div className={styles.currentMonthName}>{focusDate.toLocaleString('en-US', { month: 'short' }).toUpperCase()}</div>
              <div className={styles.currentDayNum}>{focusDate.getDate()}</div>
              <div className={styles.currentWeekday}>{focusDate.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()}</div>
            </div>
            <div className={styles.monthSelector}>
              <span className={styles.eyebrow}>Calendar</span>
              <h2>{headerTitle}</h2>
            </div>
          </div>
          
          <div className={styles.headerRight}>
            <div className={styles.navGroup}>
              <button className={styles.iconButton} onClick={handlePrevious} aria-label={`Previous ${view.toLowerCase()}`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
              </button>
              <button className={styles.todayButton} onClick={handleToday}>Today</button>
              <button className={styles.iconButton} onClick={handleNext} aria-label={`Next ${view.toLowerCase()}`}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
              </button>
            </div>
            <div className={styles.viewSwitch} aria-label="Calendar view">
              {viewOptions.map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`${styles.viewButton} ${view === option ? styles.viewButtonActive : ''}`}
                  onClick={() => handleViewChange(option)}
                >
                  {option}
                </button>
              ))}
            </div>
            <button className={styles.closeButton} onClick={onClose} aria-label="Close calendar">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
            </button>
          </div>
        </div>

        <div className={styles.gridContainer}>
          {view === 'Month' && (
            <>
              <div className={styles.daysHeader}>
                {daysOfWeek.map(day => (
                  <div key={day} className={styles.dayHeaderCell}>{day}</div>
                ))}
              </div>
              <div className={styles.daysGrid}>
                {monthDays.map(renderDayButton)}
              </div>
            </>
          )}

          {view === 'Week' && (
            <>
              <div className={styles.weekHeader}>
                {weekDays.map((date) => (
                  <div key={getLocalDateKey(date)} className={styles.weekHeaderCell}>
                    <span>{date.toLocaleDateString('en-US', { weekday: 'short' })}</span>
                    <strong>{date.getDate()}</strong>
                  </div>
                ))}
              </div>
              <div className={styles.weekGrid}>
                {weekDays.map((date) => renderDayButton({ date, isCurrentMonth: date.getMonth() === currentDate.getMonth() }))}
              </div>
            </>
          )}

          {view === 'Day' && (
            <div className={styles.dayAgenda}>
              <div className={styles.agendaDateRail}>
                <span>{currentDate.toLocaleDateString('en-GB', { weekday: 'short' })}</span>
                <strong>{currentDate.getDate()}</strong>
              </div>
              <div className={styles.agendaList}>
                {selectedMeetings.length > 0 ? (
                  selectedMeetings.map((meeting) => (
                    <button key={meeting.id} type="button" className={styles.agendaItem} onClick={() => handleSelectDate(currentDate)}>
                      <span className={styles.agendaTime}>{meeting.time}</span>
                      <span className={styles.agendaContent}>
                        <strong>{meeting.doctor || meeting.title}</strong>
                        <span>{meeting.drug} · {meeting.hospital}</span>
                      </span>
                    </button>
                  ))
                ) : (
                  <div className={styles.emptyAgenda}>No meetings scheduled for this date.</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CalendarDrawer;

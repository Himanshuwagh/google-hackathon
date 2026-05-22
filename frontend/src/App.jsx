import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Topbar from './components/Topbar';
import Sidebar from './components/Sidebar';
import RightPanel from './components/RightPanel';
import CalendarDrawer from './components/CalendarDrawer';
import AddMeetingModal from './components/AddMeetingModal';
import { fetchJson } from './api';
import styles from './App.module.css';

const today = new Date();
const REP_ID = 'rep_rakesh_sharma';

/** Read a value from the current URL search params. */
const readParam = (key) => new URLSearchParams(window.location.search).get(key);

/** Write key/value pairs into the URL search params without a full navigation. */
const writeParams = (updates) => {
  const params = new URLSearchParams(window.location.search);
  for (const [key, value] of Object.entries(updates)) {
    if (value == null) params.delete(key);
    else params.set(key, value);
  }
  const query = params.toString();
  const url = query ? `${window.location.pathname}?${query}` : window.location.pathname;
  window.history.replaceState(null, '', url);
};

/** Parse a YYYY-MM-DD string into a local Date, falling back to `today`. */
const parseDateParam = (value) => {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
};

const SIDEBAR_MIN_WIDTH = 260;
const SIDEBAR_MAX_WIDTH = 430;

const formatDateKey = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const addDays = (date, amount) => {
  const nextDate = new Date(date);
  nextDate.setDate(date.getDate() + amount);
  return nextDate;
};

const displayDate = (dateKey) => {
  if (!dateKey) return '';
  const [year, month, day] = dateKey.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  });
};

const mapStatus = (status) => {
  switch (status) {
    case 'briefing_ready':
    case 'needs_review':
      return 'ready';
    case 'agent_processing':
    case 'processing':
      return 'processing';
    case 'agent_error':
    case 'failed':
      return 'failed';
    case 'scheduled':
      return 'waiting';
    default:
      return status || 'waiting';
  }
};

const mapMeeting = (meeting) => ({
  id: meeting.meeting_id,
  doctor: meeting.hcp_name,
  specialty: meeting.hcp_specialty,
  hospital: meeting.hospital,
  drug: meeting.drug_name,
  time: meeting.meeting_time_display,
  duration: `${meeting.duration_mins} min`,
  date: meeting.meeting_date_key,
  dateLabel: displayDate(meeting.meeting_date_key),
  status: mapStatus(meeting.status),
  rawStatus: meeting.status,
  briefingId: meeting.briefing_id,
  errorMessage: meeting.error_message,
});

function App() {
  const [selectedMeetingId, setSelectedMeetingId] = useState(() => readParam('meeting'));
  const [isSidebarOpenOnMobile, setIsSidebarOpenOnMobile] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  
  const [selectedDate, setSelectedDate] = useState(() => parseDateParam(readParam('date')) || today);
  const [isCalendarOpen, setIsCalendarOpen] = useState(false);
  const [meetings, setMeetings] = useState([]);
  const [meetingsError, setMeetingsError] = useState('');
  const [isLoadingMeetings, setIsLoadingMeetings] = useState(true);
  const [isAddMeetingOpen, setIsAddMeetingOpen] = useState(false);
  const [deletingMeetingId, setDeletingMeetingId] = useState(null);
  const [toastMessage, setToastMessage] = useState('');
  const hasAutoSelectedMeeting = useRef(false);

  const loadMeetings = useCallback(async (signal) => {
    const startDate = formatDateKey(addDays(today, -365));
    const endDate = formatDateKey(addDays(today, 365));

    setMeetingsError('');
    try {
      const params = new URLSearchParams({
        rep_id: REP_ID,
        start_date: startDate,
        end_date: endDate,
      });
      const data = await fetchJson(`/meetings?${params}`, { signal });
      const mappedMeetings = data.map(mapMeeting);
      setMeetings(mappedMeetings);

      if (!hasAutoSelectedMeeting.current && mappedMeetings.length > 0) {
        // If URL already has a date/meeting, honour it; otherwise pick today's first meeting.
        const urlDate = readParam('date');
        const urlMeeting = readParam('meeting');

        if (urlDate && urlMeeting && mappedMeetings.some(m => m.id === urlMeeting)) {
          // URL state is valid — keep it (already initialised from useState)
          hasAutoSelectedMeeting.current = true;
        } else if (urlDate && !urlMeeting) {
          // Date in URL but no meeting — auto-pick first meeting on that date
          const dateMatch = mappedMeetings.find(m => m.date === urlDate);
          if (dateMatch) {
            setSelectedMeetingId(dateMatch.id);
            writeParams({ meeting: dateMatch.id });
          }
          hasAutoSelectedMeeting.current = true;
        } else {
          const todayKey = formatDateKey(today);
          const initialMeeting = mappedMeetings.find(meeting => meeting.date === todayKey) || mappedMeetings[0];
          const [year, month, day] = initialMeeting.date.split('-').map(Number);
          const initialDate = new Date(year, month - 1, day);
          setSelectedDate(initialDate);
          setSelectedMeetingId(initialMeeting.id);
          writeParams({ date: initialMeeting.date, meeting: initialMeeting.id });
          hasAutoSelectedMeeting.current = true;
        }
      }
      return mappedMeetings;
    } catch (error) {
      if (error.name !== 'AbortError') {
        setMeetingsError(error.message || 'Could not load meetings');
        setMeetings([]);
      }
      return [];
    } finally {
      if (!signal?.aborted) {
        setIsLoadingMeetings(false);
      }
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function loadInitialMeetings() {
      await loadMeetings(controller.signal);
    }

    loadInitialMeetings();
    const intervalId = window.setInterval(() => {
      loadMeetings();
    }, 8000);

    return () => {
      controller.abort();
      window.clearInterval(intervalId);
    };
  }, [loadMeetings]);

  const selectedMeeting = meetings.find(m => m.id === selectedMeetingId);
  
  const formattedSelectedDate = formatDateKey(selectedDate);
  const filteredMeetings = useMemo(
    () => meetings.filter(m => m.date === formattedSelectedDate),
    [formattedSelectedDate, meetings]
  );

  const handleSelectDate = (date) => {
    setSelectedDate(date);
    setSelectedMeetingId(null);
    writeParams({ date: formatDateKey(date), meeting: null });
  };

  const handleSelectMeeting = useCallback((meetingId) => {
    setSelectedMeetingId(meetingId);
    writeParams({ meeting: meetingId });
  }, []);

  const handleSidebarResizeStart = useCallback((event) => {
    event.preventDefault();
    const startX = event.clientX;
    const startWidth = sidebarWidth;

    const handlePointerMove = (moveEvent) => {
      const nextWidth = Math.min(
        SIDEBAR_MAX_WIDTH,
        Math.max(SIDEBAR_MIN_WIDTH, startWidth + moveEvent.clientX - startX)
      );
      setSidebarWidth(nextWidth);
    };

    const handlePointerUp = () => {
      document.body.classList.remove(styles.resizingSidebar);
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };

    document.body.classList.add(styles.resizingSidebar);
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
  }, [sidebarWidth]);

  const handleMeetingCreated = async ({ meetingId, dateKey, message }) => {
    const [year, month, day] = dateKey.split('-').map(Number);
    setSelectedDate(new Date(year, month - 1, day));
    setSelectedMeetingId(meetingId);
    writeParams({ date: dateKey, meeting: meetingId });
    setIsAddMeetingOpen(false);
    setToastMessage(message || 'Meeting added.');
    await loadMeetings();
    window.setTimeout(() => setToastMessage(''), 3600);
  };

  const handleDeleteMeeting = useCallback(async (meeting) => {
    if (!window.confirm(`Delete the meeting with ${meeting.doctor}?`)) return;

    setDeletingMeetingId(meeting.id);
    try {
      const response = await fetchJson(`/meetings/${meeting.id}`, { method: 'DELETE' });
      const deletingSelectedMeeting = selectedMeetingId === meeting.id;
      if (deletingSelectedMeeting) {
        setSelectedMeetingId(null);
        writeParams({ meeting: null });
      }

      const nextMeetings = await loadMeetings();

      if (deletingSelectedMeeting) {
        const replacement = nextMeetings.find((item) => item.date === meeting.date && item.id !== meeting.id);
        setSelectedMeetingId(replacement?.id || null);
        writeParams({ meeting: replacement?.id || null });
      }

      setToastMessage(response.message || 'Meeting deleted.');
      window.setTimeout(() => setToastMessage(''), 3600);
    } catch (error) {
      setToastMessage(error.message || 'Could not delete meeting.');
      window.setTimeout(() => setToastMessage(''), 3600);
    } finally {
      setDeletingMeetingId(null);
    }
  }, [loadMeetings, selectedMeetingId]);

  return (
    <div className={styles.appContainer} style={{ '--sidebar-width': `${sidebarWidth}px` }}>
      <Topbar 
        isCalendarOpen={isCalendarOpen}
        onToggleCalendar={() => setIsCalendarOpen(!isCalendarOpen)}
        selectedDate={selectedDate}
      />
      <div className={styles.mainLayout}>
        <Sidebar 
          meetings={filteredMeetings} 
          selectedMeetingId={selectedMeetingId}
          onSelectMeeting={handleSelectMeeting}
          isOpen={isSidebarOpenOnMobile}
          onClose={() => setIsSidebarOpenOnMobile(false)}
          selectedDate={selectedDate}
          isLoading={isLoadingMeetings}
          error={meetingsError}
          width={sidebarWidth}
          onResizeStart={handleSidebarResizeStart}
          onAddMeeting={() => setIsAddMeetingOpen(true)}
          onDeleteMeeting={handleDeleteMeeting}
          deletingMeetingId={deletingMeetingId}
        />
        <RightPanel 
          selectedMeeting={selectedMeeting} 
          meetingsCount={filteredMeetings.length}
          selectedDate={selectedDate}
          onAddMeeting={() => setIsAddMeetingOpen(true)}
          onRefreshMeetings={() => loadMeetings()}
        />
        {isCalendarOpen && (
          <CalendarDrawer
            isOpen={isCalendarOpen}
            onClose={() => setIsCalendarOpen(false)}
            selectedDate={selectedDate}
            onSelectDate={handleSelectDate}
            meetings={meetings}
          />
        )}
      </div>
      {isAddMeetingOpen && (
        <AddMeetingModal
          selectedDate={selectedDate}
          onClose={() => setIsAddMeetingOpen(false)}
          onCreated={handleMeetingCreated}
        />
      )}
      {toastMessage && <div className={styles.toast}>{toastMessage}</div>}
    </div>
  );
}

export default App;

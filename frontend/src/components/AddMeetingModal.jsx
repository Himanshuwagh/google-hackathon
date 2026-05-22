import { useEffect, useMemo, useState } from 'react';
import { fetchJson } from '../api';
import styles from './AddMeetingModal.module.css';

const REP_ID = 'rep_rakesh_sharma';
const DURATION_OPTIONS = [15, 20, 25, 30, 45, 60];

const formatDateKey = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const nextHalfHour = () => {
  const now = new Date();
  const next = new Date(now);
  const minutes = now.getMinutes();
  const roundedMinutes = minutes === 0 ? 30 : minutes <= 30 ? 30 : 60;
  next.setMinutes(roundedMinutes, 0, 0);
  if (roundedMinutes === 60) {
    next.setHours(next.getHours() + 1, 0, 0, 0);
  }
  return `${String(next.getHours()).padStart(2, '0')}:${String(next.getMinutes()).padStart(2, '0')}`;
};

const isSameDate = (left, right) =>
  left.getFullYear() === right.getFullYear() &&
  left.getMonth() === right.getMonth() &&
  left.getDate() === right.getDate();

const initialForm = (selectedDate) => ({
  hcpId: '',
  drugId: '',
  date: formatDateKey(selectedDate),
  time: isSameDate(selectedDate, new Date()) ? nextHalfHour() : '09:30',
  duration: '20',
  location: '',
});

function AddMeetingModal({ selectedDate, onClose, onCreated }) {
  const [options, setOptions] = useState({ hcps: [], drugs: [] });
  const [form, setForm] = useState(() => initialForm(selectedDate));
  const [touched, setTouched] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    fetchJson(`/meetings/options?${new URLSearchParams({ rep_id: REP_ID })}`, {
      signal: controller.signal,
    })
      .then((data) => setOptions({
        hcps: data.hcps || [],
        drugs: data.drugs || [],
      }))
      .catch((loadError) => {
        if (loadError.name !== 'AbortError') {
          setError(loadError.message || 'Could not load meeting options.');
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, []);

  const selectedHcp = useMemo(
    () => options.hcps.find((hcp) => hcp.id === form.hcpId),
    [form.hcpId, options.hcps]
  );

  const selectedDrug = useMemo(
    () => options.drugs.find((drug) => drug.id === form.drugId),
    [form.drugId, options.drugs]
  );

  const validation = {
    hcpId: form.hcpId ? '' : 'Select a doctor.',
    drugId: form.drugId ? '' : 'Select a drug.',
    date: form.date ? '' : 'Choose a date.',
    time: form.time ? '' : 'Choose a time.',
    duration: form.duration ? '' : 'Choose a duration.',
    location: form.location.trim() ? '' : 'Add a location.',
  };

  const isValid = Object.values(validation).every((message) => !message);

  const updateField = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleHcpChange = (event) => {
    const hcpId = event.target.value;
    const hcp = options.hcps.find((item) => item.id === hcpId);
    setForm((current) => ({
      ...current,
      hcpId,
      location: hcp?.hospital || current.location,
    }));
  };

  const markTouched = (field) => {
    setTouched((current) => ({ ...current, [field]: true }));
  };

  const fieldError = (field) => touched[field] ? validation[field] : '';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setTouched({
      hcpId: true,
      drugId: true,
      date: true,
      time: true,
      duration: true,
      location: true,
    });
    if (!isValid) return;

    setError('');
    setIsSubmitting(true);
    try {
      const meetingDate = new Date(`${form.date}T${form.time}:00`);
      const response = await fetchJson('/meetings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rep_id: REP_ID,
          hcp_id: form.hcpId,
          drug_id: form.drugId,
          meeting_date: meetingDate.toISOString(),
          location: form.location.trim(),
          duration_mins: Number(form.duration),
        }),
      });

      onCreated?.({
        meetingId: response.meeting_id,
        dateKey: form.date,
        message: response.message || 'Meeting added.',
      });
    } catch (submitError) {
      setError(submitError.message || 'Could not add meeting.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className={styles.overlay} onMouseDown={onClose}>
      <div className={styles.modal} onMouseDown={(event) => event.stopPropagation()}>
        <div className={styles.header}>
          <div>
            <div className={styles.eyebrow}>New meeting</div>
            <h2 className="serif">Schedule doctor visit</h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close add meeting form">×</button>
        </div>

        {error && <div className={styles.errorBanner}>{error}</div>}

        {isLoading ? (
          <div className={styles.loadingState}>Loading doctors and drugs...</div>
        ) : (
          <form className={styles.form} onSubmit={handleSubmit}>
            <label className={styles.field}>
              <span>Doctor</span>
              <select
                value={form.hcpId}
                onChange={handleHcpChange}
                onBlur={() => markTouched('hcpId')}
                disabled={isSubmitting}
              >
                <option value="">Select doctor</option>
                {options.hcps.map((hcp) => (
                  <option key={hcp.id} value={hcp.id}>
                    {hcp.name} · {hcp.specialty} · {hcp.hospital}
                  </option>
                ))}
              </select>
              {fieldError('hcpId') && <em>{fieldError('hcpId')}</em>}
            </label>

            {selectedHcp && (
              <div className={styles.contextCard}>
                <strong>{selectedHcp.name}</strong>
                <span>{[selectedHcp.specialty, selectedHcp.hospital, selectedHcp.city].filter(Boolean).join(' · ')}</span>
              </div>
            )}

            <label className={styles.field}>
              <span>Drug</span>
              <select
                value={form.drugId}
                onChange={(event) => updateField('drugId', event.target.value)}
                onBlur={() => markTouched('drugId')}
                disabled={isSubmitting}
              >
                <option value="">Select drug</option>
                {options.drugs.map((drug) => (
                  <option key={drug.id} value={drug.id}>
                    {drug.brand_name} · {drug.generic_name || drug.drug_class}
                  </option>
                ))}
              </select>
              {fieldError('drugId') && <em>{fieldError('drugId')}</em>}
            </label>

            {selectedDrug && (
              <div className={styles.contextCard}>
                <strong>{selectedDrug.brand_name}</strong>
                <span>{[selectedDrug.generic_name, selectedDrug.drug_class].filter(Boolean).join(' · ')}</span>
              </div>
            )}

            <div className={styles.inlineGrid}>
              <label className={styles.field}>
                <span>Date</span>
                <input
                  type="date"
                  value={form.date}
                  onChange={(event) => updateField('date', event.target.value)}
                  onBlur={() => markTouched('date')}
                  disabled={isSubmitting}
                />
                {fieldError('date') && <em>{fieldError('date')}</em>}
              </label>

              <label className={styles.field}>
                <span>Time</span>
                <input
                  type="time"
                  value={form.time}
                  onChange={(event) => updateField('time', event.target.value)}
                  onBlur={() => markTouched('time')}
                  disabled={isSubmitting}
                />
                {fieldError('time') && <em>{fieldError('time')}</em>}
              </label>
            </div>

            <label className={styles.field}>
              <span>Duration</span>
              <div className={styles.durationRow}>
                {DURATION_OPTIONS.map((duration) => (
                  <button
                    key={duration}
                    type="button"
                    className={`${styles.durationBtn} ${form.duration === String(duration) ? styles.durationActive : ''}`}
                    onClick={() => updateField('duration', String(duration))}
                    disabled={isSubmitting}
                  >
                    {duration}
                  </button>
                ))}
              </div>
              {fieldError('duration') && <em>{fieldError('duration')}</em>}
            </label>

            <label className={styles.field}>
              <span>Location</span>
              <input
                type="text"
                value={form.location}
                onChange={(event) => updateField('location', event.target.value)}
                onBlur={() => markTouched('location')}
                placeholder="Hospital, room, or meeting location"
                disabled={isSubmitting}
              />
              {fieldError('location') && <em>{fieldError('location')}</em>}
            </label>

            <div className={styles.footer}>
              <button type="button" className={styles.secondaryBtn} onClick={onClose} disabled={isSubmitting}>
                Cancel
              </button>
              <button type="submit" className={styles.primaryBtn} disabled={!isValid || isSubmitting}>
                {isSubmitting ? 'Saving...' : 'Add meeting'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

export default AddMeetingModal;

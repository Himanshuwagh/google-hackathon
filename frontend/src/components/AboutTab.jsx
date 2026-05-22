import { useEffect, useState } from 'react';
import { fetchJson } from '../api';
import styles from './AboutTab.module.css';

const asArray = (value) => Array.isArray(value) ? value : [];

const formatDate = (value) => {
  if (!value) return 'Not recorded';
  return new Date(value).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
};

function AboutTab({ meeting }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadHcp = async () => {
      try {
        setLoading(true);
        // We fetch the meeting which contains the latest hcp from MongoDB
        const data = await fetchJson(`/meeting/${meeting.id}`);
        setDetail(data);
        setError(null);
      } catch (err) {
        setError(err.message || 'Failed to load doctor details');
      } finally {
        setLoading(false);
      }
    };
    loadHcp();
  }, [meeting.id]);

  if (loading) {
    return <div className={styles.container}><div className={styles.message}>Loading doctor details...</div></div>;
  }

  if (error) {
    return <div className={styles.container}><div className={styles.message}>{error}</div></div>;
  }

  const hcp = detail?.hcp;
  const drug = detail?.drug || {};
  const focusAreas = asArray(hcp?.prescribing_focus);
  const concerns = asArray(hcp?.known_objections);
  const therapyName = drug.brand_name || drug.name || drug.generic_name || meeting.drug || 'Not assigned';
  const therapyClass = drug.drug_class || 'Not recorded';

  if (!hcp) {
    return <div className={styles.container}><div className={styles.message}>No doctor details available.</div></div>;
  }

  return (
    <div className={styles.container}>
      <section className={styles.profileHeader}>
        <div className={styles.signalGrid}>
          <div className={styles.signal}>
            <span>Relationship</span>
            <strong>{hcp.relationship_score !== undefined ? `${hcp.relationship_score}/10` : 'N/A'}</strong>
          </div>
          <div className={styles.signal}>
            <span>Last visit</span>
            <strong>{formatDate(hcp.last_visited)}</strong>
          </div>
          <div className={styles.signal}>
            <span>Language</span>
            <strong>{hcp.preferred_language || 'Not recorded'}</strong>
          </div>
        </div>
      </section>

      <div className={styles.layout}>
        <section className={styles.contextSection}>
          <div className={styles.sectionHeading}>
            <div className={styles.eyebrow}>Doctor Context</div>
            <h3>What matters for this conversation</h3>
          </div>

          <div className={styles.contextGroups}>
            <div className={styles.contextGroup}>
              <div className={styles.groupLabel}>Prescribing focus</div>
              <div className={styles.chipRow}>
                {focusAreas.length > 0
                  ? focusAreas.map((focus) => <span key={focus} className={styles.focusChip}>{focus}</span>)
                  : <span className={styles.emptyValue}>No focus areas recorded</span>}
              </div>
            </div>

            <div className={styles.contextGroup}>
              <div className={styles.groupLabel}>Known concerns</div>
              <div className={styles.concernList}>
                {concerns.length > 0
                  ? concerns.map((concern) => <div key={concern} className={styles.concernItem}>{concern}</div>)
                  : <span className={styles.emptyValue}>No concerns recorded</span>}
              </div>
            </div>
          </div>
        </section>

        <aside className={styles.visitSection}>
          <div className={styles.sectionHeading}>
            <div className={styles.eyebrow}>Meeting Context</div>
            <h3>Therapy snapshot</h3>
          </div>

          <dl className={styles.visitFacts}>
            <div>
              <dt>Therapy</dt>
              <dd>{therapyName}</dd>
            </div>
            <div>
              <dt>Drug class</dt>
              <dd>{therapyClass}</dd>
            </div>
          </dl>
        </aside>
      </div>

      <section className={styles.prepStrip}>
        <div className={styles.prepCell}>
          <span>Engagement</span>
          <strong>{hcp.relationship_score !== undefined && hcp.relationship_score >= 8 ? 'Strong' : 'Build trust'}</strong>
        </div>
        <div className={styles.prepCell}>
          <span>Discussion focus</span>
          <strong>{focusAreas[0] || hcp.specialty || 'Doctor needs'}</strong>
        </div>
        <div className={styles.prepCell}>
          <span>Objection to prepare</span>
          <strong>{concerns[0] || 'Review after visit'}</strong>
        </div>
      </section>
    </div>
  );
}

export default AboutTab;

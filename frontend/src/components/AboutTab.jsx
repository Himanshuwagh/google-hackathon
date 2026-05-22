import { useEffect, useState } from 'react';
import { fetchJson } from '../api';
import styles from './AboutTab.module.css';

function AboutTab({ meeting }) {
  const [hcp, setHcp] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadHcp = async () => {
      try {
        setLoading(true);
        // We fetch the meeting which contains the latest hcp from MongoDB
        const data = await fetchJson(`/meeting/${meeting.id}`);
        setHcp(data.hcp);
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

  if (!hcp) {
    return <div className={styles.container}><div className={styles.message}>No doctor details available.</div></div>;
  }

  const renderArray = (arr) => {
    if (!arr || arr.length === 0) return 'None';
    return (
      <ul className={styles.list}>
        {arr.map((item, i) => <li key={i}>{item}</li>)}
      </ul>
    );
  };

  return (
    <div className={styles.container}>
      <h2 className={`serif ${styles.title}`}>{hcp.name}</h2>
      
      <div className={styles.grid}>
        <div className={styles.card}>
          <div className={styles.label}>Specialty</div>
          <div className={styles.value}>{hcp.specialty || 'N/A'}</div>
        </div>
        
        <div className={styles.card}>
          <div className={styles.label}>Hospital</div>
          <div className={styles.value}>{hcp.hospital || 'N/A'}</div>
        </div>
        
        <div className={styles.card}>
          <div className={styles.label}>City</div>
          <div className={styles.value}>{hcp.city || 'N/A'}</div>
        </div>
        
        <div className={styles.card}>
          <div className={styles.label}>Relationship Score</div>
          <div className={styles.value}>{hcp.relationship_score !== undefined ? `${hcp.relationship_score}/10` : 'N/A'}</div>
        </div>
        
        <div className={styles.card}>
          <div className={styles.label}>Last Visited</div>
          <div className={styles.value}>{hcp.last_visited ? new Date(hcp.last_visited).toLocaleDateString('en-GB') : 'N/A'}</div>
        </div>
        
        <div className={styles.card}>
          <div className={styles.label}>Preferred Language</div>
          <div className={styles.value}>{hcp.preferred_language || 'N/A'}</div>
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Prescribing Focus</div>
        <div className={styles.sectionContent}>
          {renderArray(hcp.prescribing_focus)}
        </div>
      </div>

      <div className={styles.section}>
        <div className={styles.sectionTitle}>Known Objections & Concerns</div>
        <div className={styles.sectionContent}>
          {renderArray(hcp.known_objections)}
        </div>
      </div>
    </div>
  );
}

export default AboutTab;

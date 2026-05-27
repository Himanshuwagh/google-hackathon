import { useMemo, useState } from 'react';
import { fetchJson } from '../api';
import styles from './AskTab.module.css';

function AskTab({ meeting }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);

  const suggestions = useMemo(() => [
    `What evidence is available for ${meeting.drug || 'this drug'}?`,
    'How should I handle the known objections?',
    'What follow-up should I prioritize after this meeting?'
  ], [meeting.drug]);

  const handleAsk = async (question) => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion) return;

    setMessages(prev => [...prev, { type: 'q', text: trimmedQuestion }]);
    setInputValue('');
    setShowSuggestions(false);
    setIsAsking(true);

    try {
      const response = await fetchJson('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          meeting_id: meeting.id,
          question: trimmedQuestion,
        }),
      });

      setMessages(prev => [...prev, {
        type: 'a',
        text: response.answer,
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        type: 'a',
        text: error.message || 'Could not answer this question right now.',
        isError: true,
      }]);
    } finally {
      setIsAsking(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    handleAsk(inputValue);
  };

  return (
    <div className={styles.askContainer}>
      <div className={styles.contextBar}>
        Asking about: {meeting.doctor} · {meeting.drug} · {meeting.date} {meeting.time}
      </div>
      
      <div className={styles.chatArea}>
        {messages.map((msg, idx) => (
          <div key={idx} className={styles.messagePair}>
            {msg.type === 'q' && (
              <div className={styles.questionBlock}>
                <div className={styles.qLabel}>You asked:</div>
                <div className={styles.qText}>{msg.text}</div>
                <hr className={styles.separator} />
              </div>
            )}
            {msg.type === 'a' && (
              <div className={styles.answerBlock}>
                <div className={`${styles.aText} ${msg.isError ? styles.errorText : ''}`}>{msg.text}</div>
              </div>
            )}
          </div>
        ))}
        
        {showSuggestions && messages.length === 0 && (
          <div className={styles.suggestionsContainer}>
            {suggestions.map((suggestion) => (
              <button 
                key={suggestion} 
                className={styles.suggestionPill}
                onClick={() => handleAsk(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className={styles.inputArea}>
        <form onSubmit={onSubmit} className={styles.inputForm}>
          <input 
            type="text" 
            className={styles.input} 
            placeholder="Ask anything about this meeting..." 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isAsking}
          />
          <button 
            type="submit" 
            className={styles.submitBtn}
            disabled={isAsking || !inputValue.trim()}
          >
            {isAsking ? 'Thinking...' : 'Ask'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default AskTab;

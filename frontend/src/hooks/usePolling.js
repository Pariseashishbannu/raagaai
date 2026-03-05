import { useState, useEffect, useRef } from 'react';
import { getJobStatus } from '../api/client';

export function useJobPolling(jobId) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    if (!jobId) return;

    const poll = async () => {
      try {
        const res = await getJobStatus(jobId);
        setStatus(res.data);
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          clearInterval(intervalRef.current);
        }
      } catch (err) {
        setError(err.message);
        clearInterval(intervalRef.current);
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 2000);

    return () => clearInterval(intervalRef.current);
  }, [jobId]);

  return { status, error };
}

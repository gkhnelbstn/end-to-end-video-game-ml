import { useCallback, useEffect, useState } from "react";

export interface Async<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
  /** Run the loader again (e.g. a Retry button after an error). */
  reload: () => void;
}

/** Run an async loader whenever `deps` change; ignores results from stale runs. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Async<T> {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<Omit<Async<T>, "reload">>({
    data: undefined,
    error: undefined,
    loading: true,
  });
  useEffect(() => {
    let current = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    load().then(
      (data) => current && setState({ data, error: undefined, loading: false }),
      (error) => current && setState({ data: undefined, error, loading: false }),
    );
    return () => {
      current = false;
    };
  }, [...deps, attempt]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { ...state, reload };
}

/** A value that only updates after `delay` ms without changes (for search boxes). */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

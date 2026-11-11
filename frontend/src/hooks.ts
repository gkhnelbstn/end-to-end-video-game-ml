import { useEffect, useState } from "react";

export interface Async<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/** Run an async loader whenever `deps` change; ignores results from stale runs. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T>>({ data: undefined, error: undefined, loading: true });
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
  }, deps);
  return state;
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

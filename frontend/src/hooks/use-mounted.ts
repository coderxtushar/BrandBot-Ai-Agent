import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/** True in the browser after hydration, false during the server render. */
export function useMounted() {
  return useSyncExternalStore(subscribe, () => true, () => false);
}

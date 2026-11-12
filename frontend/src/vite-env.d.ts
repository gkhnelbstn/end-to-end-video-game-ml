/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Rauthy's issuer, when the app is not served next to it (e.g. `npm run dev`). */
  readonly VITE_OIDC_AUTHORITY?: string;
}

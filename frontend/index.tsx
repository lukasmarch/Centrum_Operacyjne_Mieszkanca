import './src/index.css';

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { captureAcquisition } from './src/services/analytics';

// Źródło wizyty zapamiętujemy PRZED zamontowaniem aplikacji. `App` przepisuje
// adres w pasku przy pierwszej nawigacji i gubi wtedy `?utm_...` — po tym
// momencie nie ma już skąd wziąć informacji, który post przyprowadził człowieka.
captureAcquisition();

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error("Could not find root element to mount to");
}

const root = ReactDOM.createRoot(rootElement);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

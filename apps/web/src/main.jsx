import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { HelmStoreProvider } from './context/HelmStore';
import '../styles.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HelmStoreProvider>
      <App />
    </HelmStoreProvider>
  </React.StrictMode>
);

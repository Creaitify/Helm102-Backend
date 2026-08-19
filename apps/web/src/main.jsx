import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { HelmProvider } from './store';
import { HelmStoreProvider } from './context/HelmStore';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <HelmStoreProvider>
      <HelmProvider>
        <App />
      </HelmProvider>
    </HelmStoreProvider>
  </React.StrictMode>,
);


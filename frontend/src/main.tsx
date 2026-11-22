import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import { DostawcaSesji } from './sesja';
import App from './App';
import './styles.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <HashRouter>
      <DostawcaSesji>
        <App />
      </DostawcaSesji>
    </HashRouter>
  </StrictMode>,
);

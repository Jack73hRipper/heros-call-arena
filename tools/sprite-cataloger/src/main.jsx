import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { AtlasProvider } from './context/AtlasContext';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AtlasProvider>
      <App />
    </AtlasProvider>
  </React.StrictMode>
);

import { useState } from 'react';
import LandingPage from './components/LandingPage';
import ScannerDashboard from './components/ScannerDashboard';

export default function App() {
  const [view, setView] = useState('landing'); // 'landing' | 'scanner'

  return (
    <>
      {view === 'landing' && <LandingPage onLaunch={() => setView('scanner')} />}
      {view === 'scanner' && <ScannerDashboard onBack={() => setView('landing')} />}
    </>
  );
}

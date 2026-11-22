import { useEffect, useState } from 'react';
import { useSessionState } from './app/app';
import {
  AnalyticsScreen, CheckInStub, ExploreScreen, FavesScreen, HomeScreen, LoadingScreen, LoginStub, MoreStub, ProfileScreen, TraveledScreen,
} from './screens/screens';

function useHash(): string {
  const [h, setH] = useState(window.location.hash);
  useEffect(() => {
    const on = () => setH(window.location.hash);
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return h.replace(/^#\/?/, '').split('?')[0];
}

export default function App() {
  const loggedIn = useSessionState();
  const route = useHash();
  const [signedInOnce, setSignedInOnce] = useState(false);
  if (!loggedIn) return <LoginStub onDone={() => { setSignedInOnce(true); window.location.hash = '#/loading'; }} />;
  if (!signedInOnce && route === '') return <LoadingScreen />;
  switch (route) {
    case 'home': return <HomeScreen />;
    case 'traveled': return <TraveledScreen />;
    case 'explore': return <ExploreScreen />;
    case 'faves': return <FavesScreen />;
    case 'profile': return <ProfileScreen />;
    case 'analytics': return <AnalyticsScreen />;
    case 'checkin': return <CheckInStub />;
    case 'more': return <MoreStub />;
    default: return <LoadingScreen />;
  }
}

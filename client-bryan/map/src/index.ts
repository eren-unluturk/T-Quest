// @tquest/map: the GIS maps for the T-Quest web app (see ../README.md for how to mount them).
import 'maplibre-gl/dist/maplibre-gl.css';
import './map.css';

export { HomeMap } from './HomeMap';
export type { HomeMapProps, MapPin } from './HomeMap';
export { TraveledMap, summarize } from './TraveledMap';
export type { RiddenSegment, TraveledSummary, UnlockedSpot } from './TraveledMap';
export type { RideReward, VerifiedRide } from './Ride';
export type { MapServices } from './data';
export type { Station } from './verify';
export { buildNetwork, routeName, tRoute } from './network';
export { matchTrip, tripsFromSchedules, verifyRide, MAX_TRAIN_KMH, ZONE_M } from './verify';
export { P, LINE_COLOR, lineOf } from './theme';
export { MapSlot, HOME_MAP_CARD, TRAVELED_MAP } from './MapSlot';
export type { SlotTarget } from './MapSlot';

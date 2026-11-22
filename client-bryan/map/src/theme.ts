// Isabella's canvas palette (design/tokens/colors.json) and the MBTA line colors.

export const P = {
  navy: '#1D3557', cream: '#FFF8EC', red: '#E63946', redDark: '#C1272D', yellow: '#FFC93C', pink: '#F4A6C6', lblue: '#A8DADC',
  steel: '#457B9D', lgreen: '#B8E0A8', land: '#F3EBDD', park: '#A8D5A2', water: '#A8DADC',
};

export type Line = 'Red' | 'Orange' | 'Blue' | 'Green';
export const SUBWAY = ['Red', 'Mattapan', 'Orange', 'Blue', 'Green-B', 'Green-C', 'Green-D', 'Green-E'];
export const LINES: Line[] = ['Green', 'Red', 'Blue', 'Orange'];
export const LINE_COLOR: Record<Line, string> = { Red: '#DA291C', Orange: '#ED8B00', Blue: '#003DA5', Green: '#00843D' };

/** MBTA route id to the line it belongs to (the Mattapan Trolley counts as Red, like the MBTA map). */
export const lineOf = (routeId: string): Line =>
  (routeId.startsWith('Green') ? 'Green' : routeId === 'Mattapan' ? 'Red' : routeId) as Line;
export const routesOf = (line: Line) => SUBWAY.filter((r) => lineOf(r) === line);

export const ICON_COLOR: Record<string, string> = { trail: P.red, landmark: P.yellow, skyline: P.lblue };
export const PIN_COLOR: Record<string, string> = { station: P.red, trail: P.pink, landmark: P.lblue, skyline: P.lgreen };
export const STAR = 'M12 2.8l2.8 5.8 6.3.9-4.6 4.4 1.1 6.3L12 17.2l-5.6 3 1.1-6.3L2.9 9.5l6.3-.9z';

/** OpenFreeMap (OpenStreetMap) vector basemap, recolored by paintCanvas. */
export const BASEMAP = 'https://tiles.openfreemap.org/styles/positron';
export const FONT = ['Noto Sans Bold'];

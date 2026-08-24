/** Ein kleines Design-System, damit die Screens gleich aussehen. */

export const colors = {
  bg: '#F4F6F5',
  surface: '#FFFFFF',
  border: '#E3E7E5',

  text: '#14201A',
  textMuted: '#63736B',
  textFaint: '#95A29B',

  // Rasengruen als Akzent, dazu ein dunkles Vereinsgruen fuer Flaechen.
  accent: '#1B8A4B',
  accentSoft: '#E6F4EC',
  dark: '#123024',

  win: '#1B8A4B',
  draw: '#B08400',
  loss: '#C0392B',

  yellowCard: '#E9B824',
  redCard: '#C0392B',
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
} as const;

export const radius = { sm: 8, md: 12, lg: 16 } as const;

export const resultColor = (result: string): string =>
  result === 'W' ? colors.win : result === 'L' ? colors.loss : colors.draw;

/** "2026-08-28" -> "Fr 28.08." */
export function formatDate(iso: string | null, withYear = false): string {
  if (!iso) return '';
  const [y, m, d] = iso.split('-');
  const weekdays = ['So', 'Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa'];
  const wd = weekdays[new Date(`${iso}T12:00:00`).getDay()] ?? '';
  return `${wd} ${d}.${m}.${withYear ? y : ''}`.trim();
}

/** Tage bis zum Spiel, fuer "heute" / "morgen" / "in 3 Tagen". */
export function relativeDay(iso: string | null): string {
  if (!iso) return '';
  const today = new Date();
  today.setHours(12, 0, 0, 0);
  const target = new Date(`${iso}T12:00:00`);
  const days = Math.round((target.getTime() - today.getTime()) / 86_400_000);
  if (days === 0) return 'heute';
  if (days === 1) return 'morgen';
  if (days === -1) return 'gestern';
  if (days > 1 && days < 8) return `in ${days} Tagen`;
  if (days < -1 && days > -8) return `vor ${Math.abs(days)} Tagen`;
  return '';
}

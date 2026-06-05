export type ProjectCardTheme = {
  gradient: string;
  iconColor: string;
};

const WARM_GRADIENTS: ProjectCardTheme[] = [
  {
    gradient: "from-amber-100 via-orange-50 to-yellow-100 dark:from-amber-950/40 dark:via-stone-900 dark:to-orange-950/30",
    iconColor: "text-amber-600/30 dark:text-amber-400/25",
  },
  {
    gradient: "from-orange-100 via-rose-50 to-amber-50 dark:from-orange-950/40 dark:via-stone-900 dark:to-rose-950/20",
    iconColor: "text-orange-600/30 dark:text-orange-400/25",
  },
  {
    gradient: "from-yellow-100 via-amber-50 to-stone-100 dark:from-yellow-950/30 dark:via-stone-900 dark:to-amber-950/30",
    iconColor: "text-yellow-700/30 dark:text-yellow-500/25",
  },
  {
    gradient: "from-stone-100 via-orange-50 to-amber-100 dark:from-stone-800/50 dark:via-stone-900 dark:to-orange-950/25",
    iconColor: "text-stone-600/35 dark:text-stone-400/25",
  },
  {
    gradient: "from-rose-100 via-orange-100 to-yellow-50 dark:from-rose-950/25 dark:via-stone-900 dark:to-orange-950/30",
    iconColor: "text-rose-600/30 dark:text-rose-400/25",
  },
  {
    gradient: "from-amber-50 via-yellow-100 to-orange-100 dark:from-amber-950/35 dark:via-stone-900 dark:to-yellow-950/25",
    iconColor: "text-amber-700/30 dark:text-amber-500/25",
  },
];

function hashString(value: string): number {
  let hash = 0;
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export function getProjectCardTheme(name: string): ProjectCardTheme {
  const index = hashString(name) % WARM_GRADIENTS.length;
  return WARM_GRADIENTS[index]!;
}

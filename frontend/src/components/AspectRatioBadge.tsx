/** Aspect ratio badge with colour coding. */
interface AspectRatioBadgeProps {
  ratio: string | null
}

const COLOURS: Record<string, string> = {
  vertical: 'bg-green-100 text-green-700',
  square: 'bg-blue-100 text-blue-700',
  horizontal: 'bg-orange-100 text-orange-700',
  unknown: 'bg-gray-100 text-gray-500',
}

export function AspectRatioBadge({ ratio }: AspectRatioBadgeProps) {
  const key = ratio ?? 'unknown'
  const colour = COLOURS[key] ?? COLOURS.unknown
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${colour}`}>
      {key}
    </span>
  )
}


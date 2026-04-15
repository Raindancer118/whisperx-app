// Volantic logo — navy wordmark with accent dot
export default function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const scale = size === 'sm' ? 'text-xl' : size === 'lg' ? 'text-4xl' : 'text-2xl'
  return (
    <div className={`font-display font-bold tracking-wide ${scale} flex items-center gap-0.5`}>
      <span className="text-navy">VOLANTIC</span>
      <span className="text-accent w-1.5 h-1.5 rounded-full bg-accent inline-block mb-0.5" />
    </div>
  )
}

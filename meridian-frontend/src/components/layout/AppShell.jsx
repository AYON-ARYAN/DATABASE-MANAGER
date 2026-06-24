import Navbar from './Navbar'

export default function AppShell({ children, wide }) {
  return (
    <div className="relative min-h-screen">
      {/* Animated ambient background */}
      <div className="aurora-bg" aria-hidden="true" />
      <Navbar />
      <main className={`relative z-10 pt-14 ${wide ? 'max-w-[1600px]' : 'max-w-6xl'} mx-auto px-4 py-8 animate-fade-up`}>
        {children}
      </main>
    </div>
  )
}

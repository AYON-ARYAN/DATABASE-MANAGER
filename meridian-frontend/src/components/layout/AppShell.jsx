import Navbar from './Navbar'

export default function AppShell({ children, wide }) {
  return (
    <div className="min-h-screen bg-zinc-950">
      <Navbar />
      <main className={`pt-14 ${wide ? 'max-w-[1600px]' : 'max-w-5xl'} mx-auto px-4 py-6`}>
        {children}
      </main>
    </div>
  )
}

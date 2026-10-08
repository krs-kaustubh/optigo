import Hero from "@/components/landing/Hero";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <>
      <Hero />
      <section className="border-y border-[var(--line)] bg-[var(--surface-2)] overflow-hidden">
         <div className="container mx-auto px-4 py-6 flex flex-wrap items-center gap-4 text-sm font-medium">
            <span className="text-[var(--ink-muted)] whitespace-nowrap">Try a route:</span>
            <div className="flex gap-2 overflow-x-auto pb-1 no-scrollbar">
              <Link href="/plan?from=11&to=1" className="bg-[var(--surface)] border border-[var(--line)] px-4 py-2 rounded-full hover:border-[var(--green)] hover:text-[var(--green)] transition-colors whitespace-nowrap shadow-sm hover:shadow-md">Panvel → Vashi</Link>
              <Link href="/plan?from=6&to=23" className="bg-[var(--surface)] border border-[var(--line)] px-4 py-2 rounded-full hover:border-[var(--orange)] hover:text-[var(--orange)] transition-colors whitespace-nowrap shadow-sm hover:shadow-md">Belapur CBD → Pendhar</Link>
              <Link href="/plan?from=6&to=14" className="bg-[var(--surface)] border border-[var(--line)] px-4 py-2 rounded-full hover:border-[var(--green)] hover:text-[var(--green)] transition-colors whitespace-nowrap shadow-sm hover:shadow-md">Belapur CBD → Kharkopar</Link>
            </div>
         </div>
      </section>
      
      <section id="how-it-works" className="py-24 bg-[var(--bg)]">
        <div className="container mx-auto px-4 text-center">
           <h2 className="font-serif text-3xl md:text-5xl font-bold mb-16 text-[var(--ink)]">How it works</h2>
           <div className="grid md:grid-cols-3 gap-8 max-w-4xl mx-auto">
              {[
                { title: "Pick stations", desc: "Select any two stations across the Navi Mumbai train and metro network." },
                { title: "Compare 3 smart routes", desc: "Instantly see the fastest, shortest, and cheapest options side-by-side." },
                { title: "Board with live times", desc: "Get real-time expected departures for the train you actually need." }
              ].map((step, i) => (
                <div key={i} className="bg-[var(--surface)] border border-[var(--line)] p-8 rounded-[24px] text-left shadow-sm">
                  <div className="w-12 h-12 bg-[var(--surface-2)] rounded-full flex items-center justify-center font-mono font-bold text-[var(--green)] text-lg mb-6">{i + 1}</div>
                  <h3 className="font-bold text-xl mb-2 text-[var(--ink)]">{step.title}</h3>
                  <p className="text-[var(--ink-muted)] leading-relaxed">{step.desc}</p>
                </div>
              ))}
           </div>
        </div>
      </section>

      <section className="py-24 bg-[var(--surface)] border-y border-[var(--line)] text-center relative overflow-hidden">
        <div className="absolute inset-0 opacity-5 pointer-events-none" style={{ backgroundImage: 'radial-gradient(circle at center, var(--green) 0, transparent 70%)' }}></div>
        <div className="container mx-auto px-4 relative z-10">
           <h2 className="font-serif text-4xl md:text-5xl font-bold mb-8 tracking-tight text-[var(--ink)]">Where to today?</h2>
           <Link href="/plan" className="inline-flex h-[52px] px-8 text-lg items-center justify-center rounded-full font-medium text-white bg-[var(--green)] hover:bg-[var(--green)]/90 shadow-lg hover:shadow-xl transition-all active:scale-95">
              Plan a route
           </Link>
        </div>
      </section>

      <footer className="py-8 bg-[var(--bg)] text-center text-sm text-[var(--ink-muted)]">
        <p>Built at KJSIT as a PBL mini project.</p>
      </footer>
    </>
  )
}

"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Chip } from "@/components/ui/chip";

export default function Hero() {
  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  };

  const item = {
    hidden: { opacity: 0, y: 12 },
    show: { opacity: 1, y: 0, transition: { type: "spring", stiffness: 300, damping: 24 } as any },
  };

  return (
    <section className="relative overflow-hidden pt-16 pb-16 md:pt-32 md:pb-40">
      <div className="container mx-auto px-4 grid md:grid-cols-2 gap-12 items-center">
        <motion.div variants={container} initial="hidden" animate="show" className="max-w-xl">
          <motion.div variants={item}>
            <Chip variant="outline" className="mb-6">Navi Mumbai · Train + Metro + Walk</Chip>
          </motion.div>
          <motion.h1 variants={item} className="font-serif text-5xl md:text-7xl font-bold leading-[1.05] tracking-tight text-[var(--ink)] mb-6 text-balance">
            One app. Every route.{" "}
            <span className="relative inline-block text-[var(--green)] mt-2">
              Optimized for you.
              <motion.svg
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={{ duration: 0.8, delay: 0.8, ease: "easeOut" }}
                className="absolute -bottom-1 left-0 w-full h-3 text-[var(--orange)]"
                viewBox="0 0 200 20"
                preserveAspectRatio="none"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path d="M2 15C50 5 150 5 198 15" stroke="currentColor" strokeWidth="6" strokeLinecap="round" />
              </motion.svg>
            </span>
          </motion.h1>
          <motion.p variants={item} className="text-lg md:text-xl text-[var(--ink-muted)] mb-10 text-balance leading-relaxed">
            Compare the fastest, shortest, and cheapest routes across the Harbour line, Uran branch, and Metro Line 1. With live train times, so you never miss a connection.
          </motion.p>
          <motion.div variants={item as any} className="flex flex-wrap items-center gap-4">
            <Link href="/plan" className="group inline-flex h-[52px] px-8 text-lg items-center justify-center rounded-full font-medium text-white bg-[var(--green)] hover:bg-[var(--green)]/90 transition-all shadow-md hover:shadow-lg active:scale-95">
              Plan a route
              <ArrowRight className="ml-2 w-5 h-5 text-[var(--orange)] group-hover:translate-x-1 transition-transform" />
            </Link>
            <a href="#how-it-works" className="inline-flex h-[52px] px-8 text-lg items-center justify-center rounded-full font-medium text-[var(--ink)] hover:bg-[var(--surface-2)] transition-all">
              See how it works
            </a>
          </motion.div>
        </motion.div>

        {/* Hero Visual */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="relative hidden md:block"
        >
          <svg viewBox="0 0 400 400" className="w-full h-auto drop-shadow-sm" fill="none" xmlns="http://www.w3.org/2000/svg">
            <motion.path
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              d="M50 300 C 100 300, 150 250, 150 200 L150 150 C 150 100, 200 100, 350 100"
              stroke="var(--green)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round"
            />
            <motion.path
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 1.5, ease: "easeInOut", delay: 0.5 }}
              d="M150 200 L150 250 C 150 300, 250 300, 250 300"
              stroke="var(--orange)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="8 8"
            />

            {[
              { cx: 50, cy: 300, label: "Panvel", align: "start" },
              { cx: 150, cy: 200, label: "Belapur", align: "end" },
              { cx: 350, cy: 100, label: "Vashi", align: "start" },
              { cx: 250, cy: 300, label: "Pendhar", align: "start" },
            ].map((pos, i) => (
              <g key={i}>
                <motion.circle
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 1 + i * 0.1, type: "spring" }}
                  cx={pos.cx} cy={pos.cy} r="6" fill="var(--surface)" stroke="var(--ink)" strokeWidth="3"
                />
                <motion.text
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 1.2 + i * 0.1 }}
                  x={pos.cx + (pos.align === "start" ? 12 : -12)}
                  y={pos.cy + 4}
                  textAnchor={pos.align as "start" | "middle" | "end" | "inherit"}
                  fill="var(--ink)"
                  className="font-medium text-xs font-sans"
                >
                  {pos.label}
                </motion.text>
              </g>
            ))}
          </svg>
        </motion.div>
      </div>
    </section>
  );
}

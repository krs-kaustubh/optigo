import { useState, useEffect } from "react";
import { Node } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ArrowDownUp, Search, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { Combobox } from "@/components/ui/combobox";

interface PlannerCardProps {
  nodes?: Node[];
  isLoading: boolean;
  initialFrom: number | null;
  initialTo: number | null;
  initialLive: boolean;
  onSearch: (from: number, to: number, live: boolean) => void;
}

export default function PlannerCard({ nodes, isLoading, initialFrom, initialTo, initialLive, onSearch }: PlannerCardProps) {
  const [from, setFrom] = useState<number | null>(initialFrom);
  const [to, setTo] = useState<number | null>(initialTo);
  const [live, setLive] = useState(initialLive);
  const [isSwapping, setIsSwapping] = useState(false);

  useEffect(() => {
    if (initialFrom) setFrom(initialFrom);
    if (initialTo) setTo(initialTo);
    setLive(initialLive);
  }, [initialFrom, initialTo, initialLive]);

  const handleSwap = () => {
    setIsSwapping(true);
    const temp = from;
    setFrom(to);
    setTo(temp);
    setTimeout(() => setIsSwapping(false), 300);
  };

  const handleSearch = () => {
    if (from && to && from !== to) {
      onSearch(from, to, live);
    }
  };

  return (
    <div className="flex flex-col gap-3.5">
      <div className="relative flex flex-col gap-1.5">
        <Combobox 
          label="From" 
          value={from} 
          onChange={setFrom} 
          nodes={nodes} 
          isLoading={isLoading} 
          icon={<div className="w-2.5 h-2.5 rounded-full border-2 border-[var(--green)] bg-[var(--surface)] shadow-xs" />}
        />
        
        {/* Integrated Flip Route Button */}
        <div className="relative flex items-center justify-end px-3 -my-2 z-20">
          <button 
            type="button"
            onClick={handleSwap}
            title="Swap origin and destination"
            aria-label="Swap origin and destination"
            className="group w-7 h-7 rounded-full bg-[var(--surface)] border border-[var(--line)] hover:border-[var(--green)] shadow-xs hover:shadow-sm flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--ink)] transition-all active:scale-90"
          >
            <motion.div animate={{ rotate: isSwapping ? 180 : 0 }} transition={{ duration: 0.25 }}>
              <ArrowDownUp className="w-3.5 h-3.5 group-hover:text-[var(--green)] transition-colors" />
            </motion.div>
          </button>
        </div>
        
        <Combobox 
          label="To" 
          value={to} 
          onChange={setTo} 
          nodes={nodes} 
          isLoading={isLoading} 
          icon={<div className="w-2.5 h-2.5 rounded-full bg-[var(--orange)] shadow-xs" />}
        />
      </div>

      <div className="flex items-center justify-between pt-0.5 px-0.5">
        <label className="flex items-center gap-2 text-sm font-medium text-[var(--ink)] cursor-pointer group select-none">
          <input 
            type="checkbox" 
            checked={live} 
            onChange={(e) => setLive(e.target.checked)}
            className="w-4 h-4 rounded border-[var(--line)] text-[var(--orange)] focus:ring-[var(--orange)] bg-[var(--surface)] accent-[var(--orange)]"
          />
          <Activity className={`w-4 h-4 transition-colors ${live ? 'text-[var(--orange)]' : 'text-[var(--ink-muted)]'}`} />
          <span>Live train board</span>
        </label>
      </div>

      <Button 
        className="w-full h-11 rounded-[14px] font-semibold" 
        onClick={handleSearch}
        disabled={!from || !to || from === to}
      >
        <Search className="w-4 h-4 mr-2" />
        {from === to && from !== null ? "Stations must be different" : "Find routes"}
      </Button>
    </div>
  );
}

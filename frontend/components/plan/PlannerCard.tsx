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
    <div className="bg-[var(--surface)] rounded-[24px] border border-[var(--line)] p-5 shadow-sm relative overflow-hidden">
      <div className="flex flex-col gap-4 relative z-10">
        <div className="flex flex-col gap-3 relative">
          <Combobox label="From" value={from} onChange={setFrom} nodes={nodes} isLoading={isLoading} />
          
          <button 
            onClick={handleSwap}
            className="absolute left-6 top-1/2 -translate-y-1/2 z-10 w-9 h-9 bg-[var(--surface)] border border-[var(--line)] rounded-full flex items-center justify-center text-[var(--ink-muted)] hover:text-[var(--ink)] hover:border-[var(--ink-muted)] transition-colors shadow-md"
          >
            <motion.div animate={{ rotate: isSwapping ? 180 : 0 }} transition={{ duration: 0.3 }}>
              <ArrowDownUp className="w-4 h-4" />
            </motion.div>
          </button>
          
          <Combobox label="To" value={to} onChange={setTo} nodes={nodes} isLoading={isLoading} />
        </div>

        <div className="flex items-center justify-between mt-1 pl-2">
          <label className="flex items-center gap-2 text-sm font-medium text-[var(--ink)] cursor-pointer group">
            <input 
              type="checkbox" 
              checked={live} 
              onChange={(e) => setLive(e.target.checked)}
              className="w-4 h-4 rounded border-[var(--line)] text-[var(--orange)] focus:ring-[var(--orange)] bg-[var(--surface)] accent-[var(--orange)]"
            />
            <Activity className={`w-4 h-4 transition-colors ${live ? 'text-[var(--orange)]' : 'text-[var(--ink-muted)]'}`} />
            Live train board
          </label>
        </div>

        <Button 
          className="w-full mt-2 h-12 rounded-[16px]" 
          onClick={handleSearch}
          disabled={!from || !to || from === to}
        >
          <Search className="w-4 h-4 mr-2" />
          {from === to && from !== null ? "Stations must be different" : "Find routes"}
        </Button>
      </div>
    </div>
  );
}

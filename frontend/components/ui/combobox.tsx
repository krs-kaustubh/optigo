"use client";
import { useState, useRef, useEffect } from "react";
import { Node } from "@/lib/types";
import { Chip } from "./chip";

export function Combobox({ label, value, onChange, nodes, isLoading, icon }: any) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedNode = nodes?.find((n: Node) => n.id === value);
  
  useEffect(() => {
    if (selectedNode && !isOpen) {
      setQuery(selectedNode.name);
    }
  }, [selectedNode, isOpen]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as globalThis.Node)) {
        setIsOpen(false);
        if (selectedNode) setQuery(selectedNode.name);
        else setQuery("");
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [selectedNode]);

  const filteredNodes = query === "" 
    ? nodes 
    : nodes?.filter((n: Node) => n.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="relative flex flex-col w-full" ref={containerRef}>
      <span className="text-[11px] font-bold text-[var(--ink-muted)] uppercase tracking-wider mb-1 pl-1">
        {label}
      </span>
      <div className="relative flex items-center">
        {icon && (
          <div className="absolute left-3.5 top-1/2 -translate-y-1/2 z-10 pointer-events-none flex items-center justify-center">
            {icon}
          </div>
        )}
        <input 
          type="text"
          value={isOpen ? query : (selectedNode ? selectedNode.name : "")}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          placeholder={isLoading ? "Loading..." : "Search station"}
          disabled={isLoading}
          className={`w-full bg-[var(--surface)] border border-[var(--line)] rounded-[14px] h-11 ${icon ? 'pl-9' : 'pl-4'} pr-20 text-[var(--ink)] font-medium outline-none focus:border-[var(--green)] focus:ring-1 focus:ring-[var(--green)] transition-all disabled:opacity-50 shadow-2xs text-sm`}
        />
        {!isOpen && selectedNode && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <Chip variant={selectedNode.type === 'metro' ? 'metro' : 'train'} className="text-[10px] px-2 py-0.5 uppercase tracking-wide">
              {selectedNode.type}
            </Chip>
          </div>
        )}
      </div>

      {isOpen && filteredNodes && filteredNodes.length > 0 && (
        <ul className="absolute z-50 w-full top-full mt-1.5 bg-[var(--surface)] border border-[var(--line)] rounded-[16px] shadow-xl max-h-60 overflow-auto py-1.5 outline outline-1 outline-[var(--line)]/50 divide-y divide-[var(--line)]/40">
          {filteredNodes.map((n: Node) => (
            <li 
              key={n.id}
              onClick={() => {
                onChange(n.id);
                setIsOpen(false);
                setQuery(n.name);
              }}
              className="px-3.5 py-2.5 hover:bg-[var(--surface-2)] cursor-pointer flex items-center justify-between transition-colors text-sm"
            >
              <span className="font-medium text-[var(--ink)]">{n.name}</span>
              <Chip variant={n.type === 'metro' ? 'metro' : 'train'} className="text-[10px] px-2 py-0.5 uppercase">
                {n.type}
              </Chip>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

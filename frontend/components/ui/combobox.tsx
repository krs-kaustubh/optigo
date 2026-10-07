"use client";
import { useState, useRef, useEffect } from "react";
import { Node } from "@/lib/types";
import { Chip } from "./chip";

export function Combobox({ label, value, onChange, nodes, isLoading }: any) {
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
    <div className="relative flex flex-col" ref={containerRef}>
      <span className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-1 pl-12">{label}</span>
      <div className="relative">
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
          className="w-full bg-[var(--surface-2)] border border-transparent rounded-[16px] h-12 pl-12 pr-16 text-[var(--ink)] font-medium outline-none focus:border-[var(--green)] focus:ring-1 focus:ring-[var(--green)] transition-colors disabled:opacity-50 shadow-inner"
        />
        {!isOpen && selectedNode && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <Chip variant={selectedNode.type === 'metro' ? 'metro' : 'train'} className="text-[10px] px-2 py-0.5">{selectedNode.type}</Chip>
          </div>
        )}
      </div>

      {isOpen && filteredNodes && filteredNodes.length > 0 && (
        <ul className="absolute z-50 w-full top-full mt-1 bg-[var(--surface)] border border-[var(--line)] rounded-[16px] shadow-lg max-h-60 overflow-auto py-2 outline outline-1 outline-[var(--line)]">
          {filteredNodes.map((n: Node) => (
            <li 
              key={n.id}
              onClick={() => {
                onChange(n.id);
                setIsOpen(false);
                setQuery(n.name);
              }}
              className="px-4 py-2 hover:bg-[var(--surface-2)] cursor-pointer flex items-center justify-between transition-colors"
            >
              <span className="font-medium text-[var(--ink)]">{n.name}</span>
              <Chip variant={n.type === 'metro' ? 'metro' : 'train'} className="text-[10px] px-2 py-0.5">{n.type}</Chip>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

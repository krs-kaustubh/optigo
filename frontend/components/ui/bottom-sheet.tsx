"use client";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect } from "react";
import { X } from "lucide-react";

export function BottomSheet({ isOpen, onClose, children, title }: { isOpen: boolean, onClose: () => void, children: React.ReactNode, title?: string }) {
  
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => { document.body.style.overflow = 'unset'; }
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-[var(--ink)]/40 z-50 lg:hidden backdrop-blur-sm"
          />
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 25, stiffness: 200 }}
            drag="y"
            dragConstraints={{ top: 0 }}
            dragElastic={0.2}
            onDragEnd={(e, { offset, velocity }) => {
              if (offset.y > 100 || velocity.y > 500) {
                onClose();
              }
            }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-[var(--bg)] rounded-t-[28px] shadow-[0_-10px_40px_rgba(0,0,0,0.1)] flex flex-col max-h-[92vh] lg:hidden"
          >
            <div className="flex justify-center p-4 cursor-grab active:cursor-grabbing pb-2">
              <div className="w-12 h-1.5 bg-[var(--line)] rounded-full" />
            </div>
            
            {title && (
              <div className="px-6 pb-4 pt-2 flex justify-between items-center border-b border-[var(--line)]">
                <h3 className="font-serif font-bold text-2xl text-[var(--ink)]">{title}</h3>
                <button onClick={onClose} className="p-2 -mr-2 bg-[var(--surface-2)] rounded-full text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors">
                  <X className="w-5 h-5" />
                </button>
              </div>
            )}
            
            <div className="overflow-y-auto p-6 flex-1">
              {children}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

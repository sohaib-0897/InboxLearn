import React, { useState } from 'react';
import { motion } from 'motion/react';
import { 
  Cpu, 
  Layers, 
  CheckSquare, 
  GitCompare, 
  History, 
  Menu, 
  X, 
  ShieldCheck, 
  Activity 
} from 'lucide-react';
import { StatusResponse } from '../api/client';

interface NavbarProps {
  activeTab: 'studio' | 'review' | 'candidate' | 'ledger' | 'pipeline';
  setActiveTab: (tab: 'studio' | 'review' | 'candidate' | 'ledger' | 'pipeline') => void;
  status: StatusResponse | null;
}

const NAV_ITEMS = [
  { id: 'studio', label: 'Inference Studio', icon: Layers },
  { id: 'review', label: 'Review Desk', icon: CheckSquare },
  { id: 'candidate', label: 'Candidate & Gate', icon: GitCompare },
  { id: 'ledger', label: 'Version Ledger', icon: History },
  { id: 'pipeline', label: 'Architecture', icon: Activity },
] as const;

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, status }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-white/10 bg-void/80 backdrop-blur-xl">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Model Status Pill */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setActiveTab('studio')}
              className="flex items-center gap-2.5 text-left group cursor-pointer"
            >
              <div className="w-8 h-8 rounded-lg bg-brand-indigo/20 border border-brand-indigo/40 flex items-center justify-center text-brand-indigo shadow-glow-indigo group-hover:scale-105 transition-transform">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <span className="font-mono font-bold tracking-tight text-white text-sm">
                  INBOXLEARN
                </span>
                <span className="text-[10px] font-mono text-zinc-500 block -mt-0.5">
                  AI INFERENCE ENGINE
                </span>
              </div>
            </button>

            {/* Active Model Version Badge */}
            {status && (
              <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-surface-elevated border border-white/10 text-xs font-mono">
                <span className="w-1.5 h-1.5 rounded-full bg-brand-emerald animate-pulse" />
                <span className="text-zinc-400">ACTIVE:</span>
                <span className="text-white font-semibold">{status.active_version.label.toUpperCase()}</span>
                <span className="text-[10px] text-zinc-500 capitalize">({status.active_version.kind})</span>
              </div>
            )}
          </div>

          {/* Desktop Navigation Tabs with Motion Pill */}
          <nav className="hidden md:flex items-center gap-1 p-1 rounded-xl bg-surface/70 border border-white/5">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`relative px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition-colors flex items-center gap-1.5 cursor-pointer ${
                    isActive ? 'text-white' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeNavPill"
                      className="absolute inset-0 rounded-lg bg-surface-highlight border border-white/10 shadow-sm"
                      transition={{ type: 'spring', stiffness: 450, damping: 35 }}
                    />
                  )}
                  <span className="relative z-10 flex items-center gap-1.5">
                    <Icon className="w-3.5 h-3.5" />
                    <span>{item.label}</span>
                  </span>
                </button>
              );
            })}
          </nav>

          {/* Quick Metrics & Badges */}
          <div className="hidden lg:flex items-center gap-4 text-xs font-mono">
            {status && (
              <div className="flex items-center gap-3 text-zinc-400 border-l border-white/10 pl-4">
                <span>
                  Emails: <strong className="text-white">{status.metrics.emails_stored}</strong>
                </span>
                <span>
                  Reviews: <strong className="text-brand-amber">{status.metrics.pending_reviews}</strong>
                </span>
                <span>
                  Feedback: <strong className="text-brand-cyan">{status.metrics.available_feedback}</strong>
                </span>
              </div>
            )}
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg bg-surface border border-white/10 text-zinc-400 hover:text-white"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden border-b border-white/10 bg-surface-elevated/95 backdrop-blur-2xl p-4 space-y-2">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setMobileMenuOpen(false);
                }}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-mono font-medium transition-colors ${
                  isActive
                    ? 'bg-brand-indigo/20 text-white border border-brand-indigo/40'
                    : 'text-zinc-400 hover:text-white bg-surface'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </header>
  );
};

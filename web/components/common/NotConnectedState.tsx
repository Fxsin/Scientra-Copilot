"use client";

import { useRouter } from "next/navigation";

interface Action { label: string; href: string; }

export function NotConnectedState({ title, description, actions }: { title: string; description: string; actions: Action[] }) {
  const router = useRouter();
  return (
    <div className="max-w-2xl mx-auto py-16 text-center">
      <div className="rounded-xl border border-slate-200/50 bg-white p-8 space-y-4">
        <h1 className="text-xl font-bold text-slate-700">{title}</h1>
        <p className="text-sm text-slate-400 leading-relaxed max-w-md mx-auto">{description}</p>
        <div className="flex items-center justify-center gap-3 pt-2">
          {actions.map((a) => (
            <button key={a.href} onClick={() => router.push(a.href)} className="text-sm px-4 py-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 hover:text-slate-800 transition-colors">{a.label}</button>
          ))}
        </div>
        <p className="text-[10px] text-slate-300 pt-2">This module is not yet connected to your literature database.</p>
      </div>
    </div>
  );
}

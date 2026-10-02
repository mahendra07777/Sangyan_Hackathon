import * as React from "react";
import { Header } from "./Header";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      <Header />
      <main className="flex-1 flex flex-col">
        {children}
      </main>
    </div>
  );
}

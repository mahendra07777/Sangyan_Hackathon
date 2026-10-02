import { BookOpen, Globe } from "lucide-react";
import { Button } from "../ui/Button";

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-neutral-200 bg-white/80 backdrop-blur">
      <div className="container mx-auto flex h-16 items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white">
            <BookOpen className="h-5 w-5" />
          </div>
          <span className="text-xl font-bold tracking-tight text-neutral-900">
            Bharat<span className="text-primary-600">Copilot</span>
          </span>
        </div>
        
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" className="hidden sm:flex gap-2">
            <Globe className="h-4 w-4" />
            English
          </Button>
        </div>
      </div>
    </header>
  );
}

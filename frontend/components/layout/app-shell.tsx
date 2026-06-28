import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

/** The persistent application chrome: fixed sidebar + sticky topbar + content. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="lg:pl-64">
        <Topbar />
        <main className="w-full px-4 py-6 lg:px-8 lg:py-8 2xl:px-10">{children}</main>
      </div>
    </div>
  );
}

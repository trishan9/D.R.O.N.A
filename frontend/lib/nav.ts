/**
 * Navigation model for the D.R.O.N.A. app shell.
 *
 * Grouped sidebar sections. Each item maps to an App Router route under the
 * `(app)` route group. Icons are lucide-react names resolved in the sidebar.
 */

import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Bot,
  Route,
  Network,
  Trophy,
  CircuitBoard,
  BarChart3,
  UserCircle,
  SlidersHorizontal,
  Info,
  Brain,
  Radio,
  FlaskConical,
  BookOpen,
  Boxes,
  Search,
  Mic,
} from "lucide-react";

export interface NavItem {
  title: string;
  href: string;
  icon: LucideIcon;
  description: string;
  badge?: string;
}

export interface NavSection {
  label: string;
  items: NavItem[];
}

export const NAV: NavSection[] = [
  {
    label: "Overview",
    items: [
      {
        title: "Dashboard",
        href: "/",
        icon: LayoutDashboard,
        description: "System status, your progress, and quick actions",
      },
    ],
  },
  {
    label: "Advising AI",
    items: [
      {
        title: "Advisor",
        href: "/advisor",
        icon: Bot,
        description: "Ask the bias-aware, locally-grounded advising model",
        badge: "Live",
      },
      {
        title: "Counselling",
        href: "/counsel",
        icon: Mic,
        description: "Talk to the advisor - voice or text, English, Nepali or a mix",
        badge: "Voice",
      },
      {
        title: "Pathways",
        href: "/pathways",
        icon: Route,
        description: "Explore, compare, and inspect evidence for each pathway",
      },
      {
        title: "Retrieval",
        href: "/retrieval",
        icon: Search,
        description: "Trace a query through BM25, dense, RRF fusion and reranking",
        badge: "C1",
      },
      {
        title: "Curriculum",
        href: "/curriculum",
        icon: BookOpen,
        description: "Browse the ingested Softwarica modules the advisor retrieves over",
      },
      {
        title: "Skills & Interests",
        href: "/skills",
        icon: Network,
        description: "Curriculum skill map, gaps, and interest alignment",
      },
      {
        title: "AI reasoning",
        href: "/reasoning",
        icon: Brain,
        description: "Why the advisor decided that - context, bias, evidence, pathways",
      },
      {
        title: "Analytics",
        href: "/analytics",
        icon: BarChart3,
        description: "Retrieval, bias, and contribution metrics (C1–C4)",
      },
      {
        title: "Models",
        href: "/models",
        icon: Boxes,
        description: "Every model in the stack, what it does, and why it was chosen",
      },
      {
        title: "Bias Lab",
        href: "/bias-lab",
        icon: FlaskConical,
        description: "Detector designs compared on held-out data, negative results included",
        badge: "C2b",
      },
    ],
  },
  {
    label: "Robotics",
    items: [
      {
        title: "Mission control",
        href: "/control",
        icon: Radio,
        description: "Live ROS2 operator console - drive, gesture, telemetry",
        badge: "Live",
      },
      {
        title: "Robot twin",
        href: "/robot",
        icon: CircuitBoard,
        description: "Live 6-DOF gesture control, telemetry, and session state",
        badge: "Sim",
      },
    ],
  },
  {
    label: "You",
    items: [
      {
        title: "Profile",
        href: "/profile",
        icon: UserCircle,
        description: "Session-scoped academic profile (device-local, no PII)",
      },
      {
        title: "Achievements",
        href: "/achievements",
        icon: Trophy,
        description: "Anti-bias exploration badges and decision diversity",
      },
      {
        title: "Preferences",
        href: "/preferences",
        icon: SlidersHorizontal,
        description: "Advising defaults, geography, theme, and backend",
      },
      {
        title: "About",
        href: "/about",
        icon: Info,
        description: "Architecture, research contributions, and ethics",
      },
    ],
  },
];

/** Flat list of every nav item, for breadcrumb / title lookups. */
export const NAV_FLAT: NavItem[] = NAV.flatMap((s) => s.items);

export function navItemForPath(pathname: string): NavItem | undefined {
  // Exact match first, then longest-prefix match (so /pathways/x still resolves).
  const exact = NAV_FLAT.find((i) => i.href === pathname);
  if (exact) return exact;
  return NAV_FLAT.filter((i) => i.href !== "/" && pathname.startsWith(i.href)).sort(
    (a, b) => b.href.length - a.href.length,
  )[0];
}

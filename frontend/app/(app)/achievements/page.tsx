"use client";

import { MessageSquare, Eye, Search, Trophy } from "lucide-react";

import { useStore } from "@/lib/store";
import { computeProgress, computeQuests } from "@/lib/achievements";
import type { CertificateData } from "@/lib/certificate";
import { slug } from "@/lib/download";
import { RankProgress } from "@/components/gamification/rank-progress";
import { Quests } from "@/components/gamification/quests";
import { BadgeGallery } from "@/components/gamification/badge-gallery";
import { Certificate } from "@/components/gamification/certificate";
import { DiversityMeter } from "@/components/gamification/diversity-meter";
import { StatCard } from "@/components/shared/stat-card";

export default function AchievementsPage() {
  const { exploration, response, prefs, setPrefs } = useStore();
  const progress = computeProgress(exploration, response);
  const quests = computeQuests(exploration, response);

  const certData: CertificateData = {
    name: prefs.displayName,
    rank: progress.rank.name,
    level: progress.level,
    badges: progress.earned,
    badgeTotal: progress.total,
    pathways: exploration.pathwaysViewed.size,
    diversity: progress.diversityScore,
    date: new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }),
    id:
      "DRONA-" +
      slug(prefs.displayName || "explorer").slice(0, 8).toUpperCase() +
      "-" +
      String(progress.xp).padStart(4, "0"),
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <RankProgress progress={progress} />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total XP" value={progress.xp} icon={Trophy} accent="brand" />
        <StatCard label="Questions asked" value={exploration.queriesAsked} icon={MessageSquare} accent="international" />
        <StatCard label="Pathways viewed" value={exploration.pathwaysViewed.size} icon={Eye} accent="regional" />
        <StatCard label="Citations opened" value={exploration.citationsOpened} icon={Search} accent="synthetic" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <BadgeGallery badges={progress.badges} />
          <Certificate data={certData} onNameChange={(v) => setPrefs({ displayName: v })} />
        </div>
        <div className="space-y-4">
          <Quests quests={quests} />
          <DiversityMeter response={response} />
        </div>
      </div>
    </div>
  );
}

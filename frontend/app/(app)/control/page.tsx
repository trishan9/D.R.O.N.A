"use client";

import { CommandCenter } from "@/components/robot/command-center";
import { SectionHeading } from "@/components/shared/section-heading";

export default function ControlPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <SectionHeading
        title="Mission control"
        description="Live ROS2 operator console over rosbridge - drive the mobile base, play gestures, inject a question, and watch joint/engagement/session telemetry. Every control publishes a real ROS2 message; all of them stay disabled until the link is up."
      />
      <CommandCenter />
    </div>
  );
}

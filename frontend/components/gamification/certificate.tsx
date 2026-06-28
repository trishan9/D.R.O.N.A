"use client";

import * as React from "react";
import { Award, FileImage, FileCode2, Loader2 } from "lucide-react";

import { certificateSvg, type CertificateData } from "@/lib/certificate";
import { downloadPng, downloadSvg, slug } from "@/lib/download";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface CertificateProps {
  data: CertificateData;
  onNameChange: (value: string) => void;
}

export function Certificate({ data, onNameChange }: CertificateProps) {
  const svg = React.useMemo(() => certificateSvg(data), [data]);
  const [busy, setBusy] = React.useState(false);
  const file = slug(data.name || "drona") + "-certificate";

  const savePng = async () => {
    setBusy(true);
    try {
      await downloadPng(svg, `${file}.png`, 2);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2 space-y-0 border-b py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
          <Award className="h-4 w-4 text-brand" /> Your certificate
        </CardTitle>
        <div className="flex gap-2">
          <Button size="sm" onClick={savePng} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileImage className="h-4 w-4" />}
            Download PNG
          </Button>
          <Button size="sm" variant="outline" onClick={() => downloadSvg(svg, `${file}.svg`)}>
            <FileCode2 className="h-4 w-4" /> SVG
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <Input
            value={data.name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Type your name for the certificate"
            className="h-9 max-w-xs"
          />
          <span className="text-xs text-muted-foreground">Personalise, then download.</span>
        </div>
        <div
          className="overflow-hidden rounded-xl border shadow-card [&>svg]:h-auto [&>svg]:w-full"
          dangerouslySetInnerHTML={{ __html: svg }}
        />
      </CardContent>
    </Card>
  );
}

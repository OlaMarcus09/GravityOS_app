"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge, Button, Card, EmptyState, ErrorText, PageHeader, Select, Spinner, StatTile } from "@/components/ui";
import type { StreamingSnapshot } from "@/lib/api";
import { useArtistStreamingLink, useStreamingHistory, useStreamingMutations, useStreamingSummary } from "@/lib/queries/useStreaming";
import { useWorkspace } from "@/lib/workspace";

const GROUPS = ["social", "streaming", "popularity", "retention", "score"] as const;
type Range = "7" | "30" | "90" | "all";

const numberFormat = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

function formatValue(value: number | string) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numberFormat.format(numeric) : String(value);
}

function formatGroup(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function TrendChart({ points }: { points: StreamingSnapshot[] }) {
  if (points.length === 0) {
    return <div className="analytics-chart-empty">No stored points for this selection yet.</div>;
  }

  const values = points.map((point) => Number(point.value)).filter(Number.isFinite);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = max - min || Math.max(max * 0.08, 1);
  const width = 720;
  const height = 230;
  const chartPoints = points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
    const y = height - ((Number(point.value) - min) / spread) * (height - 32) - 16;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const first = Number(points[0].value);
  const last = Number(points[points.length - 1].value);
  const change = first ? ((last - first) / Math.abs(first)) * 100 : null;

  return (
    <div>
      <div className="analytics-chart-summary">
        <div>
          <span className="eyebrow">Latest</span>
          <strong>{formatValue(last)}</strong>
        </div>
        <div>
          <span className="eyebrow">Change</span>
          <strong style={{ color: change !== null && change >= 0 ? "var(--success)" : "var(--danger)" }}>
            {change === null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(1)}%`}
          </strong>
        </div>
        <time dateTime={points[points.length - 1].captured_at}>
          {new Date(points[points.length - 1].captured_at).toLocaleDateString()}
        </time>
      </div>
      <div className="analytics-chart-wrap">
        <svg className="analytics-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Soundcharts metric trend">
          {[0, 1, 2, 3].map((line) => {
            const y = 16 + (line / 3) * (height - 32);
            return <line key={line} x1="0" x2={width} y1={y} y2={y} className="analytics-chart-grid" />;
          })}
          <polyline points={chartPoints} className="analytics-chart-line" />
          {points.map((point, index) => {
            const x = points.length === 1 ? width / 2 : (index / (points.length - 1)) * width;
            const y = height - ((Number(point.value) - min) / spread) * (height - 32) - 16;
            return <circle key={`${point.id}-${index}`} cx={x} cy={y} r="4" className="analytics-chart-dot" />;
          })}
        </svg>
      </div>
      <div className="analytics-chart-axis">
        <span>{new Date(points[0].captured_at).toLocaleDateString()}</span>
        <span>{points.length} stored snapshot{points.length === 1 ? "" : "s"}</span>
        <span>{new Date(points[points.length - 1].captured_at).toLocaleDateString()}</span>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { workspaceId, isReadOnly } = useWorkspace();
  const [range, setRange] = useState<Range>("30");
  const [metricGroup, setMetricGroup] = useState<string>("streaming");
  const [platform, setPlatform] = useState("all");
  const link = useArtistStreamingLink(workspaceId);
  const summary = useStreamingSummary(workspaceId);
  const history = useStreamingHistory(workspaceId);
  const mutations = useStreamingMutations(workspaceId);

  const availableGroups = useMemo(() => {
    const groups = Array.from(new Set((summary.data ?? []).map((item) => item.metric_type)));
    return groups.length ? GROUPS.filter((group) => groups.includes(group)) : GROUPS;
  }, [summary.data]);

  const availablePlatforms = useMemo(() => {
    const platforms = Array.from(new Set((history.data ?? []).filter((item) => item.metric_type === metricGroup).map((item) => item.platform)));
    return platforms.sort();
  }, [history.data, metricGroup]);

  const filteredPoints = useMemo(() => {
    const cutoff = range === "all" ? 0 : Date.now() - Number(range) * 24 * 60 * 60 * 1000;
    return (history.data ?? [])
      .filter((item) => item.metric_type === metricGroup && (platform === "all" || item.platform === platform))
      .filter((item) => new Date(item.captured_at).getTime() >= cutoff)
      .sort((a, b) => new Date(a.captured_at).getTime() - new Date(b.captured_at).getTime());
  }, [history.data, metricGroup, platform, range]);

  const latestMetrics = useMemo(() => (summary.data ?? []).slice().sort((a, b) => `${a.metric_type}-${a.platform}`.localeCompare(`${b.metric_type}-${b.platform}`)), [summary.data]);
  const lastCaptured = latestMetrics.reduce<string | null>((latest, item) => !latest || item.captured_at > latest ? item.captured_at : latest, null);

  if (link.isLoading || summary.isLoading || history.isLoading) return <Spinner label="Loading Soundcharts analytics…" />;

  return (
    <div>
      <PageHeader
        title="Soundcharts analytics"
        subtitle="A snapshot-based view of your artist audience and streaming signals."
        action={link.data && !isReadOnly ? (
          <Button size="sm" onClick={() => mutations.sync.mutate(link.data!.id)} disabled={mutations.sync.isPending}>
            {mutations.sync.isPending ? "Syncing…" : "Sync now"}
          </Button>
        ) : undefined}
      />

      <ErrorText error={link.error ?? summary.error ?? history.error ?? mutations.sync.error} />

      {!link.data ? (
        <EmptyState
          title="Connect a Soundcharts artist to unlock analytics"
          hint={isReadOnly ? "Ask a workspace editor to connect the artist in Settings." : "Connecting stores the identity only. It does not call Soundcharts or spend API credits."}
          action={!isReadOnly ? <Link href="/settings" className="button-link">Open Soundcharts settings</Link> : undefined}
        />
      ) : (
        <div className="analytics-page-stack">
          <Card className="analytics-connection-card">
            <div>
              <span className="eyebrow">Connected artist</span>
              <strong className="analytics-uuid">{link.data.soundcharts_uuid}</strong>
            </div>
            <div className="analytics-connection-meta">
              <Badge tone="success">Soundcharts connected</Badge>
              <span>Last imported {lastCaptured ? new Date(lastCaptured).toLocaleString() : "not yet"}</span>
              <Link href="/settings">Manage connection</Link>
            </div>
          </Card>

          <div className="stat-grid analytics-stat-grid">
            <Card><StatTile label="Signals" value={latestMetrics.length} hint="Latest metric/platform pairs" tone="cyan" /></Card>
            <Card><StatTile label="Platforms" value={new Set(latestMetrics.map((item) => item.platform)).size} hint="Across imported groups" tone="accent" /></Card>
            <Card><StatTile label="Snapshots" value={history.data?.length ?? 0} hint="Stored points available" tone="success" /></Card>
            <Card><StatTile label="Refresh" value="15 min" hint="Minimum sync cooldown" tone="accent" /></Card>
          </div>

          <div className="split-2 analytics-main-grid">
            <Card>
              <div className="analytics-section-heading">
                <div>
                  <span className="eyebrow">Trend explorer</span>
                  <h2>Stored metric history</h2>
                </div>
                <div className="analytics-filters">
                  <Select aria-label="Metric group" value={metricGroup} onChange={(event) => { setMetricGroup(event.target.value); setPlatform("all"); }}>
                    {availableGroups.map((group) => <option key={group} value={group}>{formatGroup(group)}</option>)}
                  </Select>
                  <Select aria-label="Platform" value={platform} onChange={(event) => setPlatform(event.target.value)}>
                    <option value="all">All platforms</option>
                    {availablePlatforms.map((item) => <option key={item} value={item}>{formatGroup(item)}</option>)}
                  </Select>
                  <Select aria-label="Time range" value={range} onChange={(event) => setRange(event.target.value as Range)}>
                    <option value="7">7 days</option>
                    <option value="30">30 days</option>
                    <option value="90">90 days</option>
                    <option value="all">All time</option>
                  </Select>
                </div>
              </div>
              {platform === "all" && new Set(filteredPoints.map((item) => item.platform)).size > 1 ? (
                <p className="analytics-chart-note">Select one platform to see a comparable trend line.</p>
              ) : <TrendChart points={filteredPoints} />}
            </Card>

            <Card>
              <div className="analytics-section-heading">
                <div>
                  <span className="eyebrow">Latest pulse</span>
                  <h2>Current signals</h2>
                </div>
                <Badge tone="accent">Read-only</Badge>
              </div>
              {latestMetrics.length ? (
                <div className="analytics-latest-list">
                  {latestMetrics.map((item) => (
                    <div className="analytics-latest-row" key={`${item.metric_type}-${item.platform}`}>
                      <div><strong>{formatGroup(item.platform)}</strong><small>{formatGroup(item.metric_type)}</small></div>
                      <strong>{formatValue(item.value)}</strong>
                    </div>
                  ))}
                </div>
              ) : <p className="analytics-muted">No imported metrics yet. Use Sync now once credentials and an artist UUID are configured.</p>}
            </Card>
          </div>

          <Card>
            <div className="analytics-section-heading">
              <div>
                <span className="eyebrow">Data policy</span>
                <h2>Designed for predictable API usage</h2>
              </div>
            </div>
            <p className="analytics-muted" style={{ marginBottom: 0 }}>
              This page reads the snapshots already stored in GravityOS. It never calls Soundcharts when you open or filter the dashboard. A workspace editor can manually refresh the data, subject to the 15-minute cooldown.
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}

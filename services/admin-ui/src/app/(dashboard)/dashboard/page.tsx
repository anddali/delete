"use client";

import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatRelativeTime } from "@/lib/utils";
import {
  Database,
  FileText,
  Key,
  Clock,
  Search,
  AlertCircle,
} from "lucide-react";

export default function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: dashboardApi.stats,
  });

  const { data: activity } = useQuery({
    queryKey: ["dashboard-activity"],
    queryFn: () => dashboardApi.activity(10),
  });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  const statCards = [
    {
      title: "Active Sources",
      value: stats?.active_sources || 0,
      total: stats?.total_sources || 0,
      icon: Database,
      color: "text-blue-600",
    },
    {
      title: "Documents",
      value: stats?.total_documents || 0,
      icon: FileText,
      color: "text-green-600",
    },
    {
      title: "Chunks",
      value: stats?.total_chunks || 0,
      icon: FileText,
      color: "text-purple-600",
    },
    {
      title: "Active Tokens",
      value: stats?.active_tokens || 0,
      total: stats?.total_tokens || 0,
      icon: Key,
      color: "text-orange-600",
    },
    {
      title: "Jobs Today",
      value: stats?.jobs_today || 0,
      icon: Clock,
      color: "text-indigo-600",
    },
    {
      title: "Queries Today",
      value: stats?.queries_today || 0,
      icon: Search,
      color: "text-cyan-600",
    },
  ];

  return (
    <div>
      <h1 className="mb-6 text-3xl font-bold">Dashboard</h1>

      {/* Stats Grid */}
      <div className="mb-8 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {statCards.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {stat.title}
              </CardTitle>
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stat.value.toLocaleString()}
              </div>
              {stat.total !== undefined && (
                <p className="text-xs text-muted-foreground">
                  of {stat.total.toLocaleString()} total
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Failed Jobs Alert */}
      {stats?.jobs_failed_today > 0 && (
        <Card className="mb-8 border-red-200 bg-red-50">
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <CardTitle className="text-lg text-red-800">
              {stats.jobs_failed_today} Failed Jobs Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-red-700">
              Some ingestion jobs have failed. Check the Jobs page for details.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {activity?.map((item: any, index: number) => (
              <div
                key={index}
                className="flex items-center justify-between border-b pb-2 last:border-0"
              >
                <div>
                  <p className="font-medium">
                    {item.action} {item.resource_type}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    by {item.user}
                  </p>
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatRelativeTime(item.timestamp)}
                </span>
              </div>
            ))}
            {(!activity || activity.length === 0) && (
              <p className="text-muted-foreground">No recent activity</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

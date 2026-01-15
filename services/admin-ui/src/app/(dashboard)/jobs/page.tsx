"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { jobsApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import { XCircle, RefreshCw } from "lucide-react";

export default function JobsPage() {
  const [page, setPage] = useState(1);
  const queryClient = useQueryClient();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["jobs", page],
    queryFn: () => jobsApi.list({ page }),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const cancelMutation = useMutation({
    mutationFn: jobsApi.cancel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });

  const getStatusBadge = (status: string) => {
    const variants: Record<
      string,
      "default" | "success" | "destructive" | "warning" | "secondary"
    > = {
      pending: "secondary",
      running: "warning",
      completed: "success",
      failed: "destructive",
      cancelled: "secondary",
    };
    return <Badge variant={variants[status] || "default"}>{status}</Badge>;
  };

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Ingestion Jobs</h1>
        <Button variant="outline" onClick={() => refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Source</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Completed</TableHead>
                <TableHead>Result</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items?.map((job: any) => (
                <TableRow key={job.id}>
                  <TableCell className="font-medium">
                    {job.source_name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{job.type}</Badge>
                  </TableCell>
                  <TableCell>{getStatusBadge(job.status)}</TableCell>
                  <TableCell>
                    {job.progress ? (
                      <div className="text-sm">
                        <div>{job.progress.current_step}</div>
                        {job.progress.total && (
                          <div className="text-muted-foreground">
                            {job.progress.processed}/{job.progress.total}
                          </div>
                        )}
                      </div>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell>
                    {job.started_at ? formatDate(job.started_at) : "-"}
                  </TableCell>
                  <TableCell>
                    {job.completed_at ? formatDate(job.completed_at) : "-"}
                  </TableCell>
                  <TableCell>
                    {job.result ? (
                      <div className="text-sm">
                        <div>+{job.result.documents_added} docs</div>
                        <div>~{job.result.documents_updated} updated</div>
                        {job.result.errors?.length > 0 && (
                          <div className="text-red-600">
                            {job.result.errors.length} errors
                          </div>
                        )}
                      </div>
                    ) : job.error ? (
                      <span className="text-sm text-red-600">{job.error}</span>
                    ) : (
                      "-"
                    )}
                  </TableCell>
                  <TableCell>
                    {(job.status === "pending" || job.status === "running") && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => cancelMutation.mutate(job.id)}
                        disabled={cancelMutation.isPending}
                      >
                        <XCircle className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {(!data?.items || data.items.length === 0) && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="text-center text-muted-foreground"
                  >
                    No jobs found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          {data?.total > data?.page_size && (
            <div className="mt-4 flex justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                Previous
              </Button>
              <span className="flex items-center text-sm">
                Page {page} of {Math.ceil(data.total / data.page_size)}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={page * data.page_size >= data.total}
              >
                Next
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
